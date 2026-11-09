import { useEffect, useRef, useState } from "react";
import { AiOrb, BrandMark, Icon, Pill } from "./bits.jsx";
import Composer from "./Composer.jsx";
import ThemePicker from "./ThemePicker.jsx";
import {
  ACCOUNT_PROFILE,
  ACTIVE_WATCHES,
  CONVERSATIONS,
  METRICS,
  MORNING_BRIEFING,
  MOBILE_SUGGESTIONS,
  TRIGGERED_ALERTS,
  TOP_ISSUES,
  WATCH_HISTORY,
  WEEKLY_BRIEFING,
} from "./mockData.js";

const CANNED_REPLY =
  "Protect ORD-120 first — Assembly is the only stage still below its 30-day median. Releasing ORD-115 into Cutting today keeps the week feasible.";

const STOPPED_REPLY = "Assembly has been below its median for three working days, so the safest move is to";

function PhoneStatus() {
  return (
    <div className="dp-mobile-status">
      <span>9:41</span>
      <span className="flex items-center gap-1.5" aria-hidden="true">
        <svg width="12" height="8" viewBox="0 0 12 8" fill="none">
          <rect x="0" y="5.5" width="2" height="2.5" rx="0.6" fill="currentColor" />
          <rect x="3.2" y="4" width="2" height="4" rx="0.6" fill="currentColor" />
          <rect x="6.4" y="2.4" width="2" height="5.6" rx="0.6" fill="currentColor" />
          <rect x="9.6" y="0.8" width="2" height="7.2" rx="0.6" fill="currentColor" opacity="0.4" />
        </svg>
        <svg width="12" height="9" viewBox="0 0 12 9" fill="none">
          <path d="M1 3.2a7.5 7.5 0 0 1 10 0M2.9 5.1a4.8 4.8 0 0 1 6.2 0M4.7 6.9a2.3 2.3 0 0 1 2.6 0" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
        </svg>
        <svg width="16" height="8" viewBox="0 0 16 8" fill="none">
          <rect x="0.6" y="0.6" width="12.8" height="6.8" rx="2" stroke="currentColor" strokeWidth="1" opacity="0.55" />
          <rect x="2" y="2" width="9.2" height="4" rx="1.2" fill="currentColor" />
          <path d="M14.6 3v2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" opacity="0.55" />
        </svg>
      </span>
    </div>
  );
}

function MobileTop({ onMenu, onBell, hasAlerts }) {
  return (
    <div className="dp-mobile-top">
      <button type="button" className="dp-icon-btn h-8 w-8 focus-ring" aria-label="History and menu" onClick={onMenu}>
        <Icon name="menu" size={15} />
      </button>
      <div className="dp-mobile-brand">
        <BrandMark size={24} />
        <span className="dp-mobile-brand-name truncate">SweaterCo</span>
      </div>
      <button
        type="button"
        className="dp-icon-btn relative h-8 w-8 justify-self-end focus-ring"
        aria-label="Alerts"
        onClick={onBell}
      >
        <Icon name="bell" size={15} />
        {hasAlerts && <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-danger ring-2 ring-surface" />}
      </button>
    </div>
  );
}

function MobileSuggestion({ item, onFill }) {
  return (
    <button
      type="button"
      onClick={() => onFill(item.title)}
      className="dp-suggestion focus-ring !rounded-2xl !p-2.5"
      title="Fill the composer — does not send"
    >
      <span className={`dp-icon-tile dp-icon-tile-sm dp-tone-${item.tone}`}>
        <Icon name={item.icon} size={14} />
      </span>
      <span className="min-w-0 flex-1 text-left">
        <span className="block text-[10.5px] font-semibold leading-snug text-foreground">{item.title}</span>
        <span className="mt-0.5 block text-[8.5px] text-muted">{item.meta}</span>
      </span>
      <Icon name="arrowRight" size={11} className="text-subtle" />
    </button>
  );
}

function MobileWelcome({ onFill }) {
  return (
    <div className="dp-mobile-pad">
      <div className="flex flex-col items-center text-center">
        <div className="relative flex h-[96px] w-[96px] items-center justify-center">
          <span className="dp-orb-halo" aria-hidden="true" />
          <AiOrb size={78} />
        </div>
        <p className="dp-eyebrow mt-3 text-accentText">SweaterCo AI</p>
        <h1 className="mt-1.5 text-[24px] font-semibold leading-[1.08] tracking-[-0.035em] text-foreground">
          Good morning, Mei.
        </h1>
        <p className="dp-gradient-ink mt-1 text-[20px] font-semibold leading-[1.12] tracking-[-0.035em]">
          What needs your attention?
        </p>
        <p className="mt-2.5 max-w-[280px] text-[10.5px] leading-[1.65] text-muted">
          Ask about orders, risk or feasibility. Answers stay grounded in factory tools.
        </p>
      </div>

      <div className="mt-5 space-y-1.5">
        {MOBILE_SUGGESTIONS.map((item) => (
          <MobileSuggestion key={item.title} item={item} onFill={onFill} />
        ))}
      </div>
    </div>
  );
}

function MobileChat({ messages, busy }) {
  return (
    <div className="dp-mobile-pad space-y-3">
      <div className="flex justify-end">
        <div className="max-w-[84%]">
          <div className="dp-user-bubble !text-[11px]">Which orders are at risk right now?</div>
        </div>
      </div>
      <div>
        <div className="flex items-center gap-2">
          <AiOrb size={24} />
          <p className="text-[10px] font-semibold text-foreground">Co-Pilot</p>
          <span className="dp-chip !h-5 !px-1.5 !text-[8px]">3 tools</span>
        </div>
        <div className="dp-prose mt-2 !text-[11px]">
          <p>
            Three TrendCart orders need attention. <strong>ORD-120</strong> is the largest exposure at 1,200 pieces —
            Assembly has not moved for three working days.
          </p>
        </div>
      </div>

      {messages.map((msg, index) =>
        msg.role === "user" ? (
          <div key={`u-${index}`} className="flex justify-end">
            <div className="max-w-[84%]">
              <div className="dp-user-bubble !text-[11px]">{msg.content}</div>
            </div>
          </div>
        ) : (
          <div key={`a-${index}`}>
            <div className="flex items-center gap-2">
              <AiOrb size={20} />
              <p className="text-[9px] font-semibold text-foreground">Co-Pilot</p>
            </div>
            <div className="dp-prose mt-1.5 !text-[11px]">
              <p>{msg.content}</p>
            </div>
            {msg.stopped && (
              <span className="dp-stopped !text-[8px]">
                <Icon name="stop" size={8} />
                Stopped · preview
              </span>
            )}
          </div>
        ),
      )}

      {busy && (
        <div className="dp-stream-note !text-[9px]">
          <span className="dp-pulse-dot" />
          Working through the factory tools…
        </div>
      )}
    </div>
  );
}

function MobileOverview({ tab, onTab }) {
  const data = tab === "week" ? WEEKLY_BRIEFING : MORNING_BRIEFING;
  return (
    <div className="dp-mobile-pad space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="dp-eyebrow">Insights · Factory 12</p>
          <h1 className="mt-1 text-[19px] font-semibold leading-tight tracking-[-0.03em] text-foreground">Overview</h1>
        </div>
        <div className="dp-segmented !p-0.5">
          <button type="button" className={`!h-6 !px-2 !text-[9px] ${tab === "morning" ? "is-active" : ""}`} onClick={() => onTab("morning")}>
            Morning
          </button>
          <button type="button" className={`!h-6 !px-2 !text-[9px] ${tab === "week" ? "is-active" : ""}`} onClick={() => onTab("week")}>
            Weekly
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {METRICS.map((metric) => (
          <div key={metric.label} className="dp-card !rounded-2xl !p-2.5">
            <div className="flex items-start justify-between gap-1">
              <p className="dp-eyebrow !text-[7.5px]">{metric.label}</p>
              <span className={`dp-icon-tile dp-icon-tile-sm !h-6 !w-6 dp-tone-${metric.tone}`}>
                <Icon name={metric.icon} size={11} />
              </span>
            </div>
            <p className="mt-1.5 tabular text-[17px] font-semibold leading-none tracking-[-0.03em] text-foreground">
              {metric.value}
            </p>
            <p className="mt-1 text-[8px] text-muted">{metric.delta} vs last week</p>
          </div>
        ))}
      </div>

      <div className="dp-card overflow-hidden !rounded-2xl">
        <div className="dp-briefing-hero !px-3.5 !py-3">
          <p className="dp-briefing-muted text-[7.5px] font-semibold uppercase tracking-[0.16em]">Factory briefing</p>
          <h3 className="dp-briefing-title mt-1 text-[15px] font-semibold leading-tight">{data.title}</h3>
          <p className="dp-briefing-muted mt-0.5 text-[8.5px]">{data.date}</p>
        </div>
        <div className="p-3.5">
          <p className="text-[9.5px] leading-4 text-muted">{data.summary}</p>
        </div>
      </div>

      <div className="dp-card !rounded-2xl p-3.5">
        <div className="flex items-center justify-between">
          <p className="text-[11px] font-semibold text-foreground">Top issues</p>
          <Pill tone="danger" dot>{TOP_ISSUES.length} open</Pill>
        </div>
        <div className="mt-1 divide-y divide-line/60">
          {TOP_ISSUES.slice(0, 3).map((issue) => (
            <div key={issue.title} className="flex items-start gap-2 py-2">
              <span
                className={`mt-0.5 inline-flex h-4 w-6 flex-shrink-0 items-center justify-center rounded text-[7px] font-bold ${
                  issue.priority === "P1"
                    ? "bg-dangerSoft text-danger"
                    : issue.priority === "P2"
                      ? "bg-warningSoft text-warning"
                      : "bg-surfaceMuted text-muted"
                }`}
              >
                {issue.priority}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[10px] font-semibold text-foreground">{issue.title}</p>
                <p className="mt-0.5 truncate text-[8px] text-muted">{issue.meta}</p>
              </div>
              <Pill tone={issue.tone} dot>{issue.risk}</Pill>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function MobileSettings({ theme, onTheme }) {
  return (
    <div className="dp-mobile-pad space-y-3">
      <div>
        <p className="dp-eyebrow">Settings</p>
        <h1 className="mt-1 text-[19px] font-semibold leading-tight tracking-[-0.03em] text-foreground">Appearance</h1>
      </div>
      <div className="dp-setting-card !rounded-2xl !p-3.5">
        <p className="text-[10.5px] font-semibold text-foreground">Colour theme</p>
        <p className="mt-0.5 text-[8.5px] leading-4 text-muted">
          Seven themes. No Light / Dark / System switch — Black is its own theme.
        </p>
        <div className="mt-2.5">
          <ThemePicker variant="grid" theme={theme} onChange={onTheme} />
        </div>
      </div>
      <div className="dp-setting-card !rounded-2xl !p-3.5">
        <div className="flex items-center gap-2.5">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-line bg-surfaceMuted text-[11px] font-semibold text-foreground">
            {ACCOUNT_PROFILE.initials}
          </span>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold text-foreground">{ACCOUNT_PROFILE.name}</p>
            <p className="text-[8.5px] text-muted">{ACCOUNT_PROFILE.role}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function AlertsDrawerBody({ watches, onCancel }) {
  return (
    <div className="space-y-4">
      <div>
        <div className="dp-context-label">
          <span className="dp-eyebrow">Triggered alerts</span>
          <Pill tone="danger" dot>{TRIGGERED_ALERTS.length}</Pill>
        </div>
        <div className="space-y-1.5">
          {TRIGGERED_ALERTS.map((alert) => (
            <div key={alert.id} className="dp-mobile-watch">
              <span className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${alert.tone === "danger" ? "bg-danger" : "bg-warning"}`} />
              <div className="min-w-0 flex-1">
                <p className="text-[10.5px] font-semibold leading-tight text-foreground">{alert.order}</p>
                <p className="mt-0.5 text-[8.5px] leading-3.5 text-muted">{alert.title}</p>
              </div>
              <span className="text-[8px] text-subtle">{alert.time}</span>
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="dp-context-label">
          <span className="dp-eyebrow">Active watches</span>
          <span className="text-[8.5px] text-subtle">{watches.length}</span>
        </div>
        <div className="space-y-1.5">
          {watches.length === 0 ? (
            <div className="dp-empty !py-4">No active watches</div>
          ) : (
            watches.map((item) => (
              <div key={item.id} className="dp-mobile-watch">
                <span className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${item.tone === "danger" ? "bg-danger" : "bg-warning"}`} />
                <div className="min-w-0 flex-1">
                  <p className="text-[10.5px] font-semibold leading-tight text-foreground">{item.order}</p>
                  <p className="mt-0.5 truncate text-[8.5px] text-muted">{item.label}</p>
                </div>
                <button
                  type="button"
                  onClick={() => onCancel(item.id)}
                  className="focus-ring rounded-full p-1 text-subtle hover:text-danger"
                  aria-label={`Cancel watch on ${item.order}`}
                >
                  <Icon name="close" size={11} />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      <div>
        <div className="dp-context-label">
          <span className="dp-eyebrow">Watch history</span>
        </div>
        <div className="space-y-1.5">
          {WATCH_HISTORY.map((item) => (
            <div key={item.id} className="dp-mobile-watch">
              <Icon name="history" size={11} className="shrink-0 text-subtle" />
              <div className="min-w-0 flex-1">
                <p className="text-[10px] font-medium leading-tight text-foreground">{item.order}</p>
                <p className="mt-0.5 truncate text-[8px] text-muted">{item.label}</p>
              </div>
              <span className="text-[8px] text-subtle">{item.time}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function MobileApp({ theme, onTheme }) {
  const [tab, setTab] = useState("ask");
  const [drawer, setDrawer] = useState(null);
  const [overviewTab, setOverviewTab] = useState("morning");
  const [watches, setWatches] = useState(ACTIVE_WATCHES);
  const [input, setInput] = useState("");
  const [focusSignal, setFocusSignal] = useState(0);
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState([]);
  const timerRef = useRef(null);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  function fill(text) {
    if (input.trim() && input.trim() !== text) {
      if (!window.confirm("Replace your current draft with this suggestion?")) return;
    }
    setInput(text);
    setTab("ask");
    setFocusSignal((n) => n + 1);
  }

  function send() {
    const text = input.trim();
    if (!text || busy) return;
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setBusy(true);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setMessages((prev) => [...prev, { role: "assistant", content: CANNED_REPLY }]);
      setBusy(false);
    }, 2400);
  }

  function stop() {
    if (!busy) return;
    clearTimeout(timerRef.current);
    setBusy(false);
    setMessages((prev) => [...prev, { role: "assistant", content: STOPPED_REPLY, stopped: true }]);
  }

  function cancelWatch(id) {
    setWatches((prev) => prev.filter((item) => item.id !== id));
  }

  const hasMessages = messages.length > 0;

  return (
    <div className="dp-device-screen">
      <PhoneStatus />
      <MobileTop
        hasAlerts={TRIGGERED_ALERTS.length > 0}
        onMenu={() => setDrawer("history")}
        onBell={() => setDrawer("alerts")}
      />

      <div className="dp-mobile-content">
        {tab === "overview" && <MobileOverview tab={overviewTab} onTab={setOverviewTab} />}
        {tab === "settings" && <MobileSettings theme={theme} onTheme={onTheme} />}
        {tab === "ask" && (hasMessages ? <MobileChat messages={messages} busy={busy} /> : <MobileWelcome onFill={fill} />)}
      </div>

      {tab === "ask" && (
        <div className="dp-mobile-composer-wrap">
          <Composer
            value={input}
            onChange={setInput}
            onSubmit={send}
            busy={busy}
            onStop={stop}
            focusSignal={focusSignal}
            compact
            placeholder="Ask anything about the factory…"
          />
        </div>
      )}

      <div className="dp-mobile-nav">
        <button
          type="button"
          className={`dp-mobile-nav-item focus-ring ${tab === "overview" ? "is-active" : ""}`}
          onClick={() => setTab("overview")}
          aria-current={tab === "overview" ? "page" : undefined}
        >
          <span className="dp-mobile-nav-icon">
            <Icon name="grid" size={16} />
          </span>
          <span>Overview</span>
        </button>

        <div className="dp-mobile-nav-center">
          <button
            type="button"
            className="dp-mobile-fab-btn focus-ring"
            onClick={() => setTab("ask")}
            aria-label="Ask AI"
            aria-current={tab === "ask" ? "page" : undefined}
          >
            <Icon name="chat" size={22} />
          </button>
          <span className="dp-mobile-fab-label">Ask AI</span>
        </div>

        <button
          type="button"
          className={`dp-mobile-nav-item focus-ring ${tab === "settings" ? "is-active" : ""}`}
          onClick={() => setTab("settings")}
          aria-current={tab === "settings" ? "page" : undefined}
        >
          <span className="dp-mobile-nav-icon">
            <Icon name="settings" size={16} />
          </span>
          <span>Settings</span>
        </button>
      </div>

      {drawer && (
        <>
          <div className="dp-drawer-scrim" onClick={() => setDrawer(null)} aria-hidden="true" />
          <div className="dp-drawer" role="dialog" aria-label={drawer === "alerts" ? "Alerts" : "History"}>
            <div className="dp-drawer-head">
              <div className="min-w-0">
                <p className="dp-context-title">{drawer === "alerts" ? "Alerts" : "History"}</p>
                <p className="dp-context-sub truncate">Factory 12 · today</p>
              </div>
              <button type="button" className="dp-icon-btn h-8 w-8 focus-ring" aria-label="Close drawer" onClick={() => setDrawer(null)}>
                <Icon name="close" size={14} />
              </button>
            </div>
            <div className="dp-drawer-scroll">
              {drawer === "alerts" ? (
                <AlertsDrawerBody watches={watches} onCancel={cancelWatch} />
              ) : (
                <div className="space-y-1">
                  <button
                    type="button"
                    onClick={() => {
                      setDrawer(null);
                      setTab("ask");
                      setMessages([]);
                    }}
                    className="dp-btn dp-btn-primary focus-ring mb-2 h-9 w-full"
                  >
                    <Icon name="plus" size={13} />
                    New conversation
                  </button>
                  {CONVERSATIONS.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => {
                        setDrawer(null);
                        setTab("ask");
                        setMessages([]);
                      }}
                      className="dp-conv-row focus-ring"
                    >
                      <span className="dp-conv-line" />
                      <span className="min-w-0 flex-1 text-left">
                        <span className="block truncate text-[10.5px] font-medium text-foreground">{item.title}</span>
                        <span className="mt-0.5 block truncate text-[8.5px] text-muted">{item.preview}</span>
                      </span>
                      <span className="text-[8px] text-subtle">{item.time}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Device({ width, label, hint, theme, onTheme }) {
  return (
    <div className="flex min-w-0 flex-col items-center gap-3">
      <div className="flex items-center gap-2">
        <span className="dp-eyebrow">{label}</span>
        <span className="h-px w-8 bg-line" />
        <span className="text-[10px] text-subtle">{hint}</span>
      </div>
      <div className="dp-device" style={{ maxWidth: width + 20 }}>
        <MobileApp theme={theme} onTheme={onTheme} />
      </div>
    </div>
  );
}

export default function MobileAskAI({ theme, onTheme }) {
  return (
    <div className="space-y-5">
      <div className="dp-panel flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div>
          <p className="dp-eyebrow">Mobile</p>
          <p className="mt-1 text-[13px] font-semibold text-foreground">Three destinations, one calm surface</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="dp-chip">360 px</span>
          <span className="dp-chip">390 px</span>
          <span className="dp-chip">Center Ask AI · safe-area aware</span>
        </div>
      </div>

      <div className="grid gap-8 xl:grid-cols-2">
        <Device width={360} label="360 px" hint="Ask AI · welcome" theme={theme} onTheme={onTheme} />
        <Device width={390} label="390 px" hint="Tap the bell for alerts" theme={theme} onTheme={onTheme} />
      </div>
    </div>
  );
}
