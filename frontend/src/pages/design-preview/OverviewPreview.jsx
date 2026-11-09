import { useState } from "react";
import { Icon, Pill, RiskLegend, RiskStack, Sparkline, ThroughputChart } from "./bits.jsx";
import {
  METRICS,
  MORNING_BRIEFING,
  TOP_ISSUES,
  WEEKLY_BRIEFING,
} from "./mockData.js";

const DELTA_ICON = {
  success: "trendUp",
  danger: "trendDown",
  warning: "alert",
  accent: "trendDown",
};

function MetricCard({ metric }) {
  return (
    <div className="dp-card p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="dp-eyebrow">{metric.label}</p>
          <p className="tabular mt-2 text-[24px] font-semibold leading-none tracking-[-0.035em] text-foreground">
            {metric.value}
          </p>
        </div>
        <span className={`dp-icon-tile dp-icon-tile-sm dp-tone-${metric.tone}`}>
          <Icon name={metric.icon} size={14} />
        </span>
      </div>
      <div className="mt-3 flex items-end justify-between gap-2">
        <div className="min-w-0">
          <span
            className={`inline-flex items-center gap-1 text-[10px] font-semibold ${
              metric.tone === "success"
                ? "text-success"
                : metric.tone === "danger"
                  ? "text-danger"
                  : metric.tone === "warning"
                    ? "text-warning"
                    : "text-accentText"
            }`}
          >
            <Icon name={DELTA_ICON[metric.tone]} size={11} />
            {metric.delta}
          </span>
          <p className="mt-1 text-[8.5px] text-subtle">vs last week</p>
        </div>
        <div className="w-[84px] shrink-0">
          <Sparkline values={metric.spark} tone={metric.tone} />
        </div>
      </div>
    </div>
  );
}

function BriefingCard({ tab }) {
  const data = tab === "week" ? WEEKLY_BRIEFING : MORNING_BRIEFING;

  return (
    <div className="dp-card overflow-hidden">
      <div className="dp-briefing-hero">
        <div className="relative z-10 flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="dp-briefing-muted text-[8.5px] font-semibold uppercase tracking-[0.18em]">
              Factory briefing
            </p>
            <h3 className="dp-briefing-title mt-1.5 text-[22px] font-semibold leading-tight tracking-[-0.02em]">
              {data.title}
            </h3>
            <p className="dp-briefing-muted mt-1 text-[10px]">{data.date}</p>
          </div>
          <span className="dp-briefing-icon flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-2xl">
            <Icon name={tab === "week" ? "layers" : "sun"} size={19} />
          </span>
        </div>
        <div className="relative z-10 mt-4 flex flex-wrap items-center gap-1.5">
          <span className="dp-briefing-chip inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[8.5px] font-medium">
            <Icon name="shield" size={10} />
            Grounded in 4 sources
          </span>
          <span className="dp-briefing-chip inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[8.5px] font-medium">
            {tab === "week" ? "Weekly roll-up" : "Generated 07:30"}
          </span>
        </div>
      </div>

      <div className="p-5">
        <p className="text-[11.5px] leading-5 text-muted">{data.summary}</p>

        <div className="mt-4 space-y-3">
          {data.points.map((point) => (
            <div key={point.title} className="flex items-start gap-3">
              <span className={`dp-icon-tile dp-icon-tile-sm dp-tone-${point.tone}`}>
                <Icon name={point.icon} size={13} />
              </span>
              <div className="min-w-0">
                <p className="text-[11px] font-semibold leading-snug text-foreground">{point.title}</p>
                <p className="mt-0.5 text-[10px] leading-4 text-muted">{point.body}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-5 flex items-center justify-between gap-3 border-t border-line/60 pt-3">
          <span className="text-[8.5px] text-subtle">Updated 07:30 · factory date</span>
          <button type="button" className="inline-flex items-center gap-1 text-[10px] font-semibold text-accentText" title="Static preview">
            Open full briefing
            <Icon name="arrowRight" size={11} />
          </button>
        </div>
      </div>
    </div>
  );
}

function IssuesCard() {
  return (
    <div className="dp-card flex flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="dp-eyebrow">Discovery</p>
          <h3 className="mt-1 text-[15px] font-semibold tracking-[-0.02em] text-foreground">Top issues</h3>
          <p className="mt-0.5 text-[10px] text-muted">Ranked by production exposure, not due date.</p>
        </div>
        <Pill tone="danger" dot>
          {TOP_ISSUES.length} open
        </Pill>
      </div>

      <div className="mt-3 min-h-0 flex-1 divide-y divide-line/60">
        {TOP_ISSUES.map((issue) => (
          <button
            key={issue.title}
            type="button"
            className="group flex w-full items-start gap-3 py-3 text-left"
            title="Static preview"
          >
            <span
              className={`mt-0.5 inline-flex h-5 w-7 flex-shrink-0 items-center justify-center rounded-md text-[8.5px] font-bold ${
                issue.priority === "P1"
                  ? "bg-dangerSoft text-danger"
                  : issue.priority === "P2"
                    ? "bg-warningSoft text-warning"
                    : "bg-surfaceMuted text-muted"
              }`}
            >
              {issue.priority}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[11px] font-semibold text-foreground">{issue.title}</span>
              <span className="mt-0.5 block truncate text-[9px] text-muted">{issue.meta}</span>
              <span className="mt-1 inline-flex items-center gap-1 text-[8.5px] text-subtle">
                <span className="h-1 w-1 rounded-full bg-current" />
                {issue.detail}
              </span>
            </span>
            <span className="flex flex-shrink-0 flex-col items-end gap-1.5">
              <Pill tone={issue.tone} dot>
                {issue.risk}
              </Pill>
              <Icon
                name="arrowRight"
                size={12}
                className="text-subtle transition-transform group-hover:translate-x-0.5"
              />
            </span>
          </button>
        ))}
      </div>

      <div className="mt-3 flex items-center justify-between border-t border-line/60 pt-3">
        <span className="text-[8.5px] text-subtle">Last scanned at 07:30</span>
        <button type="button" className="inline-flex items-center gap-1 text-[10px] font-semibold text-accentText" title="Static preview">
          View all 6 issues
          <Icon name="arrowRight" size={11} />
        </button>
      </div>
    </div>
  );
}

function ThroughputCard() {
  return (
    <div className="dp-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="dp-eyebrow">Production</p>
          <h3 className="mt-1 text-[15px] font-semibold tracking-[-0.02em] text-foreground">
            Stage throughput vs. baseline
          </h3>
          <p className="mt-0.5 text-[10px] text-muted">Assembly · completed pieces per working day</p>
        </div>
        <div className="flex items-center gap-3 text-[9px] text-muted">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            Actual
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-0 w-4 border-t border-dashed border-subtle" />
            30-day median
          </span>
        </div>
      </div>

      <div className="mt-3">
        <ThroughputChart />
      </div>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-line/60 pt-3">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-warningSoft px-2 py-0.5 text-[9px] font-medium text-warning">
          <Icon name="alert" size={10} />
          4 of 7 days below the 70% threshold
        </span>
        <span className="text-[8.5px] text-subtle">production_log.csv · 30 working days</span>
      </div>
    </div>
  );
}

function RiskCard() {
  return (
    <div className="dp-card flex flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="dp-eyebrow">Exposure</p>
          <h3 className="mt-1 text-[15px] font-semibold tracking-[-0.02em] text-foreground">Risk mix</h3>
          <p className="mt-0.5 text-[10px] text-muted">51 open orders · today</p>
        </div>
        <span className="dp-icon-tile dp-icon-tile-sm dp-tone-danger">
          <Icon name="alert" size={14} />
        </span>
      </div>

      <div className="mt-4">
        <RiskStack />
      </div>
      <div className="mt-4 flex-1">
        <RiskLegend />
      </div>

      <div className="mt-4 rounded-2xl border border-line/70 bg-surfaceMuted/40 p-3">
        <p className="dp-eyebrow">How risk is calculated</p>
        <p className="mt-1 text-[9.5px] leading-4 text-muted">
          An order is flagged when its current stage falls below 70% of its own 30-day
          median for three consecutive working days.
        </p>
      </div>
    </div>
  );
}

export default function OverviewPreview({ tab: controlledTab, onTabChange, embedded = false }) {
  const [internalTab, setInternalTab] = useState("morning");
  const tab = controlledTab ?? internalTab;
  const setTab = onTabChange ?? setInternalTab;

  return (
    <div className={embedded ? "space-y-4 p-4 md:p-5" : "space-y-4"}>
      <div className="dp-panel px-5 py-5 md:px-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="dp-eyebrow">Insights · Factory 12</p>
            <h1 className="mt-1.5 text-[26px] font-semibold leading-tight tracking-[-0.035em] text-foreground">
              Overview
            </h1>
            <p className="mt-1 text-[11.5px] text-muted">
              Top issues with the morning and weekly factory briefing.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="dp-segmented" role="group" aria-label="Briefing range">
              <button
                type="button"
                className={tab === "morning" ? "is-active" : ""}
                aria-pressed={tab === "morning"}
                onClick={() => setTab("morning")}
              >
                Morning
              </button>
              <button
                type="button"
                className={tab === "week" ? "is-active" : ""}
                aria-pressed={tab === "week"}
                onClick={() => setTab("week")}
              >
                Weekly
              </button>
            </div>
            <button type="button" className="dp-pill" title="Static preview">
              <Icon name="refresh" size={12} />
              Refresh
            </button>
          </div>
        </div>

        <div className="mt-5 grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
          {METRICS.map((metric) => (
            <MetricCard key={metric.label} metric={metric} />
          ))}
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.08fr_0.92fr]">
        <BriefingCard tab={tab} />
        <IssuesCard />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.34fr_0.66fr]">
        <ThroughputCard />
        <RiskCard />
      </div>
    </div>
  );
}
