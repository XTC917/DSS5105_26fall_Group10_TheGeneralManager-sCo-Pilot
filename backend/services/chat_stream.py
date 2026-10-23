"""Progress labels for a live chat turn. No prompts, tool inputs, or tool output."""

from langchain_core.callbacks import BaseCallbackHandler

_LABELS = {
    "get_order_status": "Reading the order record…",
    "find_orders": "Listing the matching orders…",
    "trace_order": "Checking the order and its risk evidence…",
    "get_orders_at_risk": "Comparing remaining work with available time…",
    "get_today_priority": "Sorting today's priorities…",
    "get_morning_briefing": "Reading this morning's snapshot…",
    "discover_factory_issues": "Checking today's production issues…",
    "get_stage_output": "Reading recent stage output…",
    "check_feasibility": "Checking capacity against the requested order…",
    "filter_rows": "Filtering the retrieved rows…",
    "summarize_rows": "Summarizing the retrieved rows…",
    "draw": "Preparing the chart…",
    "render_table": "Preparing the table…",
}


class ToolProgress(BaseCallbackHandler):
    def __init__(self, emit, on_tool_start_extra=None):
        self.emit = emit
        self.on_tool_start_extra = on_tool_start_extra

    def on_tool_start(self, serialized, input_str, **kwargs):
        if self.on_tool_start_extra:
            self.on_tool_start_extra()
        name = (serialized or {}).get("name", "")
        self.emit(_LABELS.get(name, "Checking factory records…"))

    def on_tool_end(self, output, **kwargs):
        self.emit("Preparing the evidence and answer…")
