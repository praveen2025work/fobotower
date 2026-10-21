"""Agent One Finance: the agent platform.

Orchestration (LangGraph), the MCP gateway to onboarded connectors, central
entitlement, a knowledge graph of past decisions, and a manifest-driven
console. An agent is configuration (config/agent-one-finance/agents/*.yaml);
the Agent One Finance team supplies connectors. The LLM and tracing backends plug in by
configuration (see agent_one_finance/config.py) so the same code runs here with stubs and
in the office against the real services.

Nothing in this package imports `fobo`.
"""
