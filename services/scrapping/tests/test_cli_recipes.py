import pytest
import os
import shutil
from scrapping.cli import main

def test_cli_recipe_alibaba_offline(tmp_path):
    results_dir = tmp_path / "recipe_res"
    config_path = "examples/configs/real/alibaba/alibaba_single_keyword.json"

    # Run CLI
    argv = [
        "recipe", "alibaba",
        "--config", config_path,
        "--keyword", "test keyword",
        "--results", str(results_dir)
    ]

    # We need to set PYTHONPATH or ensure scrapping is importable
    # Here we just call main() directly in the same process
    ret = main(argv)
    assert ret == 0
    assert (results_dir / "products.jsonl").exists()

def test_cli_recipe_batch_alibaba_offline(tmp_path):
    results_dir = tmp_path / "batch_res"
    config_path = "examples/configs/real/alibaba/alibaba_single_keyword.json"
    l3_json = "examples/configs/real/alibaba/l3_hierarchy.json"

    argv = [
        "recipe-batch", "alibaba",
        "--config", config_path,
        "--l3-json", l3_json,
        "--results", str(results_dir)
    ]

    ret = main(argv)
    assert ret == 0
    assert (results_dir / "l3_tracking.json").exists()
