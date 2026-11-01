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
    <div className="space-y-1">
      {loading ? (
        <p className="px-2 py-3 type-caption text-subtle">Loading history…</p>
      ) : conversations.length === 0 ? (
        <p className="px-2 py-3 type-caption text-subtle">No saved conversations.</p>
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
                className={`focus-ring block w-full rounded-xl px-2.5 py-2 text-left transition-colors duration-[var(--dur-fast)] disabled:opacity-50 ${
                  active
                    ? "bg-accentSoft text-foreground shadow-xs"
                    : "text-foreground hover:bg-surfaceMuted"
                }`}
              >
                <span className="block truncate type-caption font-medium">{conversation.title}</span>
                <span className={`mt-0.5 block text-[10px] ${active ? "text-accentText" : "text-subtle"}`}>
                  {conversation.turn_count} turns · {formatUpdatedAt(conversation.updated_at)}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
