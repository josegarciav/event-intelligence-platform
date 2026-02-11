# Notebooks

This directory contains interactive walkthroughs and deep dives into the `scrapping` library.

## Recommended Reading Order

For the best experience, we recommend following this path:
1. **00 → [Methodology & Capabilities]**: Start here to understand the framework and the **Hard Targets Diagnostics Lab**.
2. **01 → [End-to-End Walkthrough]**: See the library in action.
3. **02 → [Online Playbook]**: Learn how to build your first config.
4. **03-05 → [Engines In-Depth]**: Master HTTP, Browser, and Hybrid strategies.
5. **06-07 → [Operational Recipes]**: Learn production-grade recipes (Alibaba, Jobs).

## Available Notebooks

### Foundations
0. **[00_scrapping_capabilities_and_methodology.ipynb](./00_scrapping_capabilities_and_methodology.ipynb)**: Executive overview, the "Methodology Ladder", and a **Hard Targets / Diagnostics Lab**.

### Core Walkthroughs
1. **[01_end_to_end_walkthrough_example_multi_sources.ipynb](./01_end_to_end_walkthrough_example_multi_sources.ipynb)**: A comprehensive guide showing how the pipeline works from discovery to quality filtering.
2. **[02_online_scraping_playbook.ipynb](./02_online_scraping_playbook.ipynb)**: A developer-facing playbook for real online scraping, teaching how to build configs step-by-step.

### Engine In-Depth Series
3. **[03_http_engine_cases.ipynb](./03_http_engine_cases.ipynb)**: Detailed coverage of the HTTP engine (pagination, rate limits, retries).
4. **[04_browser_engine_cases.ipynb](./04_browser_engine_cases.ipynb)**: Deep dive into the Browser engine (JS rendering, actions, wait_for).
5. **[05_hybrid_engine_cases.ipynb](./05_hybrid_engine_cases.ipynb)**: Orchestrating mixed speed/accuracy strategies using the Hybrid engine.

### Operational Recipes
6. **[06_alibaba_l3_migration.ipynb](./06_alibaba_l3_migration.ipynb)**: Operational tutorial for the Alibaba L3 recipe, covering state management and resumability.
7. **[07_jobs_aggregator_recipe.ipynb](./07_jobs_aggregator_recipe.ipynb)**: Multi-source methodology for aggregating job posts across heterogeneous sites.

## How to Run

### 1. Prerequisites

Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -e ".[dev,browser,notebooks,all]"
playwright install
```

#### Linux/Colab Playwright Dependencies
If you are running on Linux (including Google Colab) and encounter errors about missing shared libraries (e.g., `libatk-1.0.so.0`), you need to install the system dependencies:
```bash
# Preferred (installs OS deps automatically)
playwright install --with-deps chromium

# Alternative (just the dependencies)
playwright install-deps chromium
```

### 2. Launch Jupyter

```bash
jupyter lab
```

### 3. Modes

- **Offline (Default)**: Uses fixtures in `tests/fixtures/html/`. No network required.
- **Online**: Set `ONLINE=1` for small, safe trials on stable public demo sites.
- **Hard Targets**: Set `HARD_TARGETS=1` along with `ONLINE=1` to run bot-detection diagnostics.

| Mode | Command | Expected Runtime |
| :--- | :--- | :--- |
| **Offline** | `jupyter lab` | < 1 minute |
| **Online** | `ONLINE=1 jupyter lab` | 2-5 minutes |
| **Hard Targets** | `ONLINE=1 HARD_TARGETS=1 jupyter lab` | 5-10 minutes |
