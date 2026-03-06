# Agent Architecture — Pulsecity Event Intelligence Platform

---

## Overview

Pulsecity uses LLMs as data operators, not assistants.
After ingestion, a sequential chain of five specialized agents reads each event through MCP, reasons over its fields, and writes structured intelligence back into the event record.
All reads and writes are mediated by the MCP layer — agents never touch the database directly.
All outputs are schema-constrained; free-text hallucinations cannot enter production data.
Non-LLM enrichment (e.g. MusicBrainz artist genre lookup) runs as a post-LLM phase inside the relevant agent rather than as a separate chain entry.

---

## System Architecture

```
Ingested Events (PostgreSQL)
          │
          ▼
PostIngestionTrigger
(services/api/src/agents/orchestration/pipeline_triggers.py)
          │
          ▼
BatchEnrichmentRunner
(services/api/src/agents/orchestration/agent_runner.py)
          │
          ├─ [1] FeatureAlignmentAgent
          ├─ [2] TaxonomyClassifierAgent
          ├─ [3] EmotionMapperAgent
          ├─ [4] DataQualityAgent
          └─ [5] DeduplicationAgent
                    │
                    ▼
          MCP Layer (read · validate · write)
                    │
                    ▼
          Enriched EventSchema
          (PostgreSQL · FastAPI)
```

---

## The Agent Chain

Agents run in fixed order. Each agent receives the events enriched by all previous agents.
Configuration lives in `services/api/src/configs/agents.yaml`.

| # | Agent                   | Config key            | Prompt                  | Target Fields                                                                                     |
|---|-------------------------|-----------------------|-------------------------|---------------------------------------------------------------------------------------------------|
| 1 | FeatureAlignmentAgent   | `feature_alignment`   | `feature_alignment`     | event_type, tags, format, price.{is_free, currency_code, minimum_price, maximum_price, early_bird_price, standard_price, vip_price, price_raw_text}, artists[*].genre — LLM batch pass; then MusicBrainz HTTP pass for artist genre (fill-null-only, no LLM) |
| 2 | TaxonomyClassifierAgent | `taxonomy_classifier` | `taxonomy_classifier`   | primary_category, subcategory, subcategory_name, activity_id, activity_name, energy_level, social_intensity, cognitive_load, physical_involvement, repeatability, unconstrained_primary_category, unconstrained_subcategory, unconstrained_activity — **two-pass RAG**: pass 1 classifies category/subcategory/dims; pass 2 retrieves activities from taxonomy JSON and picks best activity_id per event |
| 3 | EmotionMapperAgent      | `emotion_mapper`      | `emotion_mapper`        | emotional_output, cost_level, environment, risk_level, age_accessibility, time_scale              |
| 4 | DataQualityAgent        | `data_quality`        | `data_quality`          | data_quality_score                                                                                |
| 5 | DeduplicationAgent      | `deduplication`       | `deduplication`         | duplicate_group_id, group_type, is_primary, duplicate_of, similarity_score, reason, is_recurring, recurrence_pattern — **two-pass**: rule-based exact match (always) + LLM fuzzy grouping (when available); recurring groups set `is_recurring=True` and `recurrence_pattern` directly on EventSchema |

---

## MCP Layer

All agent reads and writes go through MCP. Three modes implement the same `MCPClient` abstract interface.

| Mode     | Class              | Transport                  | Use case                                     |
|----------|--------------------|----------------------------|----------------------------------------------|
| `local`  | `LocalMCPClient`   | FastMCP in-process         | **Default** — no network, same process       |
| `server` | `ServerMCPClient`  | FastMCP HTTP SSE           | Production — separate service                |
| `direct` | `DirectMCPClient`  | In-memory Python           | Legacy — no FastMCP dependency               |

Switch modes in `services/api/src/configs/agents.yaml`:

```yaml
global:
  mcp_mode: "local"    # or "server" | "direct"
  mcp_server:
    url: "http://localhost:8001"
```

Start the FastMCP server for `server` mode:

```bash
python -m src.agents.mcp.fastmcp_server --host localhost --port 8001
```

---

## LLM Providers

| Provider    | Config key    | Structured Output   | Setup                                    |
|-------------|---------------|---------------------|------------------------------------------|
| `ollama`    | `"ollama"`    | Instructor JSON     | `brew install ollama && ollama pull llama3.2:1b` |
| `anthropic` | `"anthropic"` | tool_use            | `ANTHROPIC_API_KEY` env var              |
| `openai`    | `"openai"`    | Instructor TOOLS    | `OPENAI_API_KEY` env var                 |

Default is `ollama` with `llama3.2:1b` — no API key or network required.

Switch any agent by editing `provider` and `model` in `services/api/src/configs/agents.yaml`:

```yaml
agents:
  feature_alignment:
    provider: "anthropic"
    model: "claude-sonnet-4-6"
```

---

## Running Enrichment

**Post-ingestion (production entry point):**

```python
from src.agents.orchestration.pipeline_triggers import load_agents_config, PostIngestionTrigger

agents_config = load_agents_config()
trigger = PostIngestionTrigger(agents_config)
enrichment_result = await trigger.on_pipeline_complete(pipeline_result)
```

**Direct batch run:**

```python
from src.agents.orchestration.agent_runner import BatchEnrichmentRunner

runner = BatchEnrichmentRunner(agents_config)
result = await runner.run(events, prompt_version="active")
```

---

## Prompt System

Each agent uses a named prompt loaded from `services/api/src/agents/prompts/{name}/`.

```
prompts/
├── feature_alignment/
│   ├── manifest.yaml    # declares active_version + per-version metadata
│   └── v1.yaml          # Jinja2 system + user prompt templates
├── taxonomy_classifier/
├── emotion_mapper/
├── data_quality/
└── deduplication/
```

`PromptRegistry` resolves the active version and renders both prompts:

```python
from src.agents.registry.prompt_registry import get_prompt_registry

registry = get_prompt_registry()
system, user = registry.render("feature_alignment", variables={"title": "Techno Night"})
```

All calls are logged with `{agent_name, prompt_name, version, event_id}` for auditability.

---

## Validation

`SchemaValidator.validate_event(event)` checks all taxonomy enum fields against the data contract defined in `services/api/src/assets/data_contract.yaml`.

`compute_confidence_score(event)` scores field completeness (60%) + agent confidence (40%).

Events below `global.confidence_threshold` (0.6, set in `agents.yaml`) are flagged via `flag_low_confidence()`.

---

## Agent Status

| Agent                   | File                                          | Status  | Prompt                  | Notes |
|-------------------------|-----------------------------------------------|---------|-------------------------|-------|
| FeatureAlignmentAgent   | `enrichment/feature_alignment_agent.py`       | Live    | `feature_alignment`     | LLM fills event_type/tags/format/pricing; MusicBrainz pass fills artists[*].genre |
| TaxonomyClassifierAgent | `enrichment/taxonomy_classifier_agent.py`     | Live    | `taxonomy_classifier`   | |
| EmotionMapperAgent      | `enrichment/emotion_mapper_agent.py`          | Live    | `emotion_mapper`        | |
| DataQualityAgent        | `enrichment/data_quality_agent.py`            | Live    | `data_quality`          | |
| DeduplicationAgent      | `enrichment/deduplication_agent.py`           | Live    | `deduplication`         | Sets is_recurring + recurrence_pattern on recurring groups |

---

## Key Files Reference

| Path                                                                 | Description                                        |
|----------------------------------------------------------------------|----------------------------------------------------|
| `services/api/src/configs/agents.yaml`                               | Agent chain config, providers, MCP mode            |
| `services/api/src/agents/orchestration/pipeline_triggers.py`         | `PostIngestionTrigger`, `load_agents_config()`     |
| `services/api/src/agents/orchestration/agent_runner.py`              | `BatchEnrichmentRunner` — ordered chain executor   |
| `services/api/src/agents/base/base_agent.py`                         | Abstract `BaseAgent` with `async run()` interface  |
| `services/api/src/agents/base/task.py`                               | `AgentTask` and `AgentResult` dataclasses          |
| `services/api/src/agents/base/output_models.py`                      | Pydantic extraction schemas                        |
| `services/api/src/agents/mcp/mcp_client.py`                          | `MCPClient` abstract + all three implementations   |
| `services/api/src/agents/mcp/readers.py`                             | MCP read tools (fetch_event_row, etc.)             |
| `services/api/src/agents/mcp/writers.py`                             | MCP write tools (write_features, etc.)             |
| `services/api/src/agents/llm/provider_router.py`                     | `get_llm_client()` factory                         |
| `services/api/src/agents/registry/prompt_registry.py`                | Loads manifests, renders Jinja2 templates          |
| `services/api/src/agents/registry/agent_registry.py`                 | Maps agent name → class for orchestrator           |
| `services/api/src/agents/validation/schema_validator.py`             | Validates against data contract + enums            |
| `services/api/src/agents/validation/confidence.py`                   | Per-field + overall confidence scoring             |
| `services/api/src/assets/data_contract.yaml`                         | Canonical field definitions and enum constraints   |
