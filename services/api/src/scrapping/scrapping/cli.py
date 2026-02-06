#!/usr/bin/env python3
"""
cli.py

Command-line interface for the Scrapping library.

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
from pathlib import Path
from typing import Any, Dict, Optional


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="scrap", description="Scrapping Library CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    # run
    pr = sub.add_parser("run", help="Run scraping pipeline")
    pr.add_argument(
        "--config", "-c", required=True, help="Path to JSON config (single file)"
    )
    pr.add_argument(
        "--results", "-o", default="results", help="Results output directory"
    )
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

    # validate
    pv = sub.add_parser("validate", help="Validate config file(s)")
    pv.add_argument("--config", "-c", required=True, help="Path to JSON config")
    pv.add_argument(
        "--verbose", "-v", action="store_true", help="Print parsed config summary"
    )

    # doctor
    pd = sub.add_parser("doctor", help="Check environment readiness")
    pd.add_argument(
        "--verbose", "-v", action="store_true", help="Print extra diagnostics"
    )

    return p.parse_args(argv)


def _read_json(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)

    if args.cmd == "doctor":
        from scrapping.orchestrator import doctor_environment

        report = doctor_environment(verbose=bool(args.verbose))
        # Pretty print
        print(json.dumps(report, indent=2, ensure_ascii=False))
        # exit non-zero if hard failures exist
        return 0 if report.get("ok", False) else 1

    if args.cmd == "validate":
        from scrapping.orchestrator import validate_config

        cfg = _read_json(args.config)
        result = validate_config(cfg, verbose=bool(args.verbose))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok", False) else 2

    if args.cmd == "run":
        from scrapping.orchestrator import Orchestrator, OrchestratorOptions

        cfg = _read_json(args.config)

        opts = OrchestratorOptions(
            results_dir=str(args.results),
            parallelism=int(args.parallelism),
            only_sources=args.only,
            json_logs=bool(args.json_logs),
            strict=bool(args.strict),
            items_format_override=args.items_format,
            dry_run=bool(args.dry_run),
        )

        orch = Orchestrator(options=opts)
        run_out = orch.run(cfg)

        # Print final run report path + summary
        print(
            json.dumps(
                {
                    "ok": run_out.get("ok", False),
                    "run_id": run_out.get("run_id"),
                    "run_dir": run_out.get("run_dir"),
                    "run_report_path": run_out.get("run_report_path"),
                    "summary": run_out.get("summary"),
                },
                indent=2,
                ensure_ascii=False,
            )
        )

        return 0 if run_out.get("ok", False) else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
