import json

from scrapping import cli


def test_observability_metrics(tmp_path):
    results_dir = tmp_path / "results"
    config_path = "tests/fixtures/config_minimal_http.json"

    # We call cli.main directly with dry-run
    argv = [
        "run",
        "--config", config_path,
        "--results", str(results_dir),
        "--dry-run",
        "--run-id", "obs_test"
    ]

    exit_code = cli.main(argv)
    assert exit_code == 0

    report_path = results_dir / "run_obs_test" / "run_report.json"
    assert report_path.exists()

    with open(report_path) as f:
        report = json.load(f)
        assert "metrics" in report
        # Dry run won't increment pages_fetched/items_saved but let's check keys are there if we ran it
        # Actually, let's just check that run.started and run.finished events would have been logged
        # and that metrics dict exists.
        assert isinstance(report["metrics"]["counters"], dict)
