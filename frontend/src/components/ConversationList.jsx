function formatUpdatedAt(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export default function ConversationList({
  conversations,
  activeConversationId,
  loading,
  disabled,
  onSelect,
  onCreate,
}) {
  return (
    <section className="rounded-lg border border-ink/10 bg-white p-2 shadow-sm">
      <div className="mb-2 flex items-center justify-between gap-2 px-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-ink/60">Conversations</p>
        <button
          type="button"
          disabled={disabled}
          onClick={onCreate}
          className="rounded border border-ink/15 px-2 py-1 text-xs font-medium text-ink hover:border-brass disabled:opacity-50"
        >
          New
        </button>
      </div>
      {loading ? (
        <p className="px-2 py-3 text-xs text-ink/45">Loading history…</p>
      ) : conversations.length === 0 ? (
        <p className="px-2 py-3 text-xs text-ink/45">No saved conversations.</p>
      ) : (
        <div className="max-h-64 space-y-1 overflow-y-auto">
          {conversations.map((conversation) => {
            const active = conversation.id === activeConversationId;
            return (
              <button
                key={conversation.id}
                type="button"
                disabled={disabled}
                onClick={() => onSelect(conversation.id)}
                className={`block w-full rounded-md px-2 py-2 text-left disabled:opacity-50 ${
                  active ? "bg-ink text-paper" : "text-ink hover:bg-paper"
                }`}
              >
                <span className="block truncate text-xs font-medium">{conversation.title}</span>
                <span className={`mt-0.5 block text-[10px] ${active ? "text-paper/65" : "text-ink/45"}`}>
                  {conversation.turn_count} turns · {formatUpdatedAt(conversation.updated_at)}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
