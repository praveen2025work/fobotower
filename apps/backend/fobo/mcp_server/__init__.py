"""MCP server: the read-only tools an agent harness calls while it reasons
about one L4 rec run.

Auth is a per-agent-session bearer token. The Reason step mints a random
token when it starts a session and stores only its sha256 on the agent_session
row; a request is honoured only while that session is starting or running. The
token resolves to an AgentContext (investigation session, caller, business
date, the run's unsettled breaks), so every graph read is scoped by that
caller's entitlement and that business date, and every call is audited as a
source_call. This package holds the tool logic; the HTTP mount lives apart.
"""
