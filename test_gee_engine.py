from datetime import date
import pytest
from gee_engine import validate_inputs


def rect(x1,y1,x2,y2):
    return {'type':'Polygon','coordinates':[[[x1,y1],[x2,y1],[x2,y2],[x1,y2],[x1,y1]]]}


def cfg():
    return {'geometry':rect(17.9,59.2,17.99,59.25),
            'before_start':'2024-06-01','before_end':'2024-08-31',
            'after_start':'2025-06-01','after_end':'2025-08-31',
            'thresholds':{'ndvi_decrease':.25,'bsi_increase':.08,
                'nbr_decrease':.15,'min_patch_ha':1.0,'cloud_score_clear_threshold':.65}}


def test_config_valid():
    validate_inputs(cfg())


def test_reject_2026():
    c=cfg(); c['after_end']='2026-08-31'
    with pytest.raises(ValueError,match='2016–2025'):
        validate_inputs(c)


def test_reject_bad_sequence():
    c=cfg(); c['before_start']='2025-06-01'
    with pytest.raises(ValueError,match='2016–2025'):
        validate_inputs(c)


def test_reject_oversized():
    c=cfg(); c['geometry']=rect(17.8,59.1,18.3,59.5)
    with pytest.raises(ValueError,match='maximum'):
        validate_inputs(c)


def test_reject_bad_threshold():
    c=cfg(); c['thresholds']['min_patch_ha']=100
    with pytest.raises(ValueError,match='min_patch_ha'):
        validate_inputs(c)
