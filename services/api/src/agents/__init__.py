"""
Pulsecity Agent Enrichment Layer.

Architecture:
  base/          — BaseAgent, AgentTask, AgentResult, output Pydantic models
  llm/           — BaseLLMClient, AnthropicLLMClient, OpenAILLMClient, provider_router
  mcp/           — MCPClient (DirectMCPClient in-memory; LocalMCPClient/ServerMCPClient FastMCP)
  enrichment/    — FeatureAlignmentAgent, TaxonomyClassifierAgent, EmotionMapperAgent,
                   DataQualityAgent, DeduplicationAgent, ArtistEnricherAgent
  validation/    — SchemaValidator, confidence scoring
  orchestration/ — BatchEnrichmentRunner, PostIngestionTrigger
  prompts/       — Versioned Jinja2 prompt templates (manifest.yaml + vN.yaml)
  registry/      — PromptRegistry, AgentRegistry

Entry points:
  from src.agents.orchestration import PostIngestionTrigger, load_agents_config
  from src.agents.registry import PromptRegistry
"""
