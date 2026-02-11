import json

from scrapping import cli


def test_cli_dry_run(tmp_path):
    results_dir = tmp_path / "results"
    config_path = "tests/fixtures/config_minimal_http.json"

    # We call cli.main directly
    run_id = "test_run_123"
    argv = [
        "run",
        "--config", config_path,
        "--results", str(results_dir),
        "--dry-run",
        "--run-id", run_id
    ]

    exit_code = cli.main(argv)
    assert exit_code == 0

    # Check if run directory was created
    run_dir = results_dir / f"run_{run_id}"
    assert run_dir.exists()

    # Check for report
    report_path = run_dir / "run_report.json"
    assert report_path.exists()

    with open(report_path) as f:
        report = json.load(f)
        assert report["summary"]["sources_total"] == 1
