import pytest
from unittest.mock import MagicMock
from scrapping.recipes.core.state import StateManager
from scrapping.recipes.alibaba_l3 import (
    SearchPhase,
    FiltersPhase,
    LinksPhase,
    RecipeContext,
    AlibabaConfig
)

def test_execute_phase_search_offline():
    state = StateManager(output_dir="tmp")
    engine = MagicMock()
    ctx = RecipeContext(keyword="test", engine=engine, state=state, config=AlibabaConfig(), online=False, log=MagicMock())

    phase = SearchPhase()
    res = phase.run(ctx)
    assert res["status"] == "skipped_offline"
    engine.get_rendered.assert_not_called()

def test_execute_phase_filters_offline(tmp_path):
    state = StateManager(output_dir=str(tmp_path))
    engine = MagicMock()
    ctx = RecipeContext(keyword="test", engine=engine, state=state, config=AlibabaConfig(), online=False, log=MagicMock())

    phase = FiltersPhase()
    phase.run(ctx)

    assert (tmp_path / "alibaba_filters.json").exists()
    assert (tmp_path / "alibaba_categories.json").exists()

def test_execute_phase_links_offline(tmp_path):
    state = StateManager(output_dir=str(tmp_path))
    engine = MagicMock()
    ctx = RecipeContext(keyword="test", engine=engine, state=state, config=AlibabaConfig(), online=False, log=MagicMock())

    phase = LinksPhase()
    phase.run(ctx)

    assert len(state.processed_urls) > 0
    assert (tmp_path / "product_links.json").exists()
