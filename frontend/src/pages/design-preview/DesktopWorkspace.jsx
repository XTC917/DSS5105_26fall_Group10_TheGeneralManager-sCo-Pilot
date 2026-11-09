import { useEffect, useRef, useState } from "react";
import WorkspaceShell from "./WorkspaceShell.jsx";
import ConversationThread from "./ConversationThread.jsx";
import OverviewPreview from "./OverviewPreview.jsx";
import ThemePicker from "./ThemePicker.jsx";
import Composer from "./Composer.jsx";
import { AiOrb, Avatar, Icon, Pill } from "./bits.jsx";
import {
  ACCOUNT_PROFILE,
  ACTIVE_WATCHES,
  CONVERSATIONS,
  DESKTOP_SUGGESTIONS,
  MORNING_BRIEFING,
  SECURITY_ROWS,
  SETTINGS_SECTIONS,
  TRIGGERED_ALERTS,
  WATCH_HISTORY,
  WEEKLY_BRIEFING,
} from "./mockData.js";

const COLLAPSE_KEY = "sweaterco.designPreview.contextCollapsed";

const CANNED_REPLY =
  "Assembly is the only stage still below its 30-day median, so I would protect ORD-120 first. Releasing 200 pieces of ORD-115 into Cutting today keeps the week feasible without moving ORD-118.";

const STOPPED_REPLY = "Assembly has been below its median for three working days, so the safest move is to";

const TITLES = {
  ask: { title: "Ask AI", sub: "Grounded factory answers" },
  overview: { title: "Overview", sub: "Top issues · briefings" },
  alerts: { title: "Alerts", sub: "Triggered alerts · watches" },
  settings: { title: "Settings", sub: "Appearance · account · security · session" },
  data: { title: "Data Management", sub: "Admin · sources & uploads" },
  users: { title: "User Management", sub: "Admin · access & roles" },
};

function readCollapsed() {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(COLLAPSE_KEY) === "1";
  } catch {
    return false;
  }
}

/* ---- Context panel bodies ---------------------------------------------- */

function ConversationRow({ item, active, onSelect, onDelete }) {
  return (
    <div className={`dp-conv-row group ${active ? "is-active" : ""}`}>
      <button
        type="button"
        onClick={() => onSelect(item.id)}
        className="flex min-w-0 flex-1 items-center gap-2 text-left focus-ring rounded-lg"
      >
        <span className="dp-conv-line" />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[11px] font-medium leading-tight text-foreground">
            {item.title}
          </span>
          <span className="mt-0.5 block truncate text-[9px] text-muted">{item.preview}</span>
        </span>
        <span className="shrink-0 text-[8.5px] text-subtle">{item.time}</span>
      </button>
      <button
        type="button"
        onClick={() => onDelete(item.id)}
        aria-label={`Delete ${item.title}`}
        title="Delete conversation"
        className="focus-ring shrink-0 rounded-full p-1 text-subtle opacity-0 transition-opacity hover:text-danger group-hover:opacity-100 focus-visible:opacity-100"
      >
        <Icon name="close" size={12} />
      </button>
    </div>
  );
}

function AskContext({ convs, search, onSearch, selectedId, onSelect, onDelete, onNew }) {
  const filtered = convs.filter((item) => item.title.toLowerCase().includes(search.toLowerCase()));
  return (
    <div>
      <button type="button" onClick={onNew} className="dp-btn dp-btn-primary focus-ring h-9 w-full">
        <Icon name="plus" size={13} />
        New conversation
      </button>

      <div className="mt-2 flex items-center gap-2 rounded-full border border-line bg-surface/70 px-3 py-1.5">
        <Icon name="search" size={13} className="shrink-0 text-subtle" />
        <input
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          placeholder="Search conversations"
          className="min-w-0 flex-1 bg-transparent text-[10.5px] text-foreground outline-none placeholder:text-subtle"
        />
      </div>

      <div className="dp-context-section mt-4">
        <div className="dp-context-label">
          <span className="dp-eyebrow">Conversations</span>
          <span className="text-[9px] text-subtle">{filtered.length}</span>
        </div>
        <div className="space-y-1">
          {filtered.map((item) => (
            <ConversationRow
              key={item.id}
              item={item}
              active={selectedId === item.id}
              onSelect={onSelect}
              onDelete={onDelete}
            />
          ))}
          {filtered.length === 0 && <div className="dp-empty">No conversations match “{search}”.</div>}
        </div>
      </div>
    </div>
  );
}

function WatchRow({ item, onCancel }) {
  return (
    <div className="dp-watch-row">
      <span className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${item.tone === "danger" ? "bg-danger" : "bg-warning"}`} />
      <span className="min-w-0 flex-1">
        <span className="block text-[11px] font-semibold leading-tight text-foreground">{item.order}</span>
        <span className="mt-0.5 block truncate text-[9px] text-muted">{item.label}</span>
      </span>
      <button
        type="button"
        onClick={() => onCancel(item.id)}
        aria-label={`Cancel watch on ${item.order}`}
        title="Cancel watch"
        className="focus-ring shrink-0 rounded-full p-1 text-subtle hover:text-danger"
      >
        <Icon name="close" size={11} />
      </button>
    </div>
  );
}

function AlertsContext({ watches, onCancel }) {
  return (
    <div className="space-y-4">
      <div className="dp-context-section">
        <div className="dp-context-label">
          <span className="dp-eyebrow">Triggered alerts</span>
          <Pill tone="danger" dot>{TRIGGERED_ALERTS.length}</Pill>
        </div>
        <div className="space-y-1">
          {TRIGGERED_ALERTS.map((alert) => (
            <div key={alert.id} className="dp-watch-row">
              <span className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${alert.tone === "danger" ? "bg-danger" : "bg-warning"}`} />
              <span className="min-w-0 flex-1">
                <span className="block text-[11px] font-semibold leading-tight text-foreground">{alert.order}</span>
                <span className="mt-0.5 block truncate text-[9px] text-muted">{alert.title}</span>
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="dp-context-section">
        <div className="dp-context-label">
          <span className="dp-eyebrow">Active watches</span>
          <span className="text-[9px] text-subtle">{watches.length}</span>
        </div>
        <div className="space-y-1">
          {watches.length === 0 ? (
            <div className="dp-empty">No active watches</div>
          ) : (
            watches.map((item) => <WatchRow key={item.id} item={item} onCancel={onCancel} />)
          )}
        </div>
      </div>

      <div className="dp-context-section">
        <div className="dp-context-label">
          <span className="dp-eyebrow">Watch history</span>
        </div>
        <div className="space-y-1">
          {WATCH_HISTORY.map((item) => (
            <div key={item.id} className="dp-watch-row">
              <Icon name="history" size={12} className="shrink-0 text-subtle" />
              <span className="min-w-0 flex-1">
                <span className="block text-[10.5px] font-medium leading-tight text-foreground">{item.order}</span>
                <span className="mt-0.5 block truncate text-[9px] text-muted">{item.label}</span>
              </span>
              <span className="shrink-0 text-[8.5px] text-subtle">{item.time}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function OverviewContext({ tab, onTab, onOpen }) {
  const data = tab === "week" ? WEEKLY_BRIEFING : MORNING_BRIEFING;
  return (
    <div className="space-y-4">
      <div className="dp-segmented w-full">
        <button
          type="button"
          className={`flex-1 ${tab === "morning" ? "is-active" : ""}`}
          onClick={() => onTab("morning")}
        >
          Morning
        </button>
        <button
          type="button"
          className={`flex-1 ${tab === "week" ? "is-active" : ""}`}
          onClick={() => onTab("week")}
        >
          Weekly
        </button>
      </div>
      <div className="dp-card p-3.5">
        <p className="dp-eyebrow">{data.title}</p>
        <p className="mt-1 text-[10px] text-subtle">{data.date}</p>
        <p className="mt-2 text-[10px] leading-4 text-muted">{data.summary}</p>
      </div>
      <div className="space-y-2">
        {data.points.map((point) => (
          <div key={point.title} className="flex items-start gap-2.5">
            <span className={`dp-icon-tile dp-icon-tile-sm dp-tone-${point.tone}`}>
              <Icon name={point.icon} size={12} />
            </span>
            <div className="min-w-0">
              <p className="text-[10.5px] font-semibold leading-snug text-foreground">{point.title}</p>
              <p className="mt-0.5 text-[9px] leading-4 text-muted">{point.body}</p>
            </div>
          </div>
        ))}
      </div>
      <button type="button" onClick={onOpen} className="dp-btn dp-btn-ghost focus-ring h-8 w-full">
        <Icon name="grid" size={12} />
        Open full overview
      </button>
    </div>
  );
}

function SettingsContext({ section, onSection }) {
  return (
    <div className="space-y-1">
      {SETTINGS_SECTIONS.map((item) => {
        const active = item.id === section;
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onSection(item.id)}
            className={`dp-nav-item focus-ring ${active ? "is-active" : ""}`}
            style={active ? { background: "var(--dp-tint-soft)", color: "rgb(var(--accent-text))" } : undefined}
          >
            <span className="dp-icon-tile dp-icon-tile-sm" style={{ background: "transparent" }}>
              <Icon name={item.icon} size={14} />
            </span>
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

/* ---- Main workspace bodies --------------------------------------------- */

function WelcomeComposer({ input, onInput, onSubmit, busy, onStop, focusSignal }) {
  return (
    <Composer
      value={input}
      onChange={onInput}
      onSubmit={onSubmit}
      busy={busy}
      onStop={onStop}
      focusSignal={focusSignal}
      placeholder="Ask about orders, risk, or feasibility…"
    />
  );
}

function WelcomeView({ input, onInput, onSubmit, busy, onStop, focusSignal, onFill, onOpenOverview, onOpenAlerts }) {
  return (
    <div className="dp-welcome">
      <div className="dp-hero-grid" aria-hidden="true" />
      <div className="dp-welcome-inner">
        <div className="dp-rise text-center">
          <div className="relative mx-auto mb-7 flex h-[138px] w-[138px] items-center justify-center">
            <span className="dp-orb-halo" aria-hidden="true" />
            <AiOrb size={112} />
            <span className="dp-chip-float left-[-62px] top-4 hidden sm:inline-flex">
              <Icon name="shield" size={11} />
              Grounded
            </span>
            <span className="dp-chip-float bottom-3 right-[-58px] hidden sm:inline-flex" style={{ animationDelay: "-3s" }}>
              <Icon name="spark" size={11} />
              Live tools
            </span>
          </div>
          <p className="dp-eyebrow text-accentText">SweaterCo · Soft Intelligence</p>
          <h1 className="mt-3 text-[30px] font-semibold leading-[1.08] tracking-[-0.035em] text-foreground sm:text-[36px]">
            Good morning, Mei.
            <span className="dp-gradient-ink mt-1 block">What needs your attention?</span>
          </h1>
          <p className="mx-auto mt-4 max-w-[520px] text-[12.5px] leading-6 text-muted sm:text-[13.5px]">
            Ask about orders, production risk, or feasibility. Every answer is grounded in the factory&apos;s live
            tools — not the model&apos;s memory.
          </p>
        </div>

        <div className="dp-rise dp-rise-1 mt-8">
          <WelcomeComposer
            input={input}
            onInput={onInput}
            onSubmit={onSubmit}
            busy={busy}
            onStop={onStop}
            focusSignal={focusSignal}
          />
        </div>

        <div className="dp-rise dp-rise-2 mt-4 grid gap-2.5 sm:grid-cols-2">
          {DESKTOP_SUGGESTIONS.map((item) => (
            <button
              key={item.title}
              type="button"
              onClick={() => onFill(item.title)}
              className="dp-suggestion focus-ring"
              title="Fill the composer — does not send"
            >
              <span className={`dp-icon-tile dp-tone-${item.tone}`}>
                <Icon name={item.icon} size={17} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-[11.5px] font-semibold leading-snug text-foreground">{item.title}</span>
                <span className="mt-0.5 block text-[9.5px] text-muted">{item.meta}</span>
              </span>
              <Icon name="arrowRight" size={13} className="text-subtle" />
            </button>
          ))}
        </div>

        <div className="dp-rise dp-rise-3 mt-6 flex flex-wrap items-center justify-center gap-2">
          <button type="button" className="dp-chip focus-ring" onClick={onOpenOverview}>
            <Icon name="sun" size={11} />
            Morning briefing
          </button>
          <button type="button" className="dp-chip focus-ring" onClick={onOpenAlerts}>
            <Icon name="alert" size={11} />
            3 at risk
          </button>
          <button type="button" className="dp-chip focus-ring" onClick={onOpenAlerts}>
            <Icon name="bell" size={11} />
            2 watches triggered
          </button>
        </div>
      </div>
    </div>
  );
}

function ChatView({ messages, busy, onStop, input, onInput, onSubmit, focusSignal, onFill }) {
  const scrollRef = useRef(null);
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages.length, busy]);

  return (
    <div className="dp-chat">
      <div className="dp-chat-scroll" ref={scrollRef}>
        <ConversationThread messages={messages} busy={busy} onGoDeeper={onFill} />
      </div>
      <div className="dp-chat-composer">
        <div className="mx-auto w-full max-w-[760px]">
          <Composer
            value={input}
            onChange={onInput}
            onSubmit={onSubmit}
            busy={busy}
            onStop={onStop}
            focusSignal={focusSignal}
            placeholder="Ask a follow-up about these orders…"
          />
        </div>
      </div>
    </div>
  );
}

function AlertsMain({ watches, onCancel }) {
  return (
    <div className="space-y-4 p-4 md:p-5">
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="dp-setting-card">
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className="dp-eyebrow">Today</p>
              <h3 className="mt-1 text-[15px] font-semibold tracking-[-0.02em] text-foreground">Triggered alerts</h3>
            </div>
            <Pill tone="danger" dot>{TRIGGERED_ALERTS.length} open</Pill>
          </div>
          <div className="mt-3 space-y-2">
            {TRIGGERED_ALERTS.map((alert) => (
              <div key={alert.id} className={`dp-alert-row ${alert.tone === "danger" ? "is-danger" : "is-warning"}`}>
                <span className={`dp-icon-tile dp-icon-tile-sm dp-tone-${alert.tone}`}>
                  <Icon name="alert" size={13} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11.5px] font-semibold text-foreground">{alert.order}</p>
                    <span className="text-[8.5px] text-subtle">{alert.time}</span>
                  </div>
                  <p className="mt-0.5 text-[10px] leading-4 text-muted">{alert.title}</p>
                  <p className="mt-0.5 text-[8.5px] text-subtle">{alert.meta}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="dp-setting-card">
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className="dp-eyebrow">Watching</p>
              <h3 className="mt-1 text-[15px] font-semibold tracking-[-0.02em] text-foreground">Active watches</h3>
            </div>
            <span className="text-[9px] text-subtle">{watches.length} active</span>
          </div>
          <div className="mt-3 space-y-2">
            {watches.length === 0 ? (
              <div className="dp-empty">No active watches</div>
            ) : (
              watches.map((item) => (
                <div key={item.id} className={`dp-alert-row ${item.tone === "danger" ? "is-danger" : "is-warning"}`}>
                  <span className={`h-2 w-2 flex-shrink-0 rounded-full ${item.tone === "danger" ? "bg-danger" : "bg-warning"}`} />
                  <div className="min-w-0 flex-1">
                    <p className="text-[11.5px] font-semibold text-foreground">{item.order}</p>
                    <p className="mt-0.5 text-[10px] leading-4 text-muted">{item.label}</p>
                  </div>
                  <button type="button" className="dp-btn dp-btn-ghost focus-ring h-7" onClick={() => onCancel(item.id)}>
                    Cancel
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="dp-setting-card">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-[13px] font-semibold text-foreground">Watch history</h3>
          <span className="text-[9px] text-subtle">Last 7 days</span>
        </div>
        <div className="mt-2 divide-y divide-line/60">
          {WATCH_HISTORY.map((item) => (
            <div key={item.id} className="flex items-center gap-3 py-2.5">
              <Icon name="history" size={13} className="shrink-0 text-subtle" />
              <div className="min-w-0 flex-1">
                <p className="text-[11px] font-medium text-foreground">{item.order}</p>
                <p className="mt-0.5 text-[9.5px] text-muted">{item.label}</p>
              </div>
              <Pill tone={item.result === "Cancelled" ? "neutral" : "success"}>{item.result}</Pill>
              <span className="w-12 text-right text-[9px] text-subtle">{item.time}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function SettingsMain({ section, theme, onTheme }) {
  return (
    <div className="space-y-4 p-4 md:p-5">
      {section === "appearance" && (
        <div className="dp-setting-card">
          <p className="dp-eyebrow">Theme</p>
          <h3 className="mt-1 text-[15px] font-semibold tracking-[-0.02em] text-foreground">Colour theme</h3>
          <p className="mt-1 max-w-[560px] text-[10.5px] leading-4 text-muted">
            Seven complete themes. There is no Light / Dark / System switch — each theme ships its own surfaces and
            contrast, including a bespoke Black theme.
          </p>
          <div className="mt-3">
            <ThemePicker variant="grid" theme={theme} onChange={onTheme} />
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            <span className="dp-chip">Persisted locally</span>
            <span className="dp-chip">Instant switch</span>
            <span className="dp-chip">Black is not Day/Night</span>
          </div>
        </div>
      )}

      {section === "account" && (
        <div className="dp-setting-card">
          <div className="flex items-center gap-3">
            <Avatar initials={ACCOUNT_PROFILE.initials} size={44} />
            <div className="min-w-0">
              <p className="text-[14px] font-semibold text-foreground">{ACCOUNT_PROFILE.name}</p>
              <p className="text-[10px] text-muted">{ACCOUNT_PROFILE.role} · {ACCOUNT_PROFILE.factory}</p>
            </div>
          </div>
          <div className="mt-4 space-y-2">
            <div className="dp-setting-row">
              <span className="text-[10.5px] text-muted">Email</span>
              <span className="text-[10.5px] font-medium text-foreground">{ACCOUNT_PROFILE.email}</span>
            </div>
            <div className="dp-setting-row">
              <span className="text-[10.5px] text-muted">Role</span>
              <span className="text-[10.5px] font-medium text-foreground">{ACCOUNT_PROFILE.role}</span>
            </div>
            <div className="dp-setting-row">
              <span className="text-[10.5px] text-muted">Factory</span>
              <span className="text-[10.5px] font-medium text-foreground">{ACCOUNT_PROFILE.factory}</span>
            </div>
          </div>
        </div>
      )}

      {section === "security" && (
        <div className="dp-setting-card">
          <h3 className="text-[15px] font-semibold tracking-[-0.02em] text-foreground">Security</h3>
          <div className="mt-3 space-y-2">
            {SECURITY_ROWS.map((row) => (
              <div key={row.id} className="dp-setting-row">
                <div className="flex items-center gap-2.5">
                  <span className="dp-icon-tile dp-icon-tile-sm dp-tone-neutral">
                    <Icon name={row.id === "pw" ? "key" : row.id === "2fa" ? "shield" : "monitor"} size={13} />
                  </span>
                  <div>
                    <p className="text-[10.5px] font-medium text-foreground">{row.label}</p>
                    <p className="text-[9px] text-muted">{row.value}</p>
                  </div>
                </div>
                <button type="button" className="dp-btn dp-btn-ghost focus-ring h-7" title="Static preview">
                  {row.action}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {section === "session" && (
        <div className="dp-setting-card">
          <h3 className="text-[15px] font-semibold tracking-[-0.02em] text-foreground">Session</h3>
          <div className="mt-3 space-y-2">
            <div className="dp-setting-row">
              <div className="flex items-center gap-2.5">
                <span className="dp-icon-tile dp-icon-tile-sm dp-tone-success">
                  <Icon name="monitor" size={13} />
                </span>
                <div>
                  <p className="text-[10.5px] font-medium text-foreground">This device</p>
                  <p className="text-[9px] text-muted">Active now · Singapore</p>
                </div>
              </div>
              <Pill tone="success" dot>Current</Pill>
            </div>
            <div className="flex items-center justify-between gap-2 rounded-xl border border-line/70 bg-surface/50 px-3.5 py-3">
              <span className="text-[9.5px] text-muted">Sign out of this preview session.</span>
              <button type="button" className="dp-btn dp-btn-ghost focus-ring h-7" title="Static preview">
                <Icon name="logout" size={12} />
                Sign out
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ManagementMain({ kind }) {
  const isData = kind === "data";
  return (
    <div className="space-y-4 p-4 md:p-5">
      <div className="dp-setting-card">
        <div className="flex items-start gap-3">
          <span className={`dp-icon-tile dp-tone-accent`}>
            <Icon name={isData ? "database" : "users"} size={17} />
          </span>
          <div className="min-w-0">
            <h3 className="text-[15px] font-semibold tracking-[-0.02em] text-foreground">
              {isData ? "Data Management" : "User Management"}
            </h3>
            <p className="mt-1 max-w-[560px] text-[10.5px] leading-4 text-muted">
              {isData
                ? "Upload datasets, review sources and row-level changes. This admin area has no contextual feed, so the context panel is hidden automatically."
                : "Invite teammates, assign roles and review access. This admin area has no contextual feed, so the context panel is hidden automatically."}
            </p>
          </div>
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-3">
          {(isData
            ? [
                { label: "Sources", value: "orders.csv", icon: "database" },
                { label: "Last upload", value: "Today · 06:12", icon: "refresh" },
                { label: "Rows changed", value: "0 pending", icon: "layers" },
              ]
            : [
                { label: "Members", value: "8 active", icon: "users" },
                { label: "Admins", value: "2", icon: "shield" },
                { label: "Pending invites", value: "0", icon: "clock" },
              ]
          ).map((stat) => (
            <div key={stat.label} className="rounded-xl border border-line/70 bg-surface/50 p-3">
              <div className="flex items-center gap-1.5 text-[8.5px] uppercase tracking-[0.12em] text-muted">
                <Icon name={stat.icon} size={11} />
                {stat.label}
              </div>
              <p className="mt-1.5 text-[13px] font-semibold text-foreground">{stat.value}</p>
            </div>
          ))}
        </div>
      </div>
      <div className="dp-empty">
        <Icon name="panelLeft" size={16} />
        Context panel hidden for this admin section
      </div>
    </div>
  );
}

/* ---- Orchestrator ------------------------------------------------------- */

export default function DesktopWorkspace({
  initialNav = "ask",
  initialConversation = null,
  theme,
  onTheme,
}) {
  const [activeNav, setActiveNav] = useState(initialNav);
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [convs, setConvs] = useState(CONVERSATIONS);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState(initialConversation);
  const [settingsSection, setSettingsSection] = useState("appearance");
  const [overviewTab, setOverviewTab] = useState("morning");
  const [watches, setWatches] = useState(ACTIVE_WATCHES);

  const [input, setInput] = useState("");
  const [focusSignal, setFocusSignal] = useState(0);
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState([]);
  const timerRef = useRef(null);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  function toggleCollapse() {
    setCollapsed((value) => {
      const next = !value;
      try {
        window.localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  }

  function fillComposer(text) {
    if (input.trim() && input.trim() !== text) {
      if (!window.confirm("Replace your current draft with this suggestion?")) return;
    }
    setInput(text);
    setFocusSignal((n) => n + 1);
  }

  function onSubmit() {
    const text = input.trim();
    if (!text || busy) return;
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    if (!selectedId) setSelectedId("trendcart");
    setBusy(true);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setMessages((prev) => [...prev, { role: "assistant", content: CANNED_REPLY }]);
      setBusy(false);
    }, 2600);
  }

  function onStop() {
    if (!busy) return;
    clearTimeout(timerRef.current);
    setBusy(false);
    setMessages((prev) => [...prev, { role: "assistant", content: STOPPED_REPLY, stopped: true }]);
  }

  function selectConversation(id) {
    setSelectedId(id);
    setActiveNav("ask");
    setMessages([]);
    setBusy(false);
    clearTimeout(timerRef.current);
  }

  function newConversation() {
    setSelectedId(null);
    setActiveNav("ask");
    setMessages([]);
    setInput("");
    setBusy(false);
    clearTimeout(timerRef.current);
    setFocusSignal((n) => n + 1);
  }

  function deleteConversation(id) {
    setConvs((prev) => prev.filter((item) => item.id !== id));
    if (selectedId === id) {
      setSelectedId(null);
      setMessages([]);
    }
  }

  function cancelWatch(id) {
    setWatches((prev) => prev.filter((item) => item.id !== id));
  }

  function openOverview() {
    setActiveNav("overview");
  }
  function openAlerts() {
    setActiveNav("alerts");
  }

  const hasContext = activeNav !== "data" && activeNav !== "users";

  let contextNode = null;
  let contextTitle = "Workspace";
  let contextSubtitle = "";
  if (activeNav === "ask") {
    contextTitle = "Conversations";
    contextSubtitle = `${convs.length} saved`;
    contextNode = (
      <AskContext
        convs={convs}
        search={search}
        onSearch={setSearch}
        selectedId={selectedId}
        onSelect={selectConversation}
        onDelete={deleteConversation}
        onNew={newConversation}
      />
    );
  } else if (activeNav === "alerts") {
    contextTitle = "Alerts";
    contextSubtitle = `${TRIGGERED_ALERTS.length} triggered`;
    contextNode = <AlertsContext watches={watches} onCancel={cancelWatch} />;
  } else if (activeNav === "overview") {
    contextTitle = "Briefing";
    contextSubtitle = overviewTab === "week" ? "Weekly" : "Morning";
    contextNode = <OverviewContext tab={overviewTab} onTab={setOverviewTab} onOpen={() => setActiveNav("overview")} />;
  } else if (activeNav === "settings") {
    contextTitle = "Settings";
    contextSubtitle = "4 sections";
    contextNode = <SettingsContext section={settingsSection} onSection={setSettingsSection} />;
  }

  const isConversation = activeNav === "ask" && selectedId;

  let mainActions = null;
  if (activeNav === "ask") {
    mainActions = (
      <>
        <span className="dp-status hidden sm:inline-flex">
          <span className="h-1.5 w-1.5 rounded-full bg-success" />
          Grounded
        </span>
        <button type="button" className="dp-pill focus-ring" onClick={newConversation} title="Start a new conversation">
          <Icon name="plus" size={12} />
          New chat
        </button>
      </>
    );
  } else {
    mainActions = (
      <span className="dp-chip hidden sm:inline-flex">
        <Icon name="shield" size={10} />
        Static sample
      </span>
    );
  }

  const meta = TITLES[activeNav] || TITLES.ask;

  return (
    <WorkspaceShell
      activeNav={activeNav}
      onNav={setActiveNav}
      collapsed={collapsed}
      onToggleCollapse={toggleCollapse}
      hasContext={hasContext}
      contextTitle={contextTitle}
      contextSubtitle={contextSubtitle}
      context={contextNode}
      mainTitle={activeNav === "ask" && selectedId ? "TrendCart risk review" : meta.title}
      mainSubtitle={activeNav === "ask" && selectedId ? "Saved conversation · 3 turns" : meta.sub}
      mainActions={mainActions}
      scrollMain={!isConversation}
    >
      {activeNav === "ask" &&
        (isConversation ? (
          <ChatView
            messages={messages}
            busy={busy}
            onStop={onStop}
            input={input}
            onInput={setInput}
            onSubmit={onSubmit}
            focusSignal={focusSignal}
            onFill={fillComposer}
          />
        ) : (
          <WelcomeView
            input={input}
            onInput={setInput}
            onSubmit={onSubmit}
            busy={busy}
            onStop={onStop}
            focusSignal={focusSignal}
            onFill={fillComposer}
            onOpenOverview={openOverview}
            onOpenAlerts={openAlerts}
          />
        ))}

      {activeNav === "overview" && (
        <OverviewPreview tab={overviewTab} onTabChange={setOverviewTab} embedded />
      )}

      {activeNav === "alerts" && <AlertsMain watches={watches} onCancel={cancelWatch} />}

      {activeNav === "settings" && (
        <SettingsMain section={settingsSection} theme={theme} onTheme={onTheme} />
      )}

      {(activeNav === "data" || activeNav === "users") && <ManagementMain kind={activeNav} />}
    </WorkspaceShell>
  );
}
