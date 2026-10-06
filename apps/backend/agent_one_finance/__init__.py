"""Agent One Finance: the capability platform.

Orchestration (LangGraph), the MCP gateway to onboarded connectors, central
entitlement, a knowledge graph of past decisions, and a manifest-driven
console. A capability is configuration (config/agent-one-finance/capabilities/*.yaml);
the Agent One Finance team supplies connectors. The LLM and tracing backends plug in by
configuration (see agent_one_finance/config.py) so the same code runs here with stubs and
in the office against the real services.

Nothing in this package imports `fobo`.
"""
