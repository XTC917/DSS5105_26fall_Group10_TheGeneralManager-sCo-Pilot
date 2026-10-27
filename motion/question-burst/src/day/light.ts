/** Room light for each hour. The day is the cut, the way the reference film uses the office. */
const HOURS = [
  { sky: "#f6d7b2", glow: "#ffe7c4", desk: "#c9a27a" },
  { sky: "#f4e6cf", glow: "#fff4e2", desk: "#d8c3a4" },
  { sky: "#f7f2e8", glow: "#ffffff", desk: "#e3d5c0" },
  { sky: "#f0d2ae", glow: "#ffd9b0", desk: "#c4966e" },
  { sky: "#e7b48a", glow: "#f6c89a", desk: "#a87552" },
];

export type HourLight = { sky: string; glow: string; desk: string };

export function lightFor(index: number): HourLight {
  return HOURS[Math.min(Math.max(index, 0), HOURS.length - 1)];
}
