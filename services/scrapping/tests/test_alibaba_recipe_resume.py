import json
from pathlib import Path
from scrapping.recipes.core.state import StateManager

def test_alibaba_state_save_load(tmp_path):
    output_dir = str(tmp_path)
    state = StateManager(output_dir=output_dir, phase="links")
    state.processed_urls = ["link1", "link2"]
    state.save()

    loaded = StateManager.load(output_dir)
    assert loaded.phase == "links"
    assert loaded.processed_urls == ["link1", "link2"]

def test_alibaba_state_resume_logic(tmp_path):
    output_dir = str(tmp_path)
    state = StateManager(output_dir=output_dir, phase="products")
    state.processed_urls = ["L1", "L2", "L3"]
    state.metadata["completed_links"] = ["L1"]
    state.save()

    loaded = StateManager.load(output_dir)
    completed = set(loaded.metadata.get("completed_links", []))
    remaining = [l for l in loaded.processed_urls if l not in completed]
    assert remaining == ["L2", "L3"]
