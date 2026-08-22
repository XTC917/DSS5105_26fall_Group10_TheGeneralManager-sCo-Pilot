"""Discovery tools — not implemented in this MVP.

TODO: discover_factory_issues should scan orders + production_log for
ranked findings (at-risk orders, stalled work, unusual stage drops)
instead of a hard-coded briefing template.
"""

from __future__ import annotations

from backend.tools.common import tool_error


def discover_factory_issues() -> str:
    """Placeholder. Do not register this tool on the agent until it is implemented."""
    return tool_error(
        "discover_factory_issues",
        "NOT_IMPLEMENTED",
        "Discovery is out of scope for the first MVP. See docs/tool_spec.md.",
    )
