from fobo.console_views.calls import call_view


def _call(tool: str, application: str) -> dict:
    return {
        "call_id": "c-1", "tool": tool, "application": application,
        "params": {}, "rows": [], "summary": "s", "latency_ms": 1, "error": None,
    }


def test_a_dotted_tool_name_splits_into_server_and_tool():
    view = call_view(_call("helix.kg_lineage", "KG"), "USD")
    assert (view["server"], view["tool"]) == ("helix", "kg_lineage")


def test_an_agent_tool_without_a_dot_is_labelled_by_its_application():
    """Agent MCP calls are recorded as bare tool names; without this the
    inspector shows "fobo_list_breaks." with a dangling dot."""
    view = call_view(_call("fobo_list_breaks", "agent"), "USD")
    assert (view["server"], view["tool"]) == ("agent", "fobo_list_breaks")
