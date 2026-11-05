import { useEffect, useId, useRef, useState } from "react";

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

function MenuIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <circle cx="12" cy="5" r="1.8" />
      <circle cx="12" cy="12" r="1.8" />
      <circle cx="12" cy="19" r="1.8" />
    </svg>
  );
}

function ConversationRow({
  conversation,
  active,
  disabled,
  canDelete,
  deleting,
  menuOpen,
  onSelect,
  onToggleMenu,
  onRequestDelete,
}) {
  return (
    <div
      className={`group relative flex items-stretch gap-0.5 rounded-xl transition-colors duration-[var(--dur-fast)] ${
        active ? "bg-accentSoft text-foreground shadow-xs" : "text-foreground hover:bg-surfaceMuted"
      }`}
    >
      <button
        type="button"
        disabled={disabled}
        onClick={() => onSelect(conversation.id)}
        className="focus-ring min-w-0 flex-1 rounded-xl px-2.5 py-2 text-left disabled:opacity-50"
      >
        <span className="block truncate type-caption font-medium">{conversation.title}</span>
        <span className={`mt-0.5 block text-[10px] ${active ? "text-accentText" : "text-subtle"}`}>
          {conversation.turn_count} turns · {formatUpdatedAt(conversation.updated_at)}
        </span>
      </button>
      {canDelete && (
        <div className="relative shrink-0 self-center pr-1">
          <button
            type="button"
            aria-label={`Conversation actions for ${conversation.title}`}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            disabled={disabled || deleting}
            onClick={(event) => {
              event.stopPropagation();
              onToggleMenu(conversation.id);
            }}
            className={`focus-ring rounded-control p-1.5 text-muted transition-colors hover:bg-surface hover:text-foreground disabled:opacity-50 ${
              menuOpen ? "bg-surface text-foreground" : "opacity-100 md:opacity-0 md:group-hover:opacity-100"
            }`}
          >
            <MenuIcon />
          </button>
          {menuOpen && (
            <div
              role="menu"
              className="absolute right-0 top-full z-20 mt-1 min-w-[8rem] rounded-control border border-line bg-surface py-1 shadow-float"
            >
              <button
                type="button"
                role="menuitem"
                disabled={deleting}
                onClick={(event) => {
                  event.stopPropagation();
                  onRequestDelete(conversation);
                }}
                className="focus-ring block w-full px-3 py-1.5 text-left type-caption font-medium text-danger hover:bg-dangerSoft disabled:opacity-50"
              >
                {deleting ? "Deleting…" : "Delete"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ConversationList({
  conversations,
  activeConversationId,
  loading,
  searching = false,
  searchQuery = "",
  searchEnabled = false,
  searchUnavailable = false,
  onSearchChange,
  disabled,
  canDelete = false,
  deleteUnavailable = false,
  deletingId = null,
  onSelect,
  onCreate,
  onRequestDelete,
  listError = "",
  emptyLabel,
  scrollable = true,
}) {
  const searchId = useId();
  const [openMenuId, setOpenMenuId] = useState(null);
  const rootRef = useRef(null);

  useEffect(() => {
    if (!openMenuId) return undefined;
    function onPointerDown(event) {
      if (!rootRef.current?.contains(event.target)) {
        setOpenMenuId(null);
      }
    }
    function onKeyDown(event) {
      if (event.key === "Escape") setOpenMenuId(null);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [openMenuId]);

  useEffect(() => {
    setOpenMenuId(null);
  }, [conversations, searchQuery]);

  const showSearch = searchEnabled || searchUnavailable;
  const trimmedQuery = (searchQuery || "").trim();
  const busy = loading || searching;
  const defaultEmpty = trimmedQuery ? "No conversations match this search." : "No saved conversations.";

  return (
    <div ref={rootRef} className="space-y-2">
      {showSearch && (
        <div className="space-y-1">
          <label htmlFor={searchId} className="sr-only">
            Search conversations
          </label>
          <div className="relative">
            <input
              id={searchId}
              type="search"
              value={searchQuery}
              disabled={disabled || !searchEnabled}
              placeholder={searchEnabled ? "Search title, questions, answers…" : "Search unavailable on this backend"}
              onChange={(event) => onSearchChange?.(event.target.value)}
              className="focus-ring w-full rounded-control border border-line bg-surface px-2.5 py-1.5 pr-8 type-caption text-foreground placeholder:text-subtle disabled:cursor-not-allowed disabled:opacity-60"
            />
            {trimmedQuery && searchEnabled && (
              <button
                type="button"
                aria-label="Clear search"
                disabled={disabled}
                onClick={() => onSearchChange?.("")}
                className="focus-ring absolute right-1 top-1/2 -translate-y-1/2 rounded-control px-1.5 py-0.5 type-caption text-muted hover:text-foreground disabled:opacity-50"
              >
                Clear
              </button>
            )}
          </div>
          {searchUnavailable && (
            <p className="px-0.5 type-caption text-subtle">
              Conversation search needs the backend upgrade before it can run here.
            </p>
          )}
          {searchEnabled && searching && (
            <p className="px-0.5 type-caption text-subtle" role="status">
              Searching…
            </p>
          )}
        </div>
      )}

      {deleteUnavailable && (
        <p className="px-0.5 type-caption text-subtle">
          Conversation delete needs the backend upgrade before it can run here.
        </p>
      )}

      {listError && (
        <p className="rounded-card border border-danger/30 bg-dangerSoft px-3 py-2 type-sm text-danger" role="alert">
          {listError}
        </p>
      )}

      {busy && conversations.length === 0 ? (
        <p className="px-2 py-3 type-caption text-subtle" role="status">
          {searching ? "Searching…" : "Loading history…"}
        </p>
      ) : conversations.length === 0 ? (
        <p className="px-2 py-3 type-caption text-subtle">{emptyLabel || defaultEmpty}</p>
      ) : (
        <div className={`space-y-1 ${scrollable ? "max-h-64 overflow-y-auto" : ""}`}>
          {conversations.map((conversation) => (
            <ConversationRow
              key={conversation.id}
              conversation={conversation}
              active={conversation.id === activeConversationId}
              disabled={disabled}
              canDelete={canDelete}
              deleting={deletingId === conversation.id}
              menuOpen={openMenuId === conversation.id}
              onSelect={onSelect}
              onToggleMenu={(id) => setOpenMenuId((current) => (current === id ? null : id))}
              onRequestDelete={(item) => {
                setOpenMenuId(null);
                onRequestDelete?.(item);
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
