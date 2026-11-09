import { Avatar, BrandMark, Icon } from "./bits.jsx";

const PRIMARY_NAV = [
  { key: "ask", label: "Ask AI", icon: "chat" },
  { key: "overview", label: "Overview", icon: "grid" },
  { key: "alerts", label: "Alerts", icon: "bell" },
];

const ADMIN_NAV = [
  { key: "data", label: "Data Management", icon: "database" },
  { key: "users", label: "User Management", icon: "users" },
];

function RailButton({ item, active, onSelect }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(item.key)}
      aria-label={item.label}
      aria-current={active ? "page" : undefined}
      className={`dp-rail-btn focus-ring ${active ? "is-active" : ""}`}
    >
      <Icon name={item.icon} size={18} />
      <span className="dp-rail-tip">{item.label}</span>
    </button>
  );
}

/**
 * Desktop double-sidebar chrome: Navigation Rail | Context Panel | Workspace.
 * The rail never scrolls with the conversation, the context panel collapses
 * independently, and the flow switches are wired through props so the
 * surrounding DesktopWorkspace owns all preview state.
 */
export default function WorkspaceShell({
  activeNav,
  onNav,
  collapsed,
  onToggleCollapse,
  hasContext = true,
  contextTitle = "Workspace",
  contextSubtitle = "",
  context,
  mainTitle,
  mainSubtitle,
  mainActions,
  headerless = false,
  scrollMain = true,
  children,
}) {
  return (
    <div className="dp-window dp-rise">
      <div className="dp-shell">
        <aside className="dp-rail" aria-label="Primary navigation">
          <div className="dp-rail-brand">
            <BrandMark size={34} />
          </div>

          <div className="dp-rail-group">
            {PRIMARY_NAV.map((item) => (
              <RailButton key={item.key} item={item} active={activeNav === item.key} onSelect={onNav} />
            ))}
          </div>

          <div className="dp-rail-divider" role="presentation" />

          <div className="dp-rail-group">
            {ADMIN_NAV.map((item) => (
              <RailButton key={item.key} item={item} active={activeNav === item.key} onSelect={onNav} />
            ))}
          </div>

          <div className="dp-rail-spacer" />

          <div className="dp-rail-group">
            <RailButton
              item={{ key: "settings", label: "Settings", icon: "settings" }}
              active={activeNav === "settings"}
              onSelect={onNav}
            />
            <div className="dp-rail-avatar">
              <Avatar initials="MC" size={32} />
            </div>
          </div>
        </aside>

        {hasContext && (
          <aside
            className={`dp-context ${collapsed ? "is-collapsed" : ""}`}
            aria-hidden={collapsed}
            aria-label="Context panel"
          >
            <div className="dp-context-inner">
              <div className="dp-context-head">
                <div className="min-w-0">
                  <p className="dp-context-title truncate">{contextTitle}</p>
                  {contextSubtitle ? <p className="dp-context-sub truncate">{contextSubtitle}</p> : null}
                </div>
                <button
                  type="button"
                  onClick={onToggleCollapse}
                  className="dp-icon-btn h-8 w-8 focus-ring"
                  aria-label="Collapse context panel"
                  title="Collapse panel"
                >
                  <Icon name="panelLeft" size={14} />
                </button>
              </div>
              <div className="dp-context-scroll">{context}</div>
            </div>
          </aside>
        )}

        <main className="dp-main">
          {!headerless && (
            <div className="dp-main-topbar">
              <div className="dp-crumb">
                {hasContext && collapsed && (
                  <button
                    type="button"
                    onClick={onToggleCollapse}
                    className="dp-icon-btn h-8 w-8 focus-ring"
                    aria-label="Expand context panel"
                    title="Expand panel"
                  >
                    <Icon name="panelRight" size={14} />
                  </button>
                )}
                <div className="min-w-0">
                  <p className="dp-crumb-title truncate">{mainTitle}</p>
                  {mainSubtitle ? <p className="dp-crumb-sub truncate">{mainSubtitle}</p> : null}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2">{mainActions}</div>
            </div>
          )}

          {scrollMain ? <div className="dp-main-scroll">{children}</div> : children}
        </main>
      </div>
    </div>
  );
}
