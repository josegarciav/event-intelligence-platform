# Changelog

## 0.1.1 (RC1) - 2026-02-03
### Added
- **Scheduling**: Meaningful interval and cron support in configs + `scrap plan` command.
- **Migrations**: Automated config transformation from v0 to v1.
- **Observability**: Structured run events (`run.started`, `source.done`) and labeled metrics.
- **Developer Experience**:
    - End-to-end walkthrough Jupyter notebook.
    - `scripts/golden_run_offline.py` for simulated runs.
    - `scripts/inspect_run.py` for result analysis.
    - Documentation hub in `docs/README.md`.
- **Validation**: New warnings for broad regex, missing Playwright, and disabled SSL.

### Changed
- CLI output is now more concise and readable.
- Integration tests are skipped by default unless `RUN_INTEGRATION=1`.

## 0.1.0 - 2026-01-31
### Added
- Initial MVP with HTTP, Browser, and Hybrid engines.
- Basic pipeline orchestration (discovery, extraction, QA, storage).
- CLI with `run`, `validate`, and `doctor`.
