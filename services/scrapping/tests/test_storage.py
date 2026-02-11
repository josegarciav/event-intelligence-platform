from pathlib import Path

from scrapping.storage.layouts import Layout, _safe_name


def test_layout_paths():
    root = Path("results")
    layout = Layout(root=root)
    run_id = "20260101_120000"

    assert layout.run_dir(run_id) == root / f"run_{run_id}"
    assert (
        layout.source_dir(run_id, "example.com")
        == root / f"run_{run_id}" / "sources" / "example.com"
    )
    assert layout.run_meta_path(run_id) == root / f"run_{run_id}" / "run_meta.json"


def test_safe_name():
    assert _safe_name("example.com") == "example.com"
    assert _safe_name("My Source!") == "My_Source_"
    assert _safe_name("   ") == "unknown_source"
    assert _safe_name(None) == "unknown_source"
    assert _safe_name("a" * 200) == "a" * 120
