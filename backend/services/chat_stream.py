"""Progress events expose execution stages, never prompts, tool inputs or output."""
from langchain_core.callbacks import BaseCallbackHandler

_LABELS = {
    "get_order_status": "Reading the order record…",
    "trace_order": "Checking the order and its risk evidence…",
    "get_orders_at_risk": "Comparing remaining work with available time…",
    "check_feasibility": "Checking capacity against the requested order…",
    "draw": "Preparing the chart…", "render_table": "Preparing the table…",
}


class ToolProgress(BaseCallbackHandler):
    def __init__(self, emit):
        self.emit = emit

    def on_tool_start(self, serialized, input_str, **kwargs):
        name = (serialized or {}).get("name", "")
        self.emit(_LABELS.get(name, "Checking factory records…"))

    def on_tool_end(self, output, **kwargs):
        self.emit("Preparing the evidence and answer…")
