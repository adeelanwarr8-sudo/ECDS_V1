import pytest
from geo_utils import validate_aoi, AOIError


def rect(x1,y1,x2,y2):
    return {"type":"Polygon","coordinates":[[[x1,y1],[x2,y1],[x2,y2],[x1,y2],[x1,y1]]]}


def test_valid_swedish_aoi():
    result=validate_aoi(rect(17.9,59.2,17.99,59.25))
    assert 50 <= result['area_ha'] <= 5000


def test_oversized_rejected():
    with pytest.raises(AOIError,match="maximum"):
        validate_aoi(rect(17.8,59.1,18.3,59.5))


def test_outside_sweden_rejected():
    with pytest.raises(AOIError,match="outside Sweden"):
        validate_aoi(rect(10.0,51.0,10.1,51.05))


def test_multiple_aois_rejected():
    with pytest.raises(AOIError,match="Exactly one"):
        validate_aoi({"type":"FeatureCollection","features":[{"type":"Feature","geometry":rect(17.9,59.2,17.99,59.25),"properties":{}}, {"type":"Feature","geometry":rect(17.9,59.2,17.99,59.25),"properties":{}}]})


def test_sweden_boundary_file_is_resolvable():
    from geo_utils import sweden_boundary
    boundary = sweden_boundary()
    assert not boundary.is_empty
    assert boundary.is_valid
