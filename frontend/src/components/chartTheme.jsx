import { useEffect, useState } from "react";

/** Read live chart / axis colours from the design-system CSS tokens. */

function rgbVar(name, fallback) {
  if (typeof document === "undefined") return fallback;
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  if (!raw) return fallback;
  return `rgb(${raw})`;
}

export function readChartTheme() {
  return {
    colors: [
      rgbVar("--chart-1", "#1d4ed8"),
      rgbVar("--chart-2", "#0ea5e9"),
      rgbVar("--chart-3", "#10b981"),
      rgbVar("--chart-4", "#f59e0b"),
      rgbVar("--chart-5", "#f43f5e"),
      rgbVar("--chart-6", "#8b5cf6"),
    ],
    grid: rgbVar("--line", "#e2e4e7"),
    axis: rgbVar("--muted", "#5a626c"),
    tooltipBg: rgbVar("--surface", "#ffffff"),
    tooltipBorder: rgbVar("--line", "#e2e4e7"),
    tooltipText: rgbVar("--foreground", "#171b20"),
    legend: rgbVar("--muted", "#5a626c"),
    danger: rgbVar("--danger", "#be282d"),
    success: rgbVar("--success", "#15805d"),
    warning: rgbVar("--warning", "#b47814"),
    foreground: rgbVar("--foreground", "#171b20"),
  };
}

/** Subscribe to theme / accent changes for Recharts consumers. */
export function useChartTheme() {
  const [theme, setTheme] = useState(() => readChartTheme());
  useEffect(() => {
    const sync = () => setTheme(readChartTheme());
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme", "data-accent"],
    });
    return () => observer.disconnect();
  }, []);
  return theme;
}

export function ChartTooltip({ active, payload, label, formatter }) {
  if (!active || !payload?.length) return null;
  const theme = readChartTheme();
  return (
    <div
      className="rounded-control border border-line bg-surface px-3 py-2 shadow-soft type-caption"
      style={{ color: theme.tooltipText, borderColor: theme.tooltipBorder, background: theme.tooltipBg }}
    >
      {label != null && label !== "" && (
        <p className="mb-1 font-semibold text-foreground">{label}</p>
      )}
      <ul className="space-y-0.5">
        {payload.map((entry) => {
          const formatted = formatter
            ? formatter(entry.value, entry.name, entry)
            : [entry.value, entry.name];
          const [valueText, nameText] = Array.isArray(formatted)
            ? formatted
            : [formatted, entry.name];
          return (
            <li key={`${entry.name}-${entry.dataKey}`} className="flex items-center gap-2 text-muted">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ background: entry.color || entry.fill || theme.colors[0] }}
              />
              <span>{nameText}</span>
              <span className="ml-auto font-medium text-foreground">{valueText}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
