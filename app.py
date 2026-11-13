"""ECDS | Environmental Crime Detection System — Increment 2.

GEE-powered environmental land-change screening (not criminal evidence).
"""
from __future__ import annotations

import json
from datetime import date

import folium
import streamlit as st
from folium.plugins import Draw, Fullscreen, MeasureControl
from streamlit_folium import st_folium

from geo_utils import AOIError, MAX_HA, MIN_HA, validate_aoi
from gee_engine import EngineError, initialize_earth_engine, run_detection, validate_inputs

st.set_page_config(
    page_title="ECDS | Environmental Crime Detection System",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  .block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1600px; }
  [data-testid="stSidebar"] { background-color: #f1f5f8; }
  [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {color: #17364a;}
  .ecds-header {background: #17364a; color: #fff; padding: 18px 22px; border-radius: 10px; margin-bottom: 13px; }
  .ecds-title {font-size: 1.9rem; font-weight: 750; letter-spacing: .02em;}
  .ecds-subtitle {font-size: .95rem; color: #d5e5ee; margin-top: 3px;}
  .ecds-pill {display: inline-block; color: #dce8ed; border: 1px solid #7996a8; border-radius: 20px; font-size:.73rem; padding:2px 10px; margin-top:9px;}
  .section-hint {color:#596b78; font-size:.87rem;}
</style>
""", unsafe_allow_html=True)

MUNICIPALITIES = {
    "Sweden (overview)": (62.0, 16.0, 5),
    "Stockholm": (59.3293, 18.0686, 11),
    "Norrtälje": (59.7580, 18.7049, 11),
    "Uppsala": (59.8586, 17.6389, 11),
    "Göteborg": (57.7089, 11.9746, 11),
    "Malmö": (55.6050, 13.0038, 11),
    "Umeå": (63.8258, 20.2630, 11),
    "Östersund": (63.1792, 14.6357, 11),
    "Luleå": (65.5848, 22.1547, 11),
}

for key, initial in {
    "accepted_aoi": None,
    "aoi_origin": None,
    "last_drawing_signature": None,
    "map_city": "Sweden (overview)",
    "map_epoch": 0,
    "detection_result": None,
    "detection_error": None,
    "detection_signature": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = initial

st.markdown("""
<div class="ecds-header">
<div class="ecds-title">ECDS</div>
<div class="ecds-subtitle">Environmental Crime Detection System</div>
<div class="ecds-pill">Prototype · Geospatial screening · Analyst review required</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("Analysis Configuration")
    st.caption("Increment 2 — Earth Engine screening")
    st.divider()
    st.subheader("1 · Study Area")
    municipality = st.selectbox(
        "Navigate to municipality", list(MUNICIPALITIES),
        index=list(MUNICIPALITIES).index(st.session_state.map_city),
        help="Map navigation only. This does not select a complete municipal boundary or create an AOI.",
    )
    st.session_state.map_city = municipality
    st.caption("Select a location, then draw a polygon/rectangle on the map or upload one GeoJSON polygon.")
    st.info(f"Allowed AOI: **{MIN_HA:,.0f}–{MAX_HA:,.0f} ha** (0.5–50 km²). One AOI per analysis, within Sweden.")
    uploaded = st.file_uploader("Upload AOI (.geojson or .json)", type=["geojson", "json"])
    if uploaded is not None:
        file_signature = f"{uploaded.name}:{uploaded.size}:{hash(uploaded.getvalue())}"
        if st.session_state.get("uploaded_signature") != file_signature:
            try:
                accepted = validate_aoi(uploaded.getvalue())
                st.session_state.accepted_aoi = accepted
                st.session_state.detection_result = None
                st.session_state.aoi_origin = "Uploaded GeoJSON"
                st.session_state.uploaded_signature = file_signature
                st.success("Uploaded AOI accepted.")
            except (AOIError, ValueError, json.JSONDecodeError) as exc:
                st.error(str(exc))
    if st.session_state.accepted_aoi:
        st.success(f"AOI accepted · {st.session_state.accepted_aoi['area_ha']:,.2f} ha")
        st.caption(f"Source: {st.session_state.aoi_origin}")
    else:
        st.warning("No valid AOI selected.")
    if st.button("Remove AOI", use_container_width=True):
        st.session_state.accepted_aoi = None
        st.session_state.detection_result = None
        st.session_state.aoi_origin = None
        st.session_state.uploaded_signature = None
        st.session_state.last_drawing_signature = None
        st.session_state.map_epoch += 1
        st.rerun()

    st.divider()
    st.subheader("2 · Analysis Period")
    season = st.selectbox("Season", ["Summer (Jun–Aug)", "Late summer (Jul–Sep)", "Growing season (May–Sep)"], index=0)
    # ECDS study window: complete calendar years 2016 through 2025 only.
    min_analysis_date = date(2016, 1, 1)
    max_analysis_date = date(2025, 12, 31)
    years = list(range(2025, 2015, -1))
    before_year = st.selectbox("Reference year", years, index=1)
    after_year = st.selectbox("Comparison year", years, index=0)
    season_bounds = {"Summer (Jun–Aug)": ((6,1), (8,31)), "Late summer (Jul–Sep)": ((7,1), (9,30)), "Growing season (May–Sep)": ((5,15), (9,15))}
    (sm, sd), (em, ed) = season_bounds[season]
    st.caption("Permitted analysis period: **2016–2025** (inclusive).")
    with st.expander("Review or edit exact dates", expanded=False):
        before_start = st.date_input("Reference start", date(before_year, sm, sd),
                                     min_value=min_analysis_date, max_value=max_analysis_date,
                                     key=f"before_start_{before_year}_{season}")
        before_end = st.date_input("Reference end", date(before_year, em, ed),
                                   min_value=min_analysis_date, max_value=max_analysis_date,
                                   key=f"before_end_{before_year}_{season}")
        after_start = st.date_input("Comparison start", date(after_year, sm, sd),
                                    min_value=min_analysis_date, max_value=max_analysis_date,
                                    key=f"after_start_{after_year}_{season}")
        after_end = st.date_input("Comparison end", date(after_year, em, ed),
                                  min_value=min_analysis_date, max_value=max_analysis_date,
                                  key=f"after_end_{after_year}_{season}")
    dates_valid = (min_analysis_date <= before_start < before_end < after_start < after_end <= max_analysis_date)
    if not dates_valid:
        st.error("Analysis periods must be sequential and entirely within 2016–2025.")

    st.divider()
    st.subheader("3 · Detection Settings")
    st.caption("Defaults preserved from the existing GEE application.")
    with st.expander("Advanced spectral and processing thresholds", expanded=False):
        ndvi_drop = st.slider("Minimum NDVI decrease", 0.10, 0.50, 0.25, 0.01)
        bsi_rise = st.slider("Minimum BSI increase", 0.00, 0.30, 0.08, 0.01)
        nbr_drop = st.slider("Minimum NBR decrease", 0.05, 0.40, 0.15, 0.01)
        min_patch = st.slider("Minimum patch size (ha)", 0.25, 10.0, 1.0, 0.25)
        cloud_score = st.slider("Cloud Score+ clear threshold", 0.40, 0.90, 0.65, 0.05)
    if st.session_state.accepted_aoi is None:
        st.caption("An accepted AOI is required before detection.")
    active_config = {
        "geometry": st.session_state.accepted_aoi["geometry"] if st.session_state.accepted_aoi else None,
        "before_start": before_start.isoformat(), "before_end": before_end.isoformat(),
        "after_start": after_start.isoformat(), "after_end": after_end.isoformat(),
        "thresholds": {"ndvi_decrease": ndvi_drop, "bsi_increase": bsi_rise,
            "nbr_decrease": nbr_drop, "min_patch_ha": min_patch,
            "cloud_score_clear_threshold": cloud_score},
    }
    signature = json.dumps(active_config, sort_keys=True)
    previous = st.session_state.get("detection_signature")
    if st.session_state.detection_result and signature != previous:
        st.warning("Parameters changed after the last run. Previous detection is hidden until re-run.")
    if st.button("🛰️ Run Detection", type="primary", disabled=not (st.session_state.accepted_aoi and dates_valid),
                 use_container_width=True):
        st.session_state.detection_result = None
        st.session_state.detection_error = None
        try:
            validate_inputs(active_config)
            with st.spinner("Running Earth Engine land-change screening and candidate extraction…"):
                ee = initialize_earth_engine(st.secrets)
                result = run_detection(active_config, ee)
            st.session_state.detection_result = result
            st.session_state.detection_signature = signature
            st.success("Change screening completed.")
        except (ValueError, EngineError, Exception) as exc:
            # Never render credentials or raw authentication error details.
            st.session_state.detection_error = str(exc) if isinstance(exc, (ValueError, EngineError)) else (
                "Earth Engine processing failed. Check configured permissions, imagery coverage and selected thresholds."
            )
            st.error(st.session_state.detection_error)
    st.caption("Public imagery only · Results are screening leads, not evidence.")

result = st.session_state.detection_result if st.session_state.get("detection_signature") == json.dumps(active_config,sort_keys=True) else None


workspace, candidates_tab, analytics_tab, reports_tab = st.tabs(
    ["Detection Workspace", "Candidate Intelligence", "Spatial Analytics", "Reports & Data"]
)

with workspace:
    lhs, rhs = st.columns([0.26, 0.74], gap="medium")
    with lhs:
        st.subheader("Study Area")
        aoi = st.session_state.accepted_aoi
        if aoi:
            st.metric("Selected area", f"{aoi['area_ha']:,.1f} ha")
            st.caption(f"{aoi['area_km2']:.2f} km² · {st.session_state.aoi_origin}")
            st.caption("Sweden boundary: preliminary coarse screening, not cadastral precision.")
        else:
            st.metric("Selected area", "—")
            st.caption("Draw a polygon or rectangle with the map tools.")
        st.markdown("**Analysis comparison**")
        st.write(f"{before_start.isoformat()} → {before_end.isoformat()}")
        st.write(f"{after_start.isoformat()} → {after_end.isoformat()}")
        st.caption("The two periods must cover comparable seasons.")
        st.markdown("**Detection status**")
        if result:
            st.success(f"Completed · {result['scene_counts']['before']} before / {result['scene_counts']['after']} after scenes")
            st.caption(f"Valid paired-image area: {result['valid_area_ha']:,.1f} ha")
        else:
            st.info(st.session_state.detection_error or "No current detection. Configure Earth Engine credentials and run screening.")

    with rhs:
        h1, h2 = st.columns([0.7, 0.3])
        h1.subheader("Interactive GIS Map")
        base_map = h2.selectbox("Basemap", ["Satellite", "OpenStreetMap"], label_visibility="collapsed")
        lat, lon, zoom = MUNICIPALITIES[municipality]
        if st.session_state.accepted_aoi:
            lat, lon = st.session_state.accepted_aoi["center"]
            zoom = 12
        m = folium.Map(location=[lat, lon], zoom_start=zoom, tiles=None, control_scale=True,
                       prefer_canvas=True)
        folium.TileLayer("OpenStreetMap", name="OpenStreetMap", show=base_map == "OpenStreetMap").add_to(m)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Tiles © Esri and contributors", name="Satellite", show=base_map == "Satellite"
        ).add_to(m)
        if result:
            active_layer = st.selectbox("Detection layer", ["After RGB", "Before RGB", "ΔNDVI", "Flagged pixels"],
                                        key="detection_layer")
            # Only the selected EE raster layer is requested, avoiding unnecessary tile rendering.
            folium.TileLayer(tiles=result['tiles'][active_layer], name=active_layer,
                             attr="Google Earth Engine / Copernicus / Google", overlay=True,
                             show=True, control=True, opacity=0.90).add_to(m)
            if result['features']:
                folium.GeoJson({"type":"FeatureCollection","features":result['features']},
                    name="Change candidates",style_function=lambda _: {
                    "color":"#ffab00","weight":2,"fillOpacity":.13},
                    tooltip=folium.GeoJsonTooltip(fields=["candidate_id","area_ha","mean_dNDVI"],
                                                aliases=["Candidate","Area (ha)","Mean ΔNDVI"])).add_to(m)
        if st.session_state.accepted_aoi:
            folium.GeoJson(st.session_state.accepted_aoi["geometry"], name="Accepted AOI",
                           style_function=lambda _: {"color":"#00e5ff", "weight":3, "fillOpacity":0.08}).add_to(m)
        Draw(export=False, draw_options={"polyline":False,"circle":False,"circlemarker":False,
                "marker":False,"polygon":True,"rectangle":True},
             edit_options={"edit":False,"remove":True}).add_to(m)
        Fullscreen().add_to(m)
        MeasureControl(primary_length_unit="kilometers", primary_area_unit="sqmeters").add_to(m)
        folium.LayerControl(collapsed=True).add_to(m)
        output = st_folium(m, height=550, use_container_width=True,
                           returned_objects=["last_active_drawing"], key=f"ecds-map-{st.session_state.map_epoch}")
        drawn = output.get("last_active_drawing") if output else None
        if drawn and drawn.get("geometry"):
            signature = json.dumps(drawn["geometry"], sort_keys=True)
            if signature != st.session_state.last_drawing_signature:
                st.session_state.last_drawing_signature = signature
                try:
                    accepted = validate_aoi(drawn["geometry"])
                    st.session_state.accepted_aoi = accepted
                    st.session_state.detection_result = None
                    st.session_state.aoi_origin = "Drawn on map"
                    st.rerun()
                except AOIError as exc:
                    st.error(f"Drawn AOI rejected: {exc}")
        st.caption("Draw one AOI using the toolbar. Satellite tiles load from an external public map service. No police data are used.")

    st.divider()
    k1, k2, k3 = st.columns(3)
    k1.metric("Detected Sites", f"{result['total_candidates']:,}" if result else "—")
    k2.metric("Protected Areas", "Not assessed")
    k3.metric("Disturbed Area", f"{result['disturbed_ha']:,.2f} ha" if result else "—")
    st.subheader("Candidate Results")
    if result and result['features']:
        rows = [{"Rank":f['properties']['rank'],"Candidate":f['properties']['candidate_id'],
            "Area (ha)":round(f['properties']['area_ha'],3),
            "Mean ΔNDVI":round(f['properties']['mean_dNDVI'],3),
            "Priority":round(f['properties']['priority'],3),"Review status":"Not reviewed"}
            for f in result['features']]
        st.dataframe(rows,use_container_width=True,hide_index=True)
        if result['truncated']:
            st.warning(f"Showing the first {result['shown_candidates']} of {result['total_candidates']} candidates; exports are similarly limited.")
    else:
        st.info("No candidate results yet." if not result else "No qualifying patches found with current settings.")
    st.caption("Protected-area and felling-notification cross-checking are planned for Increment 3.")

with candidates_tab:
    st.subheader("Candidate Intelligence")
    if result and result['features']:
        st.caption("Change-screening candidates only · No criminal classification has been performed.")
        ids=[f['properties']['candidate_id'] for f in result['features']]
        selected=st.selectbox("Inspect candidate",ids)
        feat=next(f for f in result['features'] if f['properties']['candidate_id']==selected)
        props=feat['properties']
        c1,c2,c3=st.columns(3)
        c1.metric("Area",f"{props['area_ha']:.2f} ha")
        c2.metric("Mean ΔNDVI",f"{props['mean_dNDVI']:.3f}")
        c3.metric("Screening score",f"{props['priority']:.2f}")
        st.write(f"Candidate centre: {props['latitude']:.5f}, {props['longitude']:.5f}")
        st.info("Protected-area, notification and permit checks have not been conducted. Review status is not persisted in Increment 2.")
    else:
        st.info("Run detection to generate candidate polygons for review.")

with analytics_tab:
    st.subheader("Spatial Analytics")
    if result:
        st.metric("Detected change area",f"{result['disturbed_ha']:,.2f} ha")
        st.metric("Candidate polygons",result['total_candidates'])
        st.metric("Valid paired-imagery area",f"{result['valid_area_ha']:,.2f} ha")
        st.write("Sentinel-2 scenes: reference",result['scene_counts']['before'],
                 "· comparison",result['scene_counts']['after'])
        st.caption("Valid-area statistic represents cloud-masked pixel overlap, not detection accuracy. The thresholds are not calibrated.")
    else:
        st.info("No analysis results yet.")

with reports_tab:
    st.subheader("Reports & Data")
    if st.session_state.accepted_aoi:
        st.download_button("Download accepted AOI (GeoJSON)",
            data=json.dumps({"type":"FeatureCollection","features":[{"type":"Feature",
             "properties":{"area_ha":st.session_state.accepted_aoi['area_ha']},
             "geometry":st.session_state.accepted_aoi['geometry']}]},indent=2),
            file_name="ecds_accepted_aoi.geojson",mime="application/geo+json")
    settings = dict(active_config)
    settings.pop('geometry',None)
    settings.update({"application":"ECDS","increment":2,"analysis_executed":bool(result),
                     "aoi_area_ha":st.session_state.accepted_aoi['area_ha'] if st.session_state.accepted_aoi else None})
    st.download_button("Download configuration (JSON)",json.dumps(settings,indent=2),
                       file_name="ecds_configuration.json",mime="application/json")
    if result:
        fc={"type":"FeatureCollection","features":result['features']}
        st.download_button("Download screening candidates (GeoJSON)",json.dumps(fc),
                           file_name="ecds_change_candidates.geojson",mime="application/geo+json")
        import csv, io
        buf=io.StringIO()
        cols=['candidate_id','rank','area_ha','mean_dNDVI','priority','longitude','latitude','review_status']
        writer=csv.DictWriter(buf,fieldnames=cols)
        writer.writeheader()
        writer.writerows({k:f['properties'].get(k) for k in cols} for f in result['features'])
        st.download_button("Download screening candidates (CSV)",buf.getvalue(),
                           file_name="ecds_change_candidates.csv",mime="text/csv")
        st.caption("These exports contain only the displayed candidate subset (maximum 250). No protected-area or permit verification has been performed.")
        st.write("**Method:**",result['method'])
        st.write("**Datasets:**",result['source'])

st.divider()
st.caption("ECDS · Environmental change screening prototype · Detected changes are leads for analyst review, never proof of an offence.")
