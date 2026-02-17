import subprocess
import sys
from pathlib import Path


def test_golden_run_offline_smoke():
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "scripts" / "golden_run_offline.py"

    # Run the script
    res = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True)
    assert res.returncode == 0
    assert "Golden run successful!" in res.stdout

    # Check artifacts
    results_dir = repo_root / "results_golden_offline" / "run_golden_offline_001"
    assert (results_dir / "run_report.json").exists()
    assert (results_dir / "sources" / "naukrigulf" / "items" / "items_valid.jsonl").exists()


def test_inspect_run_smoke(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "scripts" / "inspect_run.py"

    # Create a fake run directory
    run_dir = tmp_path / "run_fake"
    run_dir.mkdir()
    report = {
        "run_id": "fake",
        "summary": {"sources_total": 1, "sources_ok": 1, "sources_failed": 0},
        "sources": [{"source_id": "src1", "ok": True, "stats": {"items_saved": 10}}],
    }
    with open(run_dir / "run_report.json", "w") as f:
        import json

        json.dump(report, f)

    # Run inspection
    res = subprocess.run(
        [sys.executable, str(script_path), "--run-dir", str(run_dir)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "RUN INSPECTION: fake" in res.stdout
    assert "src1" in res.stdout
    assert "Items Saved: 10" in res.stdout
