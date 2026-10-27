import React from "react";

const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

/** Five hours, drawn as the sun moving through the day. */
export const DayIcon: React.FC<{ index: number; size?: number }> = ({ index, size = 28 }) => {
  const kind = ((index % 5) + 5) % 5;
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden>
      {kind === 0 ? <Sunrise /> : null}
      {kind === 1 ? <Morning /> : null}
      {kind === 2 ? <Noon /> : null}
      {kind === 3 ? <Afternoon /> : null}
      {kind === 4 ? <Evening /> : null}
    </svg>
  );
};

const Sunrise = () => (
  <>
    <path {...stroke} d="M8 34h32" />
    <path {...stroke} d="M16 34a8 8 0 0 1 16 0" />
    <path {...stroke} d="M24 18v6M16 22l3 3M32 22l-3 3" />
  </>
);

const Morning = () => (
  <>
    <circle {...stroke} cx="24" cy="24" r="7" />
    <path {...stroke} d="M24 8v4M24 36v4M8 24h4M36 24h4M12.5 12.5l2.8 2.8M32.7 32.7l2.8 2.8M35.5 12.5l-2.8 2.8M15.3 32.7l-2.8 2.8" />
  </>
);

const Noon = () => (
  <>
    <circle {...stroke} cx="24" cy="26" r="8" />
    <path {...stroke} d="M24 6v6M10 14l4 3M38 14l-4 3M6 28h6M36 28h6" />
  </>
);

const Afternoon = () => (
  <>
    <path {...stroke} d="M8 36h32" />
    <path {...stroke} d="M22 36a8 8 0 0 1 16 0" />
    <path {...stroke} d="M30 20v4M40 24h4M36 16l-2 3" />
  </>
);

const Evening = () => (
  <>
    <path {...stroke} d="M30 14a8 8 0 1 0 0 14 6.5 6.5 0 1 1 0-14z" />
    <path {...stroke} d="M14 16l1.2 2.4 2.6.4-1.9 1.8.4 2.6L14 22l-2.3 1.2.4-2.6-1.9-1.8 2.6-.4z" />
    <circle {...stroke} cx="18" cy="30" r="1.2" />
  </>
);
