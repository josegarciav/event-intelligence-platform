import json

from scrapping.orchestrator import validate_config


def test_validate_config_ok():
    with open("tests/fixtures/config_minimal_http.json") as f:
        cfg = json.load(f)
    result = validate_config(cfg)
    assert result["ok"] is True
    assert len(result["issues"]) == 0


def test_validate_config_fails_without_sources():
    cfg = {"sources": []}
    result = validate_config(cfg)
    assert result["ok"] is False
    assert any(i["code"] == "missing_sources" for i in result["issues"])


def test_validate_config_duplicate_source_id():
    cfg = {
        "sources": [
            {
                "source_id": "src1",
                "engine": {"type": "http"},
                "entrypoints": [{"url": "http://a"}],
            },
            {
                "source_id": "src1",
                "engine": {"type": "http"},
                "entrypoints": [{"url": "http://b"}],
            },
        ]
    }
    result = validate_config(cfg)
    assert result["ok"] is False
    assert any(i["code"] == "duplicate_source_id" for i in result["issues"])


def test_validate_config_warnings():
    # Broad regex
    cfg = {
        "sources": [
            {
                "source_id": "broad",
                "engine": {"type": "http"},
                "entrypoints": [{"url": "http://a"}],
                "discovery": {"link_extract": {"method": "regex", "pattern": ".*"}},
            }
        ]
    }
    res = validate_config(cfg)
    assert res["ok"] is True
    assert any(i["code"] == "broad_regex" for i in res["issues"])

    # SSL disabled
    cfg = {
        "sources": [
            {
                "source_id": "nossl",
                "engine": {"type": "http", "verify_ssl": False},
                "entrypoints": [{"url": "http://a"}],
                "discovery": {"link_extract": {"method": "regex", "pattern": "abc"}},
            }
        ]
    }
    res = validate_config(cfg)
    assert res["ok"] is True
    assert any(i["code"] == "ssl_disabled" for i in res["issues"])
