// Presentation metadata for the current chat; no history API dependency.
export function assistantMessage(answer, meta = {}) {
  return {
    role: "assistant", content: answer,
    toolsUsed: meta.tools_used || [], traces: meta.traces || [],
    why: meta.why || null, reasoningSummary: meta.reasoning_summary || [],
    limitation: meta.limitation, proposedActions: meta.proposed_actions || [],
    charts: meta.charts || [], tables: meta.tables || [],
    clarification: meta.clarification || null,
  };
}
