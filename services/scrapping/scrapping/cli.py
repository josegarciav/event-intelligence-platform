#!/usr/bin/env python3
"""Command-line interface for the Scrapping library.

Commands:
  - scrap run       : Run scraping pipeline(s) for configured sources
  - scrap validate  : Validate config files (schema + sanity checks)
  - scrap doctor    : Check environment readiness (deps, browser install hints)

Typical usage:
  python cli.py run --config config.json --results results
  python cli.py validate --config config.json
  python cli.py doctor
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="scrap", description="Scrapping Library CLI")
    p.add_argument("--version", action="store_true", help="Print version and exit")
    sub = p.add_subparsers(dest="cmd")

    # run
    pr = sub.add_parser("run", help="Run scraping pipeline")
    pr.add_argument("--config", "-c", required=True, help="Path to JSON config (single file)")
    pr.add_argument("--results", "-o", default="results", help="Results output directory")
    pr.add_argument(
        "--parallelism", "-p", type=int, default=16, help="Parallelism for fetch/detail"
    )
    pr.add_argument("--only", nargs="*", default=None, help="Run only these source_ids")
    pr.add_argument("--json-logs", action="store_true", help="Emit JSON logs")
    pr.add_argument(
        "--strict",
        action="store_true",
        help="Fail if optional deps are missing for requested outputs",
    )
    pr.add_argument(
        "--items-format",
        default=None,
        choices=["jsonl", "csv", "parquet"],
        help="Override items output format",
    )
    pr.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not fetch; only validate+plan (no network calls)",
    )
    pr.add_argument(
        "--run-id",
        default=None,
        help="Override run_id (useful for tests/reproducibility)",
    )

    # validate
    pv = sub.add_parser("validate", help="Validate config file(s)")
    pv.add_argument("--config", "-c", required=True, help="Path to JSON config")
    pv.add_argument("--verbose", "-v", action="store_true", help="Print parsed config summary")

    # doctor
    pd = sub.add_parser("doctor", help="Check environment readiness")
    pd.add_argument("--verbose", "-v", action="store_true", help="Print extra diagnostics")

    # plan
    pp = sub.add_parser("plan", help="Show scraping plan (schedules) without running")
    pp.add_argument("--config", "-c", required=True, help="Path to JSON config")

    # recipe
    pre = sub.add_parser("recipe", help="Run a recipe")
    pre.add_argument("recipe_name", help="Name of the recipe (e.g., alibaba, jobs)")
    pre.add_argument("--config", "-c", required=True, help="Path to recipe config JSON")
    pre.add_argument(
        "--keyword",
        "-k",
        required=False,
        help="Keyword to scrape (for keyword-based recipes)",
    )
    pre.add_argument("--results", "-o", default=None, help="Output directory")
    pre.add_argument("--online", action="store_true", help="Run in online mode")
    pre.add_argument("--headed", action="store_true", help="Run with headed browser")
    pre.add_argument("--only", help="Comma-separated source IDs to run (for multi-source recipes)")
    pre.add_argument("--max-pages", type=int, help="Override max pages")
    pre.add_argument("--max-items", type=int, help="Override max items")

    # recipe-batch
    preb = sub.add_parser("recipe-batch", help="Run a batch recipe")
    preb.add_argument("recipe_name", help="Name of the recipe (e.g., alibaba)")
    preb.add_argument("--config", "-c", required=True, help="Path to recipe config JSON")
    preb.add_argument("--l3-json", required=True, help="Path to keywords JSON")
    preb.add_argument("--results", "-o", default="results/recipe_batch", help="Output directory")
    preb.add_argument("--online", action="store_true", help="Run in online mode")
    preb.add_argument("--start-from", type=int, default=0, help="Start from index")

    # capture-fixture
    pcf = sub.add_parser("capture-fixture", help="Fetch a URL and save HTML as fixture")
    pcf.add_argument("--url", required=True, help="URL to fetch")
    pcf.add_argument("--engine", choices=["http", "browser"], default="http", help="Engine to use")
    pcf.add_argument(
        "--out", required=True, help="Output path (e.g., tests/fixtures/html/test.html)"
    )
    pcf.add_argument(
        "--save-artifacts",
        action="store_true",
        help="Save browser screenshots/traces if using browser engine",
    )

    # scaffold-test
    pst = sub.add_parser("scaffold-test", help="Generate a regression test for a fixture")
    pst.add_argument("--fixture", required=True, help="Path to the HTML fixture")
    pst.add_argument(
        "--extract",
        choices=["css", "regex"],
        default="css",
        help="Extraction method to test",
    )
    pst.add_argument("--pattern", required=True, help="CSS selector or Regex pattern")
    pst.add_argument("--expect-count", type=int, default=1, help="Expected number of links")
    pst.add_argument("--out", help="Output test file path (default: tests/test_autogen.py)")

    return p.parse_args(argv)


def _read_json(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI with the given arguments."""
    try:
        return _main_impl(argv)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in config: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _main_impl(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.version:
        from scrapping import __version__

        print(f"scrapping version {__version__}")
        return 0

    if not args.cmd:
        print("Error: Command required. Use --help for usage info.", file=sys.stderr)
        return 1

    if args.cmd == "plan":
        import time

        from scrapping.scheduling.schedule import next_run_times, parse_schedule

        cfg = _read_json(args.config)
        sources = cfg.get("sources") or []
        if not isinstance(sources, list):
            sources = [sources]

        print(f"{'SOURCE ID':<20} {'SCHEDULE':<20} {'NEXT RUNS'}")
        print("-" * 60)

        now = time.time()
        for s in sources:
            sid = s.get("source_id", "unknown")
            sched_spec = s.get("schedule") or {}
            sched = parse_schedule(sched_spec)

            if not sched:
                print(f"{sid:<20} {'no schedule':<20}")
                continue

            next_times = next_run_times(sched, now, n=3)
            next_str = ", ".join(t.strftime("%Y-%m-%d %H:%M") for t in next_times)
            print(f"{sid:<20} {sched.summary():<20} {next_str}")

        return 0

    if args.cmd == "doctor":
        from scrapping.orchestrator import doctor_environment

        report = doctor_environment(verbose=bool(args.verbose))
        # Pretty print
        print(json.dumps(report, indent=2, ensure_ascii=False))
        # exit non-zero if hard failures exist
        return 0 if report.get("ok", False) else 1

    if args.cmd == "validate":
        from scrapping.config.migration import migrate_config
        from scrapping.orchestrator import validate_config

        cfg = _read_json(args.config)

        # Report version before migration
        if isinstance(cfg, dict):
            sources = cfg.get("sources")
            if isinstance(sources, list) and sources:
                v = sources[0].get("config_version", 0)
            else:
                v = cfg.get("config_version", 0)
            print(f"Detected config version: {v}")

        cfg_migrated, was_migrated = migrate_config(cfg)
        if was_migrated:
            print("Migration applied to version 1.")

        result = validate_config(cfg_migrated, verbose=bool(args.verbose))

        ok = result.get("ok", False)
        if ok:
            print("Config is VALID.")
            if args.verbose:
                print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("Config is INVALID. Issues found:", file=sys.stderr)
            for issue in result.get("issues", []):
                lvl = issue.get("level", "error").upper()
                msg = issue.get("msg")
                code = issue.get("code")
                print(f"  - [{lvl}] {code}: {msg}", file=sys.stderr)

        return 0 if ok else 2

    if args.cmd == "recipe":
        print(f"Unknown recipe: {args.recipe_name}", file=sys.stderr)
        print("No built-in recipes are currently registered.", file=sys.stderr)
        return 1

    if args.cmd == "recipe-batch":
        print(f"Unknown recipe: {args.recipe_name}", file=sys.stderr)
        print("No built-in recipes are currently registered.", file=sys.stderr)
        return 1

    if args.cmd == "capture-fixture":
        from scrapping.engines.browser import BrowserEngine, BrowserEngineOptions
        from scrapping.engines.http import HttpEngine

        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Capturing fixture from {args.url} using {args.engine} engine...")

        if args.engine == "browser":
            opts = BrowserEngineOptions(headless=True, save_artifacts=args.save_artifacts)
            engine = BrowserEngine(options=opts)
            res = engine.get_rendered(args.url)
            engine.close()
        else:
            engine = HttpEngine()
            res = engine.get(args.url)
            engine.close()

        if res.ok and res.text:
            out_path.write_text(res.text, encoding="utf-8")
            print(f"Fixture saved to {out_path} ({len(res.text)} bytes)")
            return 0
        else:
            print(f"Failed to capture fixture: {res.short_error()}", file=sys.stderr)
            return 1

    if args.cmd == "scaffold-test":
        fixture_path = Path(args.fixture)
        if not fixture_path.exists():
            print(f"Error: Fixture not found: {fixture_path}", file=sys.stderr)
            return 1

        test_name = f"test_extract_{fixture_path.stem}"
        out_path = args.out or f"tests/test_{fixture_path.stem}_gen.py"

        content = f"""import pytest
from pathlib import Path
from scrapping.extraction.link_extractors import LinkExtractRequest, extract_links

def {test_name}():
    fixture_path = Path("{fixture_path}")
    html = fixture_path.read_text(encoding="utf-8")
    req = LinkExtractRequest(
        html=html,
        method="{args.extract}",
        {"pattern" if args.extract == "regex" else "selector"}="{args.pattern}",
        base_url="https://example.com"
    )
    links = extract_links(req)
    assert len(links) == {args.expect_count}
    print(f"Found {{len(links)}} links as expected.")
"""
        Path(out_path).write_text(content, encoding="utf-8")
        print(f"Test scaffolded to {out_path}")
        return 0

    if args.cmd == "run":
        from scrapping.config.migration import migrate_config
        from scrapping.orchestrator import Orchestrator, OrchestratorOptions

        cfg = _read_json(args.config)
        cfg_migrated, _ = migrate_config(cfg)

        opts = OrchestratorOptions(
            results_dir=str(args.results),
            parallelism=int(args.parallelism),
            only_sources=args.only,
            json_logs=bool(args.json_logs),
            strict=bool(args.strict),
            items_format_override=args.items_format,
            dry_run=bool(args.dry_run),
            run_id_override=args.run_id,
        )

        orch = Orchestrator(options=opts)
        run_out = orch.run(cfg_migrated)

        # Print summary
        ok = run_out.get("ok", False)
        run_id = run_out.get("run_id")
        run_dir = run_out.get("run_dir")
        report_path = run_out.get("run_report_path")
        summary = run_out.get("summary")

        print("-" * 40)
        print(f"Run {'SUCCESSFUL' if ok else 'FAILED'}")
        print(f"Run ID:      {run_id}")
        print(f"Run Dir:     {run_dir}")
        print(f"Report:      {report_path}")
        if summary:
            print(f"Summary:     {json.dumps(summary)}")
        print("-" * 40)

        return 0 if ok else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
