import pytest
import logging
from unittest.mock import MagicMock, patch
from scrapping.recipes.alibaba_l3 import run_single_keyword, AlibabaConfig

# Patch where it is imported in the framework bits
@patch("scrapping.recipes.core.phases.emit_event")
@patch("scrapping.recipes.alibaba_l3.emit_event")
def test_alibaba_recipe_events(mock_emit_recipe, mock_emit_phases, tmp_path):
    output_dir = str(tmp_path)
    config = AlibabaConfig(max_pages=1)

    run_single_keyword(
        keyword="test",
        output_dir=output_dir,
        config=config,
        online=False
    )

    # Check if phase events were emitted
    emitted_phases = [call.args[1] for call in mock_emit_phases.call_args_list]
    assert "phase.started" in emitted_phases
    assert "phase.finished" in emitted_phases

    # Let's try with checkpoint_every_n=1
    config.checkpoint_every_n = 1
    # reset both
    mock_emit_recipe.reset_mock()
    mock_emit_phases.reset_mock()

    # We must ensure we are starting fresh (no state.json from previous run in same tmp_path)
    import shutil
    import os
    if os.path.exists(os.path.join(output_dir, "state.json")):
        os.remove(os.path.join(output_dir, "state.json"))

    run_single_keyword(
        keyword="test",
        output_dir=output_dir,
        config=config,
        online=False
    )
    emitted_recipe = [call.args[1] for call in mock_emit_recipe.call_args_list]
    assert "checkpoint.saved" in emitted_recipe

def test_recipe_results_contain_timings_and_counts(tmp_path):
    output_dir = str(tmp_path)
    config = AlibabaConfig(max_pages=1)

    results = run_single_keyword(
        keyword="test",
        output_dir=output_dir,
        config=config,
        online=False
    )

    for res in results:
        assert res.elapsed_ms >= 0
        assert isinstance(res.counts, dict)
        if res.name == "links":
            assert "links_found" in res.counts
