import json
import pytest
from pathlib import Path
from scrapping.recipes.jobs_aggregator import (
    run_jobs_recipe,
    JobSourceConfig,
    DiscoverListingPagesPhase,
    JobRecipeContext
)
from scrapping.recipes.core.state import StateManager
from unittest.mock import MagicMock

def test_jobs_item_schema_validation():
    from scrapping.schemas.job_items import JobPostItem

    # Valid
    item = JobPostItem(
        source_id="test",
        url="https://example.com/job1",
        title="Software Engineer",
        company="Tech Inc",
        location="USA",
        description="We need a developer with 5 years experience..."
    )
    assert item.title == "Software Engineer"

    # Invalid title
    with pytest.raises(ValueError):
        JobPostItem(
            source_id="test",
            url="https://example.com/job1",
            title="SE",
            company="Tech Inc",
            location="USA",
            description="We need a developer..."
        )

def test_discover_listing_pages_logic():
    cfg = JobSourceConfig(
        source_id="test",
        entrypoints=[{
            "url": "https://example.com/p={page}",
            "paging": {"pages": 3}
        }]
    )
    state = StateManager(output_dir="tmp")
    ctx = JobRecipeContext(engine=MagicMock(), state=state, config=cfg, online=False, log=MagicMock(), metadata={})

    phase = DiscoverListingPagesPhase()
    res = phase.run(ctx)

    assert res["urls_count"] == 3
    assert "https://example.com/p=1" in state.metadata["listing_urls"]
    assert "https://example.com/p=3" in state.metadata["listing_urls"]

def test_jobs_recipe_offline(tmp_path):
    output_root = tmp_path / "jobs_out"
    config = JobSourceConfig(
        source_id="source1",
        entrypoints=[{"url": "https://example.com/jobs"}],
        discovery={"link_extract": {"method": "regex", "pattern": "/job/\\d+"}},
        parsing={"item_extract": {"fields": {"description": {"selector": ".description"}}}}
    )

    run_jobs_recipe(
        source_configs=[config],
        output_root=str(output_root),
        online=False
    )

    assert (output_root / "source1" / "jobs.jsonl").exists()
    assert (output_root / "jobs_tracking.json").exists()

    with open(output_root / "source1" / "jobs.jsonl") as f:
        item = json.loads(f.readline())
        assert item["source_id"] == "source1"
        assert "Software Engineer" in item["title"]
