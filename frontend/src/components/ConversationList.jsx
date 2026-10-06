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
  createBusy,
  error,
  onSelect,
  onCreate,
  interactionDisabled,
}) {
  return (
    <section className="rounded-lg border border-ink/10 bg-white p-3 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-ink/60">
          Conversations
        </h2>

        <button
          type="button"
          disabled={createBusy || interactionDisabled}
          onClick={onCreate}
          className="rounded border border-ink/15 px-2 py-1 text-xs font-medium text-ink/70 hover:border-brass disabled:opacity-50"
        >
          {createBusy ? "Creating…" : interactionDisabled ? "Working…" : "New"}
        </button>
      </div>

      {error && (
        <p className="mt-2 rounded bg-red-50 px-2 py-1 text-xs text-red-700">
          {error}
        </p>
      )}

      {interactionDisabled && (
        <p className="mt-2 text-xs text-ink/50">
          Wait for the current response before switching conversations.
        </p>
      )}

      {loading && (
        <p className="mt-3 text-xs text-ink/45">
          Loading conversations…
        </p>
      )}

      {!loading && conversations.length === 0 && (
        <p className="mt-3 text-xs text-ink/45">
          No conversations yet.
        </p>
      )}

      {!loading && conversations.length > 0 && (
        <ul className="mt-2 space-y-1">
          {conversations.map((conversation) => {
            const active = conversation.id === activeConversationId;

            return (
              <li key={conversation.id}>
                <button
                  type="button"
                  disabled={interactionDisabled}
                  onClick={() => onSelect(conversation.id)}
                  aria-current={active ? "true" : undefined}
                  className={`w-full rounded px-2 py-2 text-left disabled:cursor-not-allowed disabled:opacity-60 ${
                    active
                      ? "bg-ink text-paper"
                      : "text-ink/75 hover:bg-paper"
                  }`}
                >
                  <span className="block truncate text-xs font-medium">
                    {conversation.title}
                  </span>

                  <span
                    className={`mt-1 block text-[11px] ${
                      active ? "text-paper/60" : "text-ink/45"
                    }`}
                  >
                    {conversation.turn_count} turns
                    {conversation.updated_at
                      ? ` · ${formatUpdatedAt(conversation.updated_at)}`
                      : ""}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}