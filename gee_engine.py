"""Earth Engine processing for ECDS Increment 2.

Open Sentinel-2, Cloud Score+, Dynamic World. Outputs are land-change
screening candidates, NOT findings of environmental offences.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

SCALE_M = 10
MAX_VECTOR_FEATURES = 250
MAX_CONNECTED_PIXELS = 1024

class EngineError(RuntimeError):
    """A human-readable Earth Engine processing failure."""


def initialize_earth_engine(secrets: Any | None = None):
    """Authenticate with Streamlit secrets or existing local EE credentials.

    Streamlit secrets: EE_PROJECT and either EE_SERVICE_ACCOUNT_JSON (full
    service account JSON as TOML multiline string) or EE_SERVICE_ACCOUNT
    plus EE_PRIVATE_KEY (PEM). Credentials never get returned to UI.
    """
    import ee
    try:
        s = dict(secrets) if secrets is not None else {}
    except Exception:
        s = {}
    project = s.get('EE_PROJECT')
    try:
        if s.get('EE_SERVICE_ACCOUNT_JSON'):
            info = json.loads(s['EE_SERVICE_ACCOUNT_JSON'])
            credentials = ee.ServiceAccountCredentials(info['client_email'], key_data=json.dumps(info))
            ee.Initialize(credentials, project=project)
        elif s.get('EE_SERVICE_ACCOUNT') and s.get('EE_PRIVATE_KEY'):
            credentials = ee.ServiceAccountCredentials(
                s['EE_SERVICE_ACCOUNT'], key_data=json.dumps({
                    'type': 'service_account',
                    'client_email': s['EE_SERVICE_ACCOUNT'],
                    'private_key': s['EE_PRIVATE_KEY'].replace('\\n','\n'),
                    'token_uri': 'https://oauth2.googleapis.com/token',
                }))
            ee.Initialize(credentials, project=project)
        else:
            ee.Initialize(project=project)
        return ee
    except Exception as exc:
        raise EngineError('Earth Engine is not configured or could not authenticate. Set EE_PROJECT and credentials in Streamlit secrets, or authenticate locally with the Earth Engine CLI.') from exc


def validate_inputs(config: dict) -> None:
    """Validate all processing constraints even if the UI is bypassed."""
    from geo_utils import validate_aoi
    validate_aoi(config['geometry'])
    starts = [date.fromisoformat(config[k]) for k in ('before_start','before_end','after_start','after_end')]
    if not (date(2016,1,1) <= starts[0] < starts[1] < starts[2] < starts[3] <= date(2025,12,31)):
        raise ValueError('Dates must be chronological and within 2016–2025.')
    params = config['thresholds']
    for key, low, high in [('ndvi_decrease',.10,.50),('bsi_increase',0,.30),('nbr_decrease',.05,.40),('min_patch_ha',.25,10),('cloud_score_clear_threshold',.40,.90)]:
        val = float(params[key])
        if not low <= val <= high:
            raise ValueError(f'Invalid {key}: expected {low}–{high}.')


def _collection(ee, aoi, start, end, clear_threshold):
    # End date exclusive in Earth Engine.
    end_plus = (date.fromisoformat(end) + timedelta(days=1)).isoformat()
    s2 = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
          .filterBounds(aoi).filterDate(start, end_plus)
          .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE',70)))
    linked = s2.linkCollection(ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED'), ['cs_cdf'])
    def mask(img):
        return (img.updateMask(img.select('cs_cdf').gte(clear_threshold))
                .select(['B2','B3','B4','B8','B11','B12']).multiply(0.0001))
    return linked.map(mask)


def _composite(ee, col, aoi):
    med = col.median()
    ndvi = med.normalizedDifference(['B8','B4']).rename('NDVI')
    nbr = med.normalizedDifference(['B8','B12']).rename('NBR')
    bsi = med.expression('((SWIR1+RED)-(NIR+BLUE))/((SWIR1+RED)+(NIR+BLUE))',
             {'SWIR1':med.select('B11'),'RED':med.select('B4'),
              'NIR':med.select('B8'),'BLUE':med.select('B2')}).rename('BSI')
    return med.addBands([ndvi,nbr,bsi]).clip(aoi)


def _tile_url(image, vis):
    return image.getMapId(vis)['tile_fetcher'].url_format


def run_detection(config: dict, ee) -> dict:
    """Compute screening masks, a bounded set of vector candidates and map tiles.

    Raises on failures rather than returning success with incomplete results.
    Earth Engine RPCs are synchronous; callers should show a spinner.
    """
    validate_inputs(config)
    aoi = ee.Geometry(config['geometry'])
    t = config['thresholds']
    before = _collection(ee,aoi,config['before_start'],config['before_end'],t['cloud_score_clear_threshold'])
    after = _collection(ee,aoi,config['after_start'],config['after_end'],t['cloud_score_clear_threshold'])
    counts = ee.Dictionary({'before':before.size(), 'after':after.size()}).getInfo()
    if not counts or not counts['before'] or not counts['after']:
        raise EngineError('No Sentinel-2 scenes found in one of the selected periods. Widen the seasonal windows.')
    b = _composite(ee,before,aoi)
    a = _composite(ee,after,aoi)
    dndvi = a.select('NDVI').subtract(b.select('NDVI')).rename('dNDVI')
    dbsi = a.select('BSI').subtract(b.select('BSI')).rename('dBSI')
    dnbr = b.select('NBR').subtract(a.select('NBR')).rename('dNBR')
    dw_end = (date.fromisoformat(config['before_end']) + timedelta(days=1)).isoformat()
    dw = (ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1')
          .filterBounds(aoi).filterDate(config['before_start'],dw_end).select('label'))
    dw_count = dw.size().getInfo()
    if not dw_count:
        raise EngineError('No reference Dynamic World observations in the selected period.')
    dw_mode = dw.mode()
    valid_land = ee.Image(1)
    for cls in (0,4,6,8):
        valid_land = valid_land.And(dw_mode.neq(cls))
    raw = (dndvi.lt(-t['ndvi_decrease'])
           .And(dbsi.gt(t['bsi_increase']).Or(dnbr.gt(t['nbr_decrease'])))
           .And(valid_land).And(b.select('NDVI').gt(.5)))
    min_px = max(1,min(MAX_CONNECTED_PIXELS,round(t['min_patch_ha']*10000/(SCALE_M*SCALE_M))))
    connected = raw.selfMask().connectedPixelCount(MAX_CONNECTED_PIXELS,True)
    flag = raw.updateMask(connected.gte(min_px)).selfMask().rename('flag').clip(aoi)
    # Quality indicator: pixels with valid data in both cloud-masked composites.
    good = b.select('NDVI').mask().And(a.select('NDVI').mask()).rename('valid')
    areas = ee.Image.cat([
        flag.multiply(ee.Image.pixelArea()).rename('disturbed_m2'),
        good.multiply(ee.Image.pixelArea()).rename('valid_m2'),
    ]).reduceRegion(reducer=ee.Reducer.sum(),geometry=aoi,scale=SCALE_M,
                   maxPixels=1e8,tileScale=4).getInfo() or {}
    if not areas.get('valid_m2'):
        raise EngineError('No valid cloud-free pixels were found across both periods.')
    vectors = flag.addBands(dndvi).reduceToVectors(
        geometry=aoi,scale=SCALE_M,geometryType='polygon',eightConnected=True,
        labelProperty='flag',reducer=ee.Reducer.mean(),maxPixels=1e8,tileScale=8)
    def properties(f):
        geom=f.geometry()
        centroid=geom.centroid(1).coordinates()
        area=geom.area(1).divide(10000)
        severity=ee.Number(f.get('mean'))
        score=area.multiply(severity.abs())
        return ee.Feature(geom,{
            'area_ha':area,'mean_dNDVI':severity,'priority':score,
            'longitude':centroid.get(0),'latitude':centroid.get(1),
            'review_status':'Not reviewed'})
    ranked = vectors.map(properties).sort('priority',False)
    # The count includes every result. Client download is explicitly capped.
    total=ranked.size().getInfo()
    shown=min(total,MAX_VECTOR_FEATURES)
    features=ranked.limit(MAX_VECTOR_FEATURES).getInfo().get('features',[]) if total else []
    for idx, f in enumerate(features, 1):
        f['properties']['rank']=idx
        f['properties']['candidate_id']=f'ECDS-{idx:04d}'
    vis_rgb={'bands':['B4','B3','B2'],'min':0,'max':0.15}
    vis_dndvi={'min':-.5,'max':.2,
        'palette':['b2182b','ef8a62','fddbc7','f7f7f7','d9f0d3','7fbf7b','1b7837']}
    return {
        'total_candidates':total,'shown_candidates':shown,
        'truncated':total>MAX_VECTOR_FEATURES,
        'disturbed_ha':round(float(areas.get('disturbed_m2') or 0)/10000,3),
        'valid_area_ha':round(float(areas['valid_m2'])/10000,3),
        'scene_counts':counts,'dynamic_world_scenes':dw_count,
        'features':features,
        'tiles':{
            'Before RGB':_tile_url(b,vis_rgb),
            'After RGB':_tile_url(a,vis_rgb),
            'ΔNDVI':_tile_url(dndvi,vis_dndvi),
            'Flagged pixels':_tile_url(flag,{'palette':['FF1744']})
        },
        'source':'Sentinel-2 SR Harmonized + Cloud Score+ + Dynamic World',
        'method':'Same-season median composites; ΔNDVI + (ΔBSI or ΔNBR); reference NDVI > 0.5; 8-connected minimum-area filter.',
        'config':config,
    }
