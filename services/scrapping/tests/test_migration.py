from scrapping.config.migration import migrate_config


def test_v0_to_v1_migration():
    old_cfg = {
        "source_id": "test_v0",
        "storage": {
            "items_format": "csv"
        }
    }

    new_cfg, was_migrated = migrate_config(old_cfg)

    assert was_migrated is True
    assert new_cfg["config_version"] == 1
    assert new_cfg["storage"]["items"]["format"] == "csv"
    assert "items_format" not in new_cfg["storage"]
    assert new_cfg["engine"]["type"] == "http"

def test_already_v1_migration():
    v1_cfg = {
        "source_id": "test_v1",
        "config_version": 1,
        "engine": {"type": "browser"}
    }

    new_cfg, was_migrated = migrate_config(v1_cfg)

    assert was_migrated is False
    assert new_cfg == v1_cfg

def test_multi_source_migration():
    cfg = {
        "sources": [
            {"source_id": "s1", "storage": {"items_format": "jsonl"}},
            {"source_id": "s2", "config_version": 1}
        ]
    }

    new_cfg, was_migrated = migrate_config(cfg)

    assert was_migrated is True
    assert new_cfg["sources"][0]["config_version"] == 1
    assert new_cfg["sources"][0]["storage"]["items"]["format"] == "jsonl"
    assert new_cfg["sources"][1]["config_version"] == 1 # Already was 1 but normalized
