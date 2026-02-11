import json
from pathlib import Path
from scrapping.recipes.alibaba_l3 import run_l3_batch, AlibabaConfig

def test_run_l3_batch_tracking(tmp_path):
    batch_json = tmp_path / "batch.json"
    with open(batch_json, "w") as f:
        json.dump({"keywords": ["k1", "k2"]}, f)

    base_dir = tmp_path / "results"
    base_dir.mkdir()

    config = AlibabaConfig(max_pages=1)
    run_l3_batch(str(batch_json), str(base_dir), config=config, online=False)

    tracking_path = base_dir / "l3_tracking.json"
    assert tracking_path.exists()
    with open(tracking_path) as f:
        data = json.load(f)
        assert "items" in data
        assert "k1" in data["items"]
        assert data["items"]["k1"]["status"] == "success"
        assert "k2" in data["items"]
        assert data["items"]["k2"]["status"] == "success"
