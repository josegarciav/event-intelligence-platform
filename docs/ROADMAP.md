# MCP & Agent Intelligence Roadmap
### Internal Data Workforce Architecture

---

# 1. Strategic Framing

Pulsecity does not use LLMs as assistants.

Pulsecity uses LLMs as data operators.

They read, reason, enrich, validate, and write intelligence back into the system through controlled interfaces.

The backbone of this system is MCP.

---

# 2. Internal Motto

> Data is our moat.
> Design like we are right.
> Test like we are wrong.

Implications:

- All enrichment must be traceable
- All writes must be schema-constrained
- All reasoning must be auditable
- All outputs must be testable

No free-text hallucinated intelligence enters production datasets.

---

# 3. MCP as the Intelligence Spine

LLMs never interact directly with databases.

All read/write operations are mediated through MCP servers.

---

## Architecture Flow

```

Event Record
↓
Agent Task Trigger
↓
MCP Request
↓
LLM Provider
↓
Structured Output
↓
Validation Layer
↓
Database Write (via MCP)

```

---

# 4. MCP Server Responsibilities

## Read Interfaces

- Fetch raw event rows
- Retrieve compressed HTML
- Access enrichment gaps
- Pull taxonomy enums
- Retrieve artist metadata

---

## Write Interfaces

- Feature enrichment fields
- Taxonomy classifications
- Emotion tags
- Artist mappings
- Normalization annotations

---

## Guardrails

- Schema validation
- Enum enforcement
- Type checking
- Confidence thresholds
- Write audit logs

---

# 5. Agent Classes

Agents are task-specific intelligence workers.

They do not own providers.

They operate through MCP + LLM abstractions.

---

## Core Agent Types

### Feature Alignment Agent
Extract structured features from:

- Descriptions (if missing)
- HTML -> enriching/validating other fields
- Metadata -> logging of the normalization done and handling of this enrichment -> log into table

---

### Taxonomy Agent
Maps events into:

- Experience categories
- Sub-genres
- Cultural classifications

---

### Emotion & Vibe Agent
Infers:

- Emotional & tag outputs
- Energy levels
- Social/Artist context

---

### Data Quality Agent
Audits:

- Missing fields
- Inconsistent taxonomy
- Confidence score computation

---

### Anti Duplication Agent
Audits:

- Subtly duplicated events
- Groups recurring events (Some events happen every hour like a show at a museum, these should be grouped in the app)

---

# 6. Provider Abstraction

Providers plug into MCP workflows.

Swappable without agent refactors.

```

OpenAI
Claude
Local models (llama)
Future OSS providers

```

---

# 7. src/agents/ — Implemented File Architecture

```
src/agents/
├── __init__.py
├── taxonomy_retriever.py                 (singleton taxonomy context loader)
│
├── base/
│   ├── __init__.py
│   ├── base_agent.py                     (abstract BaseAgent with async run() interface)
│   ├── task.py                           (AgentTask + AgentResult dataclasses)
│   └── output_models.py                  (Pydantic extraction schemas)
│
├── llm/
│   ├── __init__.py
│   ├── base_llm_client.py                (abstract async interface)
│   ├── openai_client.py                  (OpenAI via Instructor)
│   ├── anthropic_client.py               (Claude via Anthropic SDK + tool_use)
│   └── provider_router.py                (get_llm_client factory)
│
├── mcp/                                  (local — in-process FastMCP, default; server — production path; direct — legacy)
│   ├── __init__.py
│   ├── mcp_client.py                     (MCPClient abstract + DirectMCPClient)
│   ├── readers.py                        (fetch_event_row, fetch_missing_features)
│   └── writers.py                        (write_features, write_taxonomy, write_emotions, write_tags)
│
├── enrichment/
│   ├── __init__.py
│   ├── feature_alignment_agent.py        (event_type, tags, event_format)
│   ├── taxonomy_classifier_agent.py      (primary_category, subcategory, behavioral dims)
│   ├── emotion_mapper_agent.py           (emotional_output, cost_level, environment, etc.)
│   ├── data_quality_agent.py             (quality_score, normalization_errors)
│   └── artist_enricher_agent.py          (STUB — requires external artist metadata API)
│
├── validation/
│   ├── __init__.py
│   ├── schema_validator.py               (validates against data contract + enums)
│   └── confidence.py                     (per-field + overall confidence scoring)
│
├── orchestration/
│   ├── __init__.py
│   ├── agent_runner.py                   (BatchEnrichmentRunner — ordered chain)
│   └── pipeline_triggers.py              (PostIngestionTrigger + load_agents_config)
│
├── prompts/
│   ├── core_metadata/                    (v1.yaml — event_type, tags, event_format)
│   ├── experience_pulse/                 (v1.yaml — behavioral taxonomy dimensions)
│   ├── logistics/                        (v1.yaml — environment, cost, risk, age)
│   ├── taxonomy_classification/          (v1.yaml — full taxonomy classification)
│   ├── emotion_vibe/                     (v1.yaml — emotional outputs + vibe dims)
│   └── data_quality/                     (v1.yaml — completeness audit)
│
└── registry/
    ├── __init__.py
    ├── prompt_registry.py                (loads manifests, renders Jinja2 templates)
    └── agent_registry.py                 (maps agent name → class for orchestrator)
```

---

## Agent Current Status

| Agent | File | Status | Prompt | Target Fields |
|---|---|---|---|---|
| FeatureAlignmentAgent | `enrichment/feature_alignment_agent.py` | **Live** | `core_metadata` | event_type, tags, event_format |
| TaxonomyClassifierAgent | `enrichment/taxonomy_classifier_agent.py` | **Live** | `taxonomy_classification` | primary_category, subcategory, behavioral dims |
| EmotionMapperAgent | `enrichment/emotion_mapper_agent.py` | **Live** | `emotion_vibe` | emotional_output, cost_level, environment, etc. |
| DataQualityAgent | `enrichment/data_quality_agent.py` | **Live** | `data_quality` | quality_score, normalization_errors |
| DeduplicationAgent | `enrichment/deduplication_agent.py` | **Live** | `deduplication` | duplicate_group_id, duplicate_group_type, is_primary, duplicate_of, similarity_score |
| ArtistEnricherAgent | `enrichment/artist_enricher_agent.py` | **Stub** | — | artists (requires external API) |
| MCP layer | `mcp/mcp_client.py` | **Stub** (in-memory) | — | All fields via DirectMCPClient |
| FastMCP server | — | **Future** | — | Replace DirectMCPClient when deployed |

---

## Prompt Versioning

Prompts live in `src/agents/prompts/{name}/`:
- `manifest.yaml` — declares `active_version` + per-version metadata
- `v1.yaml` — Jinja2 system + user prompt templates

`PromptRegistry.render("core_metadata", version="active", variables={...})` resolves the active version and renders both prompts. All calls are logged with `{agent_name, prompt_name, version, event_id}`.

---

## Entry Points

```python
# Load config
from src.agents.orchestration.pipeline_triggers import load_agents_config, PostIngestionTrigger
agents_config = load_agents_config()

# Post-ingestion enrichment
trigger = PostIngestionTrigger(agents_config)
enrichment_result = await trigger.on_pipeline_complete(gyg_result)

# Direct batch run
from src.agents.orchestration.agent_runner import BatchEnrichmentRunner
runner = BatchEnrichmentRunner(agents_config)
result = await runner.run(events, prompt_version="active")

# Prompt testing
from src.agents.registry.prompt_registry import get_prompt_registry
registry = get_prompt_registry()
system, user = registry.render("core_metadata", variables={"title": "Techno Night"})

# MCP client — local mode (in-process FastMCP, no network)
from src.agents.mcp import create_mcp_client
client = create_mcp_client("local", events=pipeline_result.events)
row = await client.read("fetch_event_row", {"event_id": "abc123"})

# MCP client — server mode (FastMCP HTTP; start server first)
# python -m src.agents.mcp.fastmcp_server --host localhost --port 8001
client = create_mcp_client("server", server_url="http://localhost:8001")
await client.load(events)

# Use Llama locally via Ollama
from src.agents.llm import get_llm_client
llm = get_llm_client("ollama", model_name="llama3.2:3b")
```

---

# 8. Base Layer

## `src/agents/base/base_agent.py`

Abstract `BaseAgent` with:
- `name: str` — unique agent identifier
- `prompt_name: str` — key into PromptRegistry
- `async run(task: AgentTask) -> AgentResult` — must be implemented by subclasses
- `_build_event_context(event)` — serializes EventSchema fields useful for LLM prompts

## `src/agents/base/task.py`

```python
@dataclass
class AgentTask:
    agent_name: str
    events: list[EventSchema]
    target_fields: list[str]
    prompt_version: str = "active"
    priority: int = 1
    retry_limit: int = 2

@dataclass
class AgentResult:
    agent_name: str
    prompt_name: str
    prompt_version: str           # resolved version used
    events: list[EventSchema]     # enriched
    confidence_scores: dict[str, float]
    token_usage: dict[str, int]   # prompt_tokens, completion_tokens, total
    errors: list[str]
    duration_seconds: float
```

---

# 9. LLM Provider Layer

Async-first. All providers implement `BaseLLMClient`:
- `complete(system, user, temperature, max_tokens) → str`
- `complete_structured(system, user, schema, ...) → T`
- `get_token_usage() → dict`

`provider_router.get_llm_client(provider, model_name, ...)` is the factory used by all agents.

| Provider | File | Structured Output | API Key |
|---|---|---|---|
| `anthropic` | `anthropic_client.py` | tool_use | ANTHROPIC_API_KEY |
| `openai` | `openai_client.py` | Instructor TOOLS | OPENAI_API_KEY |
| `ollama` / `llama` | `ollama_client.py` | Instructor JSON | None (local) |

**Ollama setup** (for Llama and other local models):
```bash
# 1. Install Ollama: https://ollama.com
# 2. Pull a model
ollama pull llama3.2:3b   # lightweight (DEFAULT)
ollama pull llama3.1:8b   # higher quality
# 3. Ollama starts automatically on port 11434
```

Switch any agent to Llama by setting `provider: "ollama"` in `configs/agents.yaml`.

---

# 10. MCP Integration Layer

Three modes, all implementing the same `MCPClient` abstract interface:

| Mode | Class | Transport | Use case |
|---|---|---|---|
| `direct` | `DirectMCPClient` | In-memory Python | Legacy; no FastMCP dependency |
| `local` | `LocalMCPClient` | FastMCP in-process | **Default** — no network, same process |
| `server` | `ServerMCPClient` | FastMCP HTTP SSE | Production — separate service |

**Start the FastMCP server (server mode):**
```bash
python -m src.agents.mcp.fastmcp_server --host localhost --port 8001
```

**Switch modes** in `configs/agents.yaml`:
```yaml
global:
  mcp_mode: "local"    # or "direct" | "server"
  mcp_server:
    url: "http://localhost:8001"
```

MCP Tools exposed:

| Tool | Type | Description |
|---|---|---|
| `fetch_event_row` | READ | Get a single event dict by ID |
| `fetch_missing_features` | READ | Check which target fields are missing |
| `list_events` | READ | List all event IDs in store |
| `fetch_taxonomy_enums` | READ | Get valid enum values for all taxonomy fields |
| `write_features` | WRITE | Write feature fields to an event |
| `write_taxonomy` | WRITE | Write taxonomy dimension fields |
| `write_emotions` | WRITE | Write emotional_output tags |
| `write_tags` | WRITE | Merge enriched tags (deduplicates) |
| `load_events_tool` | INIT | Bulk-load events into server store (server mode) |

---

# 11. Enrichment Agents

See status table in Section 7. All agents:
- Skip gracefully if disabled (`enabled: false`) or LLM unavailable
- Return `AgentResult` with `prompt_version` logged for auditability
- Feed enriched events to the next agent in the chain

---

# 12. Validation Layer

`SchemaValidator.validate_event(event)` checks all taxonomy enum fields against the data contract.
`compute_confidence_score(event)` scores field completeness (60%) + agent confidence (40%).
Events below `global.confidence_threshold` (0.6) are flagged via `flag_low_confidence()`.

---

# 13. Orchestration Layer

`BatchEnrichmentRunner` executes the ordered agent chain:
```
feature_alignment → taxonomy_classifier → emotion_mapper → data_quality
```

`PostIngestionTrigger.on_pipeline_complete(pipeline_result)` is the production entry point — call it after any `pipeline.execute()`.

Config is loaded from `src/configs/agents.yaml` via `load_agents_config()`.

---

# 14. Data Contract Integration

Agents do not rely on prompts alone.

They ingest structured contracts.

---

## Source

```

src/assets/data_contract.yaml

```

Defines:

- Feature names
- Descriptions
- Data types
- Enum options
- Extraction guidance

Used to:

- Generate system prompts
- Constrain outputs
- Validate writes

---

# 15. Enrichment Flow

```

Ingested Event
↓
Missing Feature Detection
↓
Agent Task Created
↓
MCP Fetch Context
↓
LLM Extraction
↓
Schema Validation
↓
MCP Write Back

```

---

# 16. Observability

All agent actions logged.

Tracked dimensions:

- Tokens used
- Cost per enrichment
- Confidence scores
- Write success rate
- Field coverage lift

---

# 17. Success Metrics

- % feature completeness
- Enrichment latency
- Cost per record
- Schema violation rate
- Human override frequency

---

# 18. Long-Term Vision

Agents evolve from extractors → analysts.

Future capabilities:

- Trend detection
- Cultural forecasting
- Demand prediction
- Experience gap, latent demand detection

---

# Closing Principle

Pulsecity does not scale intelligence through headcount.

It scales intelligence through agents connected to structured data rails.

MCP is the nervous system.

Agents are the cognition layer.

The dataset becomes the moat.

Keep track of latent demand (once the product is built). Jose



# Expansion Roadmap — Beyond MCP Architecture: IDEAS

| Category                | Initiative                        | Responsibility | Description                                                                                                                    | Priority |
| ----------------------- | --------------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------ | -------- |
| Data Contracts          | Contract Versioning System        | AI Engineer    | Implement versioned schemas for enrichment fields to track evolution of feature definitions and ensure backward compatibility. | High     |
| Data Contracts          | Contract Drift Detection          | AI Engineer    | Monitor when real-world data stops fitting contract assumptions (new genres, formats, HTML structures).                        | High     |
| MCP Platform            | MCP Auth & Permissioning          | CTO            | Role-based access for agents (read vs write scopes, field-level permissions).                                                  | High     |
| MCP Platform            | Write Sandboxing                  | CTO            | Staging write layer before production DB commit. Enables replay & rollback.                                                    | High     |
| MCP Platform            | MCP Rate Limiting                 | CTO            | Prevent runaway agent loops or cost explosions.                                                                                | Medium   |
| LLM Ops                 | Prompt Version Registry           | AI Engineer    | Track prompt changes per agent for auditability & performance regression testing.                                              | High     |
| LLM Ops                 | Structured Output Testing Harness | AI Engineer    | Automated tests to ensure providers respect JSON/schema constraints.                                                           | High     |
| LLM Ops                 | Provider Evaluation Benchmarks    | AI Engineer    | Compare OpenAI vs Claude vs Llama on enrichment accuracy & cost.                                                               | Medium   |
| LLM Ops                 | Cost Telemetry Layer              | CTO            | Aggregate token + infra cost across providers & pipelines.                                                                     | High     |
| Enrichment Intelligence | Multi-Agent Collaboration         | AI Engineer    | Agents cross-review outputs (taxonomy validates emotion, etc.).                                                                | Medium   |
| Enrichment Intelligence | Self-Reflection Loops             | AI Engineer    | Agent critiques its own output before write.                                                                                   | Medium   |
| Enrichment Intelligence | Ensemble Extraction               | AI Engineer    | Multiple providers vote on enrichment outputs.                                                                                 | Low      |
| Data Quality            | Human-in-the-Loop UI              | CTO            | Internal review dashboard for low-confidence enrichments.                                                                      | High     |
| Data Quality            | Override Learning System          | AI Engineer    | Train feedback loops from human corrections.                                                                                   | High     |
| Observability           | Agent Performance Dashboard       | CTO            | Track latency, enrichment lift, cost, error rates.                                                                             | High     |
| Observability           | Field Coverage Heatmaps           | AI Engineer    | Visualize enrichment completeness across dataset.                                                                              | Medium   |
| Storage                 | Feature Store Integration         | CTO            | Persist enriched features for downstream ML use.                                                                               | Medium   |
| Storage                 | Vector Store Layer                | CTO            | Store embeddings for semantic retrieval & clustering.                                                                          | Medium   |
| Intelligence Infra      | Embedding Pipelines               | AI Engineer    | Generate embeddings for events, artists, venues.                                                                               | High     |
| Intelligence Infra      | Similarity Graph Builder          | AI Engineer    | Build cultural/experience graphs from embeddings.                                                                              | Medium   |
| Orchestration           | DAG Pipeline Manager              | CTO            | Airflow/Temporal/Prefect orchestration of agent workflows.                                                                     | High     |
| Orchestration           | Real-Time Enrichment Queue        | CTO            | Kafka/PubSub triggers for streaming enrichment.                                                                                | Medium   |
| Evaluation              | Ground Truth Dataset Creation     | AI Engineer    | Curate labeled enrichment benchmarks.                                                                                          | High     |
| Evaluation              | Enrichment Accuracy Scoring       | AI Engineer    | Measure precision/recall on taxonomy, emotion, features.                                                                       | High     |
| Security                | PII Detection Agents              | AI Engineer    | Detect & redact sensitive info in ingested content.                                                                            | Medium   |
| Security                | Compliance Logging                | CTO            | GDPR/AI Act audit logs for automated decisions.                                                                                | Medium   |
| Resilience              | Fallback Provider Routing         | CTO            | Auto-switch providers on outage or degradation.                                                                                | Medium   |
| Resilience              | Idempotent Write Design           | CTO            | Prevent duplicate enrichment writes.                                                                                           | High     |
| Knowledge Layer         | Cultural Ontology Graph           | AI Engineer    | Build structured graph of genres, scenes, subcultures.                                                                         | High     |
| Knowledge Layer         | Temporal Trend Indexing           | AI Engineer    | Detect shifts in vibes, genres, demand over time.                                                                              | Medium   |
| Productization          | Intelligence API                  | CTO            | External/internal API exposing enriched event intelligence.                                                                    | Medium   |
| Productization          | Insight Generation Agents         | AI Engineer    | Convert enriched data into trend reports.                                                                                      | Low      |
