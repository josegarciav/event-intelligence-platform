import json
import os

import pytest

from scrapping import cli


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("RUN_INTEGRATION") != "1", reason="RUN_INTEGRATION=1 not set")
def test_run_example_com(tmp_path):
    results_dir = tmp_path / "results"
    config_path = "tests/fixtures/config_minimal_http.json"

    argv = [
        "run",
        "--config", config_path,
        "--results", str(results_dir)
    ]

    exit_code = cli.main(argv)
    assert exit_code == 0

    # Check if run directory was created
    runs = list(results_dir.glob("run_*"))
    assert len(runs) == 1
    run_dir = runs[0]

    # Check for report
    report_path = run_dir / "run_report.json"
    assert report_path.exists()

    # Check for links file
    links_path = run_dir / "sources" / "example_com" / "links" / "extracted_links.jsonl"
    assert links_path.exists()

    with open(report_path) as f:
        report = json.load(f)
        assert report["summary"]["sources_total"] == 1
        assert report["summary"]["sources_ok"] == 1
