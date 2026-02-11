# Scrapping Library Documentation

Welcome to the documentation for the `scrapping` library. This is a config-driven scraping framework designed for data science teams.

## Guides and Reference

- **[Config Schema](./config_schema.md)**: Detailed explanation of all fields in the JSON configuration files.
- **[Notebook Series](../notebooks/README.md)**: Interactive deep dives into each engine and real-world scraping strategies.
    - [HTTP Engine Deep Dive](../notebooks/03_http_engine_cases.ipynb)
    - [Browser Engine Deep Dive](../notebooks/04_browser_engine_cases.ipynb)
    - [Hybrid Engine Deep Dive](../notebooks/05_hybrid_engine_cases.ipynb)
- **[Engines Reference](./engines.md)**: Comprehensive guide to all engine options and resilience features.
- **[Scheduling & Planning](../README.md#core-commands)**: How to use the `plan` command and interval/cron schedules.
- **[Migrations](../README.md#adding-a-new-source)**: How configs evolve between versions.

## Developer Scripts
We provide scripts to help with development and debugging:
- `scripts/golden_run_offline.py`: Runs a simulated scrape using local fixtures to ensure the framework is working correctly.
- `scripts/inspect_run.py`: Provides a clean summary of any run result directory.

## Troubleshooting
- **Playwright issues**: Run `scrap doctor` to check for missing browser binaries.
- **Blocked pages**: Check logs for "Matched block pattern" and consider switching engines.
- **Empty items**: Verify your CSS/XPath selectors using the walkthrough notebook.
