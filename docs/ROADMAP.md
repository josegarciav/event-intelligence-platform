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

# 7. src/agents/ — File Architecture

Below is the canonical structure to support MCP-native enrichment.

---

## Root Structure

```

src/agents/
│
├── base/
├── llm/
├── mcp/
├── enrichment/
├── validation/
└── orchestration/

```

---

# 8. Base Layer

## `src/agents/base/base_agent.py`

Defines the universal agent interface.

Responsibilities:

- Task definition
- Input schema binding
- MCP routing
- Output formatting

---

## `src/agents/base/task.py`

Task abstraction.

Encapsulates:

- Objective
- Input dataset slice
- Target fields
- Priority
- Retry logic

---

# 9. LLM Provider Layer

Provider logic is isolated from agent logic.

---

## `src/agents/llm/base_llm_client.py`

Abstract provider interface.

Defines:

- Completion calls
- Structured output calls
- Token accounting
- Retry handling

---

## `src/agents/llm/openai_client.py`

OpenAI implementation.

---

## `src/agents/llm/claude_client.py`

Anthropic implementation.

---

## `src/agents/llm/llama_client.py`

Llama implementation (links to a local model no API key required).

---

## `src/agents/llm/provider_router.py`

Dynamic routing:

- Cost optimization
- Latency routing
- Task specialization

---

# 10. MCP Integration Layer

This is the critical layer.

---

## `src/agents/mcp/mcp_client.py`

Primary MCP interface.

Handles:

- Read requests
- Write requests
- Auth
- Endpoint routing

---

## `src/agents/mcp/readers.py`

Predefined read operations:

- fetch_event_row
- fetch_html
- fetch_missing_features (at the event level)
- fetch_taxonomy_enums

---

## `src/agents/mcp/writers.py`

Predefined write operations:

- write_features
- write_taxonomy
- write_emotions
- write_normalization_notes
- write_tags

---

# 11. Enrichment Agents

Task-specific implementations.

---

## `src/agents/enrichment/feature_extractor.py`

Inputs:

- Event row
- Compressed HTML
- Data contract YAML

Outputs:

- Structured feature payload

---

## `src/agents/enrichment/taxonomy_classifier.py`

Maps events into taxonomy graph.

---

## `src/agents/enrichment/emotion_mapper.py`

Generates emotional + vibe tags.

---

## `src/agents/enrichment/artist_enricher.py`

Links artists to:

- Genres
- Popularity
- Audio embeddings (future)

---

# 12. Validation Layer

Prevents hallucinated writes.

---

## `src/agents/validation/schema_validator.py`

Validates against:

- Data contracts
- Enum sets
- Serialization rules
- Schema enforcement
- Serialization compliance

---

## `src/agents/validation/confidence.py`

Calculates outputs below:

- Confidence thresholds
    - Based on completeness thresholds and agent context into the event
- Reject based on low scores? We will still keep these though, we will have an internal review dashboard for low-confidence enrichments.

---

# 13. Orchestration Layer

Coordinates agent execution.

---

## `src/agents/orchestration/agent_runner.py`

Responsibilities:

- Batch task execution
- Retry handling
- Logging
- Metrics

---

## `src/agents/orchestration/pipeline_triggers.py`

Triggers agents on:

- New ingestion
- Missing fields
- Schema updates
- Low quality flags

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
