import { ACCENTS, THEME_MODES } from "../../theme/themeConfig.js";
import { useTheme } from "../../theme/useTheme.js";
import { cx } from "./cx.js";

function ModeIcon({ id }) {
  const common = { width: 15, height: 15, viewBox: "0 0 24 24", fill: "none", "aria-hidden": true };
  if (id === "dark") {
    return (
      <svg {...common}>
        <path
          d="M21 12.8A8.5 8.5 0 1 1 11.2 3a6.5 6.5 0 0 0 9.8 9.8z"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  if (id === "system") {
    return (
      <svg {...common}>
        <rect x="3" y="4" width="18" height="12" rx="2" stroke="currentColor" strokeWidth="1.8" />
        <path d="M8 20h8M12 16v4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M19.1 4.9l-1.8 1.8M6.7 17.3l-1.8 1.8"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Appearance mode segmented control (Light / Dark / System). */
export function ModeToggle({ className }) {
  const { mode, setMode } = useTheme();
  return (
    <div
      className={cx(
        "inline-flex items-center gap-0.5 rounded-full border border-line bg-surfaceMuted p-0.5",
        className,
      )}
      role="group"
      aria-label="Appearance mode"
    >
      {THEME_MODES.map((item) => {
        const active = mode === item.id;
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => setMode(item.id)}
            aria-pressed={active}
            className={cx(
              "focus-ring inline-flex h-8 items-center gap-1.5 rounded-full px-3 type-caption font-medium transition-colors duration-[var(--dur-fast)]",
              active
                ? "bg-surface text-foreground shadow-xs"
                : "text-muted hover:text-foreground",
            )}
          >
            <ModeIcon id={item.id} />
            <span className="hidden sm:inline">{item.label}</span>
            <span className="sr-only sm:hidden">{item.label}</span>
          </button>
        );
      })}
    </div>
  );
}

/** Accent colour swatch picker. */
export function AccentPicker({ className }) {
  const { accent, setAccent } = useTheme();
  return (
    <div
      className={cx("flex flex-wrap items-center gap-2", className)}
      role="group"
      aria-label="Accent colour"
    >
      {ACCENTS.map((item) => {
        const active = accent === item.id;
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => setAccent(item.id)}
            aria-pressed={active}
            aria-label={item.name}
            title={item.name}
            className={cx(
              "focus-ring relative inline-flex h-8 w-8 items-center justify-center rounded-full transition-transform duration-[var(--dur-fast)] hover:scale-105",
              active ? "ring-2 ring-offset-2" : "ring-1 ring-line",
            )}
            style={{
              backgroundColor: item.swatch,
              "--tw-ring-offset-color": "rgb(var(--surface))",
              ...(active ? { "--tw-ring-color": item.swatch } : {}),
            }}
          >
            {active && (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  d="M5 12.5l4.5 4.5L19 7.5"
                  stroke="#fff"
                  strokeWidth="2.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
          </button>
        );
      })}
    </div>
  );
}

/** Convenience composite used in the preview header. */
export default function ThemeSwitcher({ className }) {
  return (
    <div className={cx("flex flex-wrap items-center gap-3", className)}>
      <ModeToggle />
      <AccentPicker />
    </div>
  );
}
