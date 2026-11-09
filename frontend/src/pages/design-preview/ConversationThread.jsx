import { useState } from "react";
import { AiOrb, Icon, Pill, ThroughputChart } from "./bits.jsx";
import {
  CLARIFICATION_OPTIONS,
  GO_DEEPER,
  ORDER_ROWS,
  TRACE_SOURCES,
  TRACE_STEPS,
} from "./mockData.js";

const STATUS_TONE = {
  danger: "dp-tone-danger",
  warning: "dp-tone-warning",
  accent: "dp-tone-accent",
  success: "dp-tone-success",
};

function UserMessage({ children }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[min(86%,520px)]">
        <div className="dp-user-bubble">{children}</div>
        <div className="mt-1 flex items-center justify-end gap-2 text-[9px] text-subtle">
          <span>09:41</span>
          <button type="button" className="focus-ring rounded-full p-0.5 hover:text-foreground" aria-label="Copy question">
            <Icon name="copy" size={11} />
          </button>
        </div>
      </div>
    </div>
  );
}

function AssistantHeader({ tools = 3 }) {
  return (
    <div className="flex items-center gap-2.5">
      <AiOrb size={30} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-[11px] font-semibold text-foreground">Co-Pilot</p>
          <span className="dp-chip">
            <Icon name="spark" size={10} />
            {tools} tools
          </span>
          <span className="text-[9px] text-subtle">Just now</span>
        </div>
      </div>
      <button type="button" className="dp-icon-btn h-7 w-7 focus-ring" aria-label="Copy answer" title="Static preview">
        <Icon name="copy" size={12} />
      </button>
    </div>
  );
}

function InsightSummary() {
  return (
    <div className="dp-insight">
      <div className="flex items-start gap-3">
        <span className="dp-icon-tile dp-tone-danger">
          <Icon name="alert" size={16} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[12px] font-semibold text-foreground">3 orders need attention</p>
          <p className="mt-0.5 text-[9.5px] text-muted">Estimated exposure $68k · 2 orders due within 4 days</p>
        </div>
        <Pill tone="danger" dot>High</Pill>
      </div>
      <div className="mt-3 grid grid-cols-3 divide-x divide-line/60 rounded-xl border border-line/60 bg-surface/50 py-2.5">
        <div className="px-3 text-center">
          <p className="tabular text-[15px] font-semibold leading-none text-foreground">1,200</p>
          <p className="mt-1 text-[8px] text-muted">pieces at risk</p>
        </div>
        <div className="px-3 text-center">
          <p className="tabular text-[15px] font-semibold leading-none text-foreground">2</p>
          <p className="mt-1 text-[8px] text-muted">due ≤ 4 days</p>
        </div>
        <div className="px-3 text-center">
          <p className="text-[13px] font-semibold leading-none text-foreground">Assembly</p>
          <p className="mt-1 text-[8px] text-muted">constraint stage</p>
        </div>
      </div>
    </div>
  );
}

function RiskTable() {
  return (
    <div className="dp-data-card overflow-hidden">
      <div className="flex items-start justify-between gap-3 border-b border-line/60 px-4 py-3">
        <div className="min-w-0">
          <p className="text-[11.5px] font-semibold text-foreground">TrendCart risk snapshot</p>
          <p className="mt-0.5 text-[8.5px] text-muted">Static sample · orders.csv · production_log.csv</p>
        </div>
        <button type="button" className="dp-icon-btn h-7 w-7 focus-ring" aria-label="Table actions" title="Static preview">
          <Icon name="more" size={13} />
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] border-collapse text-left">
          <thead>
            <tr className="border-b border-line/60 bg-surfaceMuted/40 text-[8px] uppercase tracking-[0.12em] text-muted">
              <th className="px-4 py-2 font-semibold">Order</th>
              <th className="px-3 py-2 font-semibold">Due</th>
              <th className="px-3 py-2 font-semibold">Stage</th>
              <th className="px-3 py-2 font-semibold">Pieces</th>
              <th className="px-4 py-2 text-right font-semibold">Status</th>
            </tr>
          </thead>
          <tbody>
            {ORDER_ROWS.map((row) => (
              <tr key={row.order} className="border-b border-line/50 last:border-0">
                <td className="px-4 py-2.5 text-[10.5px] font-semibold text-foreground">{row.order}</td>
                <td className="px-3 py-2.5 text-[10px] text-muted">{row.due}</td>
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-foreground">{row.stage}</span>
                    <span className="hidden h-1 w-10 overflow-hidden rounded-full bg-surfaceMuted sm:block">
                      <span
                        className={`block h-full rounded-full ${
                          row.tone === "danger"
                            ? "bg-danger"
                            : row.tone === "warning"
                              ? "bg-warning"
                              : row.tone === "success"
                                ? "bg-success"
                                : "bg-accent"
                        }`}
                        style={{ width: `${row.progress}%` }}
                      />
                    </span>
                  </div>
                </td>
                <td className="tabular px-3 py-2.5 text-[10px] text-muted">{row.pieces}</td>
                <td className="px-4 py-2.5 text-right">
                  <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[8.5px] font-semibold ${STATUS_TONE[row.tone]}`}>
                    <span className="h-1 w-1 rounded-full bg-current" />
                    {row.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ChartCard() {
  return (
    <div className="dp-data-card overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line/60 px-4 py-3">
        <div className="min-w-0">
          <p className="text-[11.5px] font-semibold text-foreground">Assembly output vs. baseline</p>
          <p className="mt-0.5 text-[8.5px] text-muted">Completed pieces · last 7 working days</p>
        </div>
        <div className="flex items-center gap-3 text-[8.5px] text-muted">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            Actual
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-0 w-3.5 border-t border-dashed border-subtle" />
            Median
          </span>
        </div>
      </div>
      <div className="px-2 py-2">
        <ThroughputChart />
      </div>
    </div>
  );
}

function ClarificationCard() {
  const [picked, setPicked] = useState("revenue");
  return (
    <div className="dp-clarify p-4">
      <div className="flex items-start gap-2.5">
        <span className="dp-icon-tile dp-icon-tile-sm dp-tone-accent">
          <Icon name="spark" size={13} />
        </span>
        <div className="min-w-0">
          <p className="text-[11px] font-semibold text-foreground">Before I rank these — what matters most?</p>
          <p className="mt-0.5 text-[9.5px] text-muted">I can order the list by exposure, urgency, or the stage that is constrained.</p>
        </div>
      </div>
      <div className="mt-3 grid gap-1.5 sm:grid-cols-3">
        {CLARIFICATION_OPTIONS.map((option) => {
          const active = picked === option.id;
          return (
            <button
              key={option.id}
              type="button"
              onClick={() => setPicked(option.id)}
              className={`flex items-start gap-2 rounded-xl border px-3 py-2 text-left transition-colors ${
                active
                  ? "border-accent-300/70 bg-accentSoft/50"
                  : "border-line/80 bg-surface/60 hover:border-accent-300/60 hover:bg-surface"
              }`}
            >
              <span
                className={`mt-0.5 flex h-3.5 w-3.5 flex-shrink-0 items-center justify-center rounded-full border ${
                  active ? "border-accent bg-accent text-white" : "border-lineStrong"
                }`}
              >
                {active && <Icon name="check" size={8} strokeWidth={2.6} />}
              </span>
              <span className="min-w-0">
                <span className="block text-[10px] font-semibold leading-snug text-foreground">{option.label}</span>
                <span className="mt-0.5 block text-[8.5px] text-muted">{option.hint}</span>
              </span>
            </button>
          );
        })}
      </div>
      <div className="mt-3 flex items-center justify-between gap-3">
        <span className="text-[8.5px] text-subtle">You can change this later.</span>
        <button type="button" className="dp-btn dp-btn-primary" title="Static preview">
          Continue
          <Icon name="arrowRight" size={11} />
        </button>
      </div>
    </div>
  );
}

function ProposedAction() {
  const [decision, setDecision] = useState(null);
  return (
    <div className="dp-action p-4">
      <div className="flex items-start gap-3">
        <span className="dp-icon-tile dp-tone-accent">
          <Icon name="bell" size={15} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[11.5px] font-semibold text-foreground">Create a watch on ORD-120</p>
            <Pill tone="accent">Proposed</Pill>
          </div>
          <p className="mt-1 text-[9.5px] leading-4 text-muted">
            Check every working day until the order moves past Assembly, or 22 Aug. The watch appears in Active
            Watches and can be cancelled later.
          </p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-line/60 pt-3">
        <span className="inline-flex items-center gap-1 text-[8.5px] text-subtle">
          <Icon name="shield" size={10} />
          Nothing is saved until you confirm. Email is never sent.
        </span>
        {decision === "confirmed" ? (
          <Pill tone="success" dot>Watch saved · #18</Pill>
        ) : decision === "dismissed" ? (
          <span className="text-[9px] text-muted">Dismissed. Nothing was saved.</span>
        ) : (
          <div className="flex items-center gap-1.5">
            <button type="button" className="dp-btn dp-btn-ghost" onClick={() => setDecision("dismissed")}>
              Dismiss
            </button>
            <button type="button" className="dp-btn dp-btn-primary" onClick={() => setDecision("confirmed")}>
              <Icon name="check" size={11} strokeWidth={2.4} />
              Confirm action
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function WhyTrace() {
  const [open, setOpen] = useState(true);
  return (
    <div className="dp-trace p-4">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="focus-ring flex w-full items-center gap-2.5 text-left"
      >
        <span className="dp-icon-tile dp-icon-tile-sm dp-tone-neutral">
          <Icon name="layers" size={13} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[11px] font-semibold text-foreground">Why this answer?</span>
          <span className="mt-0.5 block text-[8.5px] text-muted">
            {TRACE_STEPS.length} steps · {TRACE_SOURCES.length} sources · stored with this turn
          </span>
        </span>
        <Icon name="chevronDown" size={13} className={`text-subtle transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="mt-4 space-y-3.5 border-t border-line/60 pt-4">
          {TRACE_STEPS.map((step, index) => (
            <div key={step.title} className="dp-trace-step">
              <span className="dp-trace-index">{index + 1}</span>
              <p className="text-[10px] font-semibold leading-snug text-foreground">{step.title}</p>
              <p className="mt-1 text-[9.5px] leading-4 text-muted">{step.body}</p>
            </div>
          ))}
          <div className="flex flex-wrap gap-1.5 pt-1">
            {TRACE_SOURCES.map((source) => (
              <span
                key={source.name}
                className="inline-flex items-center gap-1.5 rounded-full border border-line/80 bg-surface/70 px-2 py-1 text-[8.5px] text-muted"
              >
                <Icon name="database" size={10} />
                <span className="font-semibold text-foreground">{source.name}</span>
                <span className="text-subtle">{source.meta}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function GoDeeper({ onFill }) {
  return (
    <div className="dp-go-deeper">
      <div className="dp-go-deeper-head">
        <Icon name="spark" size={11} />
        Go deeper
        <span className="ml-1 font-normal tracking-normal normal-case text-subtle">· fills the composer</span>
      </div>
      <div className="dp-go-chips">
        {GO_DEEPER.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onFill(item.title)}
            className="dp-go-chip focus-ring"
            title="Fill the composer — does not send"
          >
            <Icon name="plus" size={11} className="dp-go-plus" />
            {item.title}
          </button>
        ))}
      </div>
    </div>
  );
}

function StreamingBubble({ content, stopped }) {
  if (!content && !stopped) {
    return (
      <div className="dp-stream-note">
        <span className="dp-pulse-dot" />
        Working through the factory tools…
      </div>
    );
  }
  return (
    <div>
      <div className="dp-prose pl-0.5">
        <p>
          {content}
          {!stopped && <span className="dp-pulse-dot ml-1 inline-block align-middle" />}
        </p>
      </div>
      {stopped && (
        <span className="dp-stopped">
          <Icon name="stop" size={9} />
          Stopped by you · preview only
        </span>
      )}
    </div>
  );
}

/**
 * Shared conversation surface. The static seed turn shows every block the real
 * product renders (markdown, chart, table, clarification, proposed action, why
 * trace) and ends with Go Deeper chips that scroll with the message. Any live
 * (mock) messages appended by the composer render below the seed.
 */
export default function ConversationThread({ messages = [], busy = false, onGoDeeper }) {
  return (
    <div className="mx-auto w-full max-w-[760px] space-y-5">
      <UserMessage>Which orders are at risk right now? Focus on the TrendCart account.</UserMessage>

      <div className="dp-rise">
        <AssistantHeader tools={3} />
        <div className="mt-2.5 space-y-4">
          <InsightSummary />
          <div className="dp-prose pl-0.5">
            <p>
              I found <strong>3 TrendCart orders</strong> that need attention this morning. The common constraint is
              Assembly: output has stayed below 70% of its own 30-day median for three working days.
            </p>
            <ol>
              <li>
                <strong>ORD-120</strong> — 1,200 hoodies, due 22 Aug. Assembly has not moved since 15 Aug.
              </li>
              <li>
                <strong>ORD-118</strong> — 640 hoodies, due 21 Aug. Cutting is 2.4 days behind plan.
              </li>
              <li>
                <strong>ORD-115</strong> — 900 hoodies, due 25 Aug. Fabric is on site but not yet in Cutting.
              </li>
            </ol>
            <p>
              The largest exposure is <strong>ORD-120</strong> at roughly <strong>$42k</strong>. If Assembly recovers
              to 390 pieces/day by 20 Aug, ORD-118 can still make its date.
            </p>
          </div>
          <ChartCard />
          <RiskTable />
          <ClarificationCard />
          <ProposedAction />
          <WhyTrace />
          <GoDeeper onFill={onGoDeeper} />
        </div>
      </div>

      {messages.map((msg, index) =>
        msg.role === "user" ? (
          <UserMessage key={`u-${index}`}>{msg.content}</UserMessage>
        ) : (
          <div key={`a-${index}`} className="dp-rise">
            <AssistantHeader tools={0} />
            <div className="mt-2.5">
              <StreamingBubble content={msg.content} stopped={msg.stopped} />
            </div>
          </div>
        ),
      )}

      {busy && <StreamingBubble content="" />}
    </div>
  );
}
