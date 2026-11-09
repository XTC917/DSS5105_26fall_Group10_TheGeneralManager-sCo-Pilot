import { useId, useState } from "react";
import { RISK_MIX, THROUGHPUT } from "./mockData.js";

const ICONS = {
  chat: (
    <path d="M5 6.5A2.5 2.5 0 0 1 7.5 4h9A2.5 2.5 0 0 1 19 6.5v6A2.5 2.5 0 0 1 16.5 15H11l-4 3.5V15H7.5A2.5 2.5 0 0 1 5 12.5v-6z" />
  ),
  grid: (
    <>
      <rect x="3" y="3" width="8" height="8" rx="2" />
      <rect x="13" y="3" width="8" height="5" rx="2" />
      <rect x="13" y="10" width="8" height="11" rx="2" />
      <rect x="3" y="13" width="8" height="8" rx="2" />
    </>
  ),
  database: (
    <>
      <ellipse cx="12" cy="6" rx="7" ry="3" />
      <path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
    </>
  ),
  users: (
    <>
      <circle cx="9" cy="8" r="3" />
      <path d="M3 19c0-3 2.7-5 6-5s6 2 6 5M16 5a3 3 0 1 1 0 6M21 19c0-2.5-2-4.5-5-5" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </>
  ),
  history: (
    <>
      <path d="M4 12a8 8 0 1 0 2.3-5.7L4 8.6M4 4v4.6h4.6" />
      <path d="M12 8v4.4l3 1.8" />
    </>
  ),
  bell: (
    <>
      <path d="M12 3a6 6 0 0 0-6 6v2.2c0 .7-.2 1.4-.6 2L4.2 15.4A1 1 0 0 0 5 17h14a1 1 0 0 0 .8-1.6L18.6 13.2c-.4-.6-.6-1.3-.6-2V9a6 6 0 0 0-6-6z" />
      <path d="M10 17a2 2 0 0 0 4 0" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-3.5-3.5" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  arrowUp: <path d="M12 19V5M6 11l6-6 6 6" />,
  arrowRight: <path d="M5 12h14M13 6l6 6-6 6" />,
  arrowLeft: <path d="M19 12H5M11 18l-6-6 6-6" />,
  spark: <path d="M12 3l1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3z" />,
  pin: (
    <path d="M9 3.5h6l-.8 6.2H17L12 20.5 7 9.7h2.8L9 3.5z" />
  ),
  chevronDown: <path d="M6 9l6 6 6-6" />,
  check: <path d="M5 12.5l4.2 4.2L19 7" />,
  shield: (
    <>
      <path d="M12 3l7 2.5v5.3c0 4.3-2.8 7.6-7 9.2-4.2-1.6-7-4.9-7-9.2V5.5L12 3z" />
      <path d="M9 11.8l2 2 4-4.2" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7v5.3l3.2 1.9" />
    </>
  ),
  trendUp: (
    <>
      <path d="M4 16l5.2-5.2 3.1 3.1L20 6.2" />
      <path d="M15 6.2h5v5" />
    </>
  ),
  trendDown: (
    <>
      <path d="M4 8l5.2 5.2 3.1-3.1L20 17.8" />
      <path d="M15 17.8h5v-5" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M19.1 4.9l-1.8 1.8M6.7 17.3l-1.8 1.8" />
    </>
  ),
  zap: <path d="M13 2.5L5 13h5.5L11 21.5 19 11h-5.5L13 2.5z" />,
  alert: (
    <>
      <path d="M12 3.2L21 19H3L12 3.2z" />
      <path d="M12 9v4.4M12 16.8v.2" />
    </>
  ),
  package: (
    <>
      <path d="M4 7.5L12 3l8 4.5v9L12 21l-8-4.5v-9z" />
      <path d="M4 7.5l8 4.5 8-4.5M12 12v9" />
    </>
  ),
  layers: (
    <>
      <path d="M12 3l8 4.5-8 4.5-8-4.5L12 3z" />
      <path d="M4 12l8 4.5 8-4.5M4 16.5L12 21l8-4.5" />
    </>
  ),
  more: (
    <>
      <circle cx="5" cy="12" r="1.6" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" />
      <circle cx="19" cy="12" r="1.6" fill="currentColor" stroke="none" />
    </>
  ),
  copy: (
    <>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15V5a2 2 0 0 1 2-2h10" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 11a8 8 0 0 0-14.7-4L4 9" />
      <path d="M4 4v5h5M4 13a8 8 0 0 0 14.7 4L20 15" />
      <path d="M20 20v-5h-5" />
    </>
  ),
  filter: <path d="M4 6h16M7 12h10M10 18h4" />,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  panelLeft: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2.4" />
      <path d="M9 4v16" />
    </>
  ),
  panelRight: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2.4" />
      <path d="M15 4v16" />
    </>
  ),
  stop: <rect x="6.5" y="6.5" width="11" height="11" rx="2.4" fill="currentColor" stroke="none" />,
  logout: (
    <>
      <path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3" />
      <path d="M10 8l4 4-4 4M14 12H3" />
    </>
  ),
  key: (
    <>
      <circle cx="8" cy="15" r="4" />
      <path d="M11 12l8-8M16 4l4 4M14.5 5.5l3 3" />
    </>
  ),
  monitor: (
    <>
      <rect x="3" y="4" width="18" height="12" rx="2" />
      <path d="M8 20h8M12 16v4" />
    </>
  ),
  sliders: (
    <>
      <path d="M4 8h10M18 8h2M4 16h2M10 16h10" />
      <circle cx="16" cy="8" r="2" />
      <circle cx="8" cy="16" r="2" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8" r="3.4" />
      <path d="M5 20c0-3.4 3.1-5.6 7-5.6s7 2.2 7 5.6" />
    </>
  ),
  edit: (
    <>
      <path d="M4 20h4L19 9l-4-4L4 16v4z" />
      <path d="M14 6l4 4" />
    </>
  ),
  external: (
    <>
      <path d="M14 4h6v6M20 4l-9 9" />
      <path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
    </>
  ),
  refreshSmall: <path d="M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5" />,
};

export function Icon({ name, size = 18, className = "", strokeWidth = 1.7 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {ICONS[name] || ICONS.spark}
    </svg>
  );
}

export function BrandMark({ size = 36 }) {
  return (
    <span className="dp-brand" style={{ width: size, height: size }} aria-hidden="true">
      <svg width={size * 0.56} height={size * 0.56} viewBox="0 0 24 24" fill="none">
        <path
          d="M16.5 6.3c-.7-1.1-2.2-1.8-4-1.8-2.6 0-4.5 1.3-4.5 3.4 0 2.2 1.9 3 4.4 3.6 2.3.5 4.1 1.3 4.1 3.5 0 2.1-1.9 3.4-4.7 3.4-2.2 0-4-.9-4.8-2.4"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
    </span>
  );
}

export function Avatar({ initials = "MC", size = 30, className = "" }) {
  return (
    <span
      className={`inline-flex flex-shrink-0 items-center justify-center rounded-full border border-line bg-surfaceMuted font-semibold text-foreground ${className}`}
      style={{ width: size, height: size, fontSize: size * 0.34 }}
      aria-hidden="true"
    >
      {initials}
    </span>
  );
}

const PILL_TONES = {
  neutral: "dp-tone-neutral",
  accent: "dp-tone-accent",
  danger: "dp-tone-danger",
  warning: "dp-tone-warning",
  success: "dp-tone-success",
};

export function Pill({ tone = "neutral", dot = false, children, className = "" }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[9.5px] font-semibold leading-none ${PILL_TONES[tone] || PILL_TONES.neutral} ${className}`}
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

export function AiOrb({ size = 112, className = "" }) {
  return (
    <span className={`dp-orb ${className}`} style={{ width: size, height: size }} aria-hidden="true">
      <span className="dp-orb-star">
        <Icon name="spark" size={size * 0.2} strokeWidth={1.5} />
      </span>
    </span>
  );
}

const SPARK_TONES = {
  danger: "rgb(var(--danger))",
  warning: "rgb(var(--warning))",
  success: "rgb(var(--success))",
  accent: "rgb(var(--accent-500))",
  neutral: "rgb(var(--muted))",
};

export function Sparkline({ values, tone = "accent", className = "" }) {
  const rawId = useId();
  const id = `spark-${rawId.replace(/[^a-zA-Z0-9]/g, "")}`;
  const width = 132;
  const height = 38;
  const pad = 3;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = values.map((value, index) => {
    const x = pad + (index * (width - pad * 2)) / (values.length - 1);
    const y = height - pad - ((value - min) / span) * (height - pad * 2);
    return [x, y];
  });
  const line = points.map(([x, y], index) => `${index ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const area = `${line} L ${width - pad} ${height - pad} L ${pad} ${height - pad} Z`;
  const color = SPARK_TONES[tone] || SPARK_TONES.accent;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={`dp-metric-spark ${className}`}
      style={{ width: "100%", height: 38 }}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" style={{ stopColor: color, stopOpacity: 0.22 }} />
          <stop offset="100%" style={{ stopColor: color, stopOpacity: 0 }} />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${id})`} />
      <path d={line} fill="none" style={{ stroke: color }} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={points[points.length - 1][0]} cy={points[points.length - 1][1]} r="2.4" style={{ fill: color }} />
    </svg>
  );
}

export function ThroughputChart() {
  const rawId = useId();
  const id = `flow-${rawId.replace(/[^a-zA-Z0-9]/g, "")}`;
  const width = 680;
  const height = 250;
  const pad = { left: 38, right: 16, top: 18, bottom: 30 };
  const max = 450;
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const x = (index) => pad.left + (index * innerW) / (THROUGHPUT.length - 1);
  const y = (value) => pad.top + (1 - value / max) * innerH;
  const line = (key) =>
    THROUGHPUT.map((point, index) => `${index ? "L" : "M"}${x(index).toFixed(1)} ${y(point[key]).toFixed(1)}`).join(" ");
  const area = `${line("actual")} L ${x(THROUGHPUT.length - 1)} ${y(0)} L ${x(0)} ${y(0)} Z`;
  const gridValues = [0, 150, 300, 450];
  const lowIndex = 3;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label="Daily assembly output versus the 30-day median">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" style={{ stopColor: "rgb(var(--accent-400))", stopOpacity: 0.26 }} />
          <stop offset="100%" style={{ stopColor: "rgb(var(--accent-400))", stopOpacity: 0 }} />
        </linearGradient>
      </defs>

      {gridValues.map((value) => (
        <g key={value}>
          <line
            x1={pad.left}
            x2={width - pad.right}
            y1={y(value)}
            y2={y(value)}
            style={{ stroke: "rgb(var(--line))" }}
            strokeDasharray="3 5"
            strokeWidth="1"
          />
          <text
            x={pad.left - 9}
            y={y(value) + 3}
            textAnchor="end"
            style={{ fill: "rgb(var(--muted-2))", fontSize: 9 }}
          >
            {value}
          </text>
        </g>
      ))}

      <path d={area} fill={`url(#${id})`} />

      <path
        d={line("median")}
        fill="none"
        style={{ stroke: "rgb(var(--muted-2))" }}
        strokeWidth="1.4"
        strokeDasharray="5 5"
        opacity="0.8"
      />
      <path
        d={line("actual")}
        fill="none"
        style={{ stroke: "rgb(var(--accent-500))" }}
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {THROUGHPUT.map((point, index) => (
        <g key={point.day}>
          <text
            x={x(index)}
            y={height - 9}
            textAnchor="middle"
            style={{ fill: "rgb(var(--muted))", fontSize: 9 }}
          >
            {point.day}
          </text>
          {index === lowIndex && (
            <>
              <line
                x1={x(index)}
                x2={x(index)}
                y1={pad.top}
                y2={y(0)}
                style={{ stroke: "rgb(var(--danger))" }}
                strokeDasharray="3 4"
                opacity="0.35"
              />
              <circle cx={x(index)} cy={y(point.actual)} r="5" style={{ fill: "rgb(var(--surface))", stroke: "rgb(var(--danger))" }} strokeWidth="2" />
              <g>
                <rect
                  x={x(index) - 23}
                  y={y(point.actual) - 30}
                  width="46"
                  height="18"
                  rx="9"
                  style={{ fill: "rgb(var(--danger))" }}
                />
                <text x={x(index)} y={y(point.actual) - 17.5} textAnchor="middle" style={{ fill: "#fff", fontSize: 8.5, fontWeight: 600 }}>
                  288
                </text>
              </g>
            </>
          )}
          {index !== lowIndex && (
            <circle cx={x(index)} cy={y(point.actual)} r="2.2" style={{ fill: "rgb(var(--accent-500))" }} />
          )}
        </g>
      ))}
    </svg>
  );
}

const BAR_TONES = {
  danger: "rgb(var(--danger))",
  warning: "rgb(var(--warning))",
  accent: "rgb(var(--accent-500))",
  success: "rgb(var(--success))",
};

export function RiskStack() {
  return (
    <div className="dp-risk-bar flex">
      {RISK_MIX.map((item) => (
        <span
          key={item.label}
          style={{ width: `${(item.value / item.total) * 100}%`, background: BAR_TONES[item.tone] }}
          title={`${item.label}: ${item.value}`}
        />
      ))}
    </div>
  );
}

export function RiskLegend() {
  return (
    <div className="space-y-2.5">
      {RISK_MIX.map((item) => (
        <div key={item.label} className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: BAR_TONES[item.tone] }} />
          <span className="flex-1 text-[11px] text-muted">{item.label}</span>
          <span className="tabular text-[11px] font-semibold text-foreground">{item.value}</span>
          <span className="w-9 text-right text-[10px] text-subtle">{Math.round((item.value / item.total) * 100)}%</span>
        </div>
      ))}
    </div>
  );
}

export function ComposerMock({
  compact = false,
  placeholder = "Ask about orders, risk, or feasibility…",
  className = "",
}) {
  const [value, setValue] = useState("");

  return (
    <form
      className={`dp-composer ${compact ? "p-1.5" : "p-2.5"} ${className}`}
      onSubmit={(event) => {
        event.preventDefault();
        setValue("");
      }}
    >
      <div className="flex items-end gap-1.5">
        <button
          type="button"
          aria-label="Add context"
          className={`dp-icon-btn ${compact ? "h-8 w-8" : "h-9 w-9"} border-transparent bg-transparent`}
        >
          <Icon name="plus" size={compact ? 15 : 16} />
        </button>
        {!compact && (
          <button type="button" className="dp-pill hidden sm:inline-flex">
            <Icon name="spark" size={12} />
            Suggestions
          </button>
        )}
        <input
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder={placeholder}
          className={`min-w-0 flex-1 bg-transparent px-1 text-foreground outline-none placeholder:text-subtle ${
            compact ? "h-8 text-[11px]" : "h-9 text-[12.5px]"
          }`}
        />
        <button type="submit" className={`dp-send ${compact ? "h-8 w-8" : ""}`} aria-label="Send message">
          <Icon name="arrowUp" size={compact ? 14 : 16} strokeWidth={2} />
        </button>
      </div>
      {!compact && (
        <div className="mt-1.5 flex items-center justify-between gap-3 px-1 text-[9px] text-subtle">
          <span className="inline-flex items-center gap-1.5">
            <Icon name="shield" size={10} />
            Grounded in factory data
          </span>
          <span className="hidden items-center gap-1.5 sm:inline-flex">
            <span className="dp-kbd">Enter</span> to send
          </span>
        </div>
      )}
    </form>
  );
}
