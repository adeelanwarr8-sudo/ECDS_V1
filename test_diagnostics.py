"""Regression tests for safe, stage-specific Earth Engine diagnostics."""
from gee_engine import _safe_error, _failure, EngineError, run_detection
from test_gee_engine import cfg


def test_redacts_auth_and_urls():
    source = 'Authorization:Bearer abc123 access_token=abc987 https://example.com/?token=secret'
    sanitized = _safe_error(ValueError(source))
    assert 'abc123' not in sanitized
    assert 'abc987' not in sanitized
    assert 'example.com' not in sanitized


def test_failure_has_stage_and_incident_no_detail():
    error = _failure('map tile generation', ValueError('access_token=supersecret'))
    assert isinstance(error, EngineError)
    assert 'map tile generation' in str(error)
    assert 'Diagnostic ID:' in str(error)
    assert 'supersecret' not in str(error)


def test_run_detection_reports_ee_stage_on_failure():
    class BadEE:
        @staticmethod
        def Geometry(value):
            raise RuntimeError('mock geometry failure')
    try:
        run_detection(cfg(), BadEE())
    except EngineError as exc:
        assert 'AOI geometry creation' in str(exc)
        assert 'mock geometry failure' not in str(exc)
    else:
        raise AssertionError('Expected failure')
