import { useEffect, useState } from "react";

/** Read live chart / axis colours from the design-system CSS tokens. */

function rgbVar(name, fallback) {
  if (typeof document === "undefined") return fallback;
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  if (!raw) return fallback;
  return `rgb(${raw})`;
}

function rawVar(name, fallback) {
  if (typeof document === "undefined") return fallback;
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return raw || fallback;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function parseRgbTriplet(input) {
  if (!input) return null;
  const text = String(input).trim();
  const hex = text.match(/^#?([0-9a-fA-F]{6})$/);
  if (hex) {
    const n = parseInt(hex[1], 16);
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
  }
  const nums = text
    .replace(/[^0-9.\s,]/g, "")
    .split(/[\s,]+/)
    .filter(Boolean)
    .map(Number);
  if (nums.length >= 3 && nums.slice(0, 3).every((n) => !Number.isNaN(n))) {
    return { r: nums[0], g: nums[1], b: nums[2] };
  }
  return null;
}

function rgbToHsl({ r, g, b }) {
  const rr = r / 255;
  const gg = g / 255;
  const bb = b / 255;
  const max = Math.max(rr, gg, bb);
  const min = Math.min(rr, gg, bb);
  const l = (max + min) / 2;
  const d = max - min;
  let h = 0;
  let s = 0;
  if (d !== 0) {
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === rr) h = (gg - bb) / d + (gg < bb ? 6 : 0);
    else if (max === gg) h = (bb - rr) / d + 2;
    else h = (rr - gg) / d + 4;
    h *= 60;
  }
  return { h, s: s * 100, l: l * 100 };
}

function hslToRgb({ h, s, l }) {
  const hh = ((h % 360) + 360) % 360;
  const ss = clamp(s, 0, 100) / 100;
  const ll = clamp(l, 0, 100) / 100;
  const c = (1 - Math.abs(2 * ll - 1)) * ss;
  const x = c * (1 - Math.abs(((hh / 60) % 2) - 1));
  const m = ll - c / 2;
  let rr = 0;
  let gg = 0;
  let bb = 0;
  if (hh < 60) { rr = c; gg = x; }
  else if (hh < 120) { rr = x; gg = c; }
  else if (hh < 180) { gg = c; bb = x; }
  else if (hh < 240) { gg = x; bb = c; }
  else if (hh < 300) { rr = x; bb = c; }
  else { rr = c; bb = x; }
  return {
    r: Math.round((rr + m) * 255),
    g: Math.round((gg + m) * 255),
    b: Math.round((bb + m) * 255),
  };
}

function hslCss(hsl) {
  const { r, g, b } = hslToRgb(hsl);
  return `rgb(${r} ${g} ${b})`;
}

function morandiSat(baseSat) {
  // Pull saturation down toward a dusty, muted Morandi range.
  return clamp(baseSat * 0.4 + 6, 14, 28);
}

/**
 * Coordinated, low-saturation (Morandi) palette derived from the theme accent
 * hue. Analogous hue offsets keep it harmonious; lightness variation keeps
 * categories distinguishable.
 */
function buildAccentPalette(baseTriplet, count = 8) {
  const rgb = parseRgbTriplet(baseTriplet);
  if (!rgb) return null;
  const { h, s, l } = rgbToHsl(rgb);
  const sat = morandiSat(s);
  const baseL = clamp(l, 50, 62);
  const specs = [
    { dh: 0, dl: 0 },
    { dh: -30, dl: 10 },
    { dh: 26, dl: -6 },
    { dh: 52, dl: 4 },
    { dh: -54, dl: -2 },
    { dh: 16, dl: -12 },
    { dh: -16, dl: 14 },
    { dh: 80, dl: 6 },
  ];
  const out = [];
  for (let i = 0; i < count; i += 1) {
    const sp = specs[i % specs.length];
    out.push(hslCss({ h: h + sp.dh, s: sat, l: clamp(baseL + sp.dl, 46, 74) }));
  }
  return out;
}

/** Single-hue muted ramp (light -> dark) for ordinal / urgency encodings. */
function buildAccentRamp(baseTriplet, steps = 6) {
  const rgb = parseRgbTriplet(baseTriplet);
  if (!rgb) return null;
  const { h, s } = rgbToHsl(rgb);
  const sat = morandiSat(s);
  const lightness = [72, 64, 56, 48, 42, 36];
  return lightness.slice(0, steps).map((l) => hslCss({ h, s: sat, l }));
}

export function readChartTheme() {
  const baseTriplet = rawVar("--accent-500", "59 130 246");
  const palette = buildAccentPalette(baseTriplet, 8) || [
    "rgb(37 99 235)",
    "rgb(96 165 250)",
    "rgb(99 102 241)",
    "rgb(139 92 246)",
    "rgb(14 165 233)",
    "rgb(30 64 175)",
    "rgb(125 211 252)",
    "rgb(165 180 252)",
  ];
  return {
    colors: [
      rgbVar("--chart-1", "#1d4ed8"),
      rgbVar("--chart-2", "#0ea5e9"),
      rgbVar("--chart-3", "#10b981"),
      rgbVar("--chart-4", "#f59e0b"),
      rgbVar("--chart-5", "#f43f5e"),
      rgbVar("--chart-6", "#8b5cf6"),
    ],
    // Coordinated (analogous) palette derived from the accent hue for
    // categorical series.
    palette,
    // Single-hue muted ramp (light -> dark) for ordinal / urgency encodings.
    accentRamp: buildAccentRamp(baseTriplet, 6) || [
      "rgb(191 205 220)",
      "rgb(158 176 198)",
      "rgb(126 147 173)",
      "rgb(99 121 148)",
      "rgb(78 98 122)",
      "rgb(60 78 100)",
    ],
    accent: rgbVar("--accent", "#2563eb"),
    accentSoft: rgbVar("--accent-soft", "#dbeafe"),
    accentText: rgbVar("--accent-text", "#1d4ed8"),
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
