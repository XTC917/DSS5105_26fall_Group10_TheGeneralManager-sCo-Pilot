import { THEMES } from "../../theme/themeConfig.js";
import { useTheme } from "../../theme/useTheme.js";
import { cx } from "./cx.js";

function Swatch({ item, active, onSelect, size = "md" }) {
  return (
    <button
      key={item.id}
      type="button"
      onClick={() => onSelect(item.id)}
      aria-pressed={active}
      aria-label={item.name}
      title={`${item.name} — ${item.caption}`}
      className={cx(
        "focus-ring relative inline-flex items-center justify-center rounded-full transition-transform duration-[var(--dur-fast)] hover:scale-105",
        size === "lg" ? "h-9 w-9" : "h-8 w-8",
        active ? "ring-2 ring-offset-2" : "ring-1 ring-line",
      )}
      style={{
        background: item.swatch,
        "--tw-ring-offset-color": "rgb(var(--surface))",
        "--tw-ring-color": "rgb(var(--accent))",
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
            style={{ filter: "drop-shadow(0 1px 1px rgba(0,0,0,0.45))" }}
          />
        </svg>
      )}
    </button>
  );
}

/** Full colour-theme swatch row (no Light / Dark / System). */
export function AccentPicker({ className, variant = "grid", size = "md" }) {
  const { theme, setTheme } = useTheme();

  if (variant === "list") {
    return (
      <div className={cx("grid gap-1.5", className)} role="group" aria-label="Colour theme">
        {THEMES.map((item) => {
          const active = theme === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setTheme(item.id)}
              aria-pressed={active}
              className={cx(
                "focus-ring flex items-center gap-2.5 rounded-control border px-2.5 py-1.5 text-left transition-colors",
                active
                  ? "border-accentText/60 bg-accentSoft/50"
                  : "border-line hover:border-lineStrong hover:bg-surfaceMuted",
              )}
            >
              <span
                className="h-5 w-5 shrink-0 rounded-full ring-1 ring-line"
                style={{ background: item.swatch }}
                aria-hidden="true"
              />
              <span className="min-w-0">
                <span className="block type-caption font-semibold leading-tight text-foreground">
                  {item.name}
                </span>
                <span className="block text-[10px] leading-tight text-subtle">{item.caption}</span>
              </span>
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div
      className={cx("flex flex-wrap items-center gap-2", className)}
      role="group"
      aria-label="Colour theme"
    >
      {THEMES.map((item) => (
        <Swatch
          key={item.id}
          item={item}
          active={theme === item.id}
          onSelect={setTheme}
          size={size}
        />
      ))}
    </div>
  );
}

/** Deprecated: the Light / Dark / System toggle no longer exists. */
export function ModeToggle() {
  return null;
}

/** Convenience composite used in Settings. */
export default function ThemeSwitcher({ className, variant = "list" }) {
  return (
    <div className={cx("space-y-3", className)}>
      <AccentPicker variant={variant} />
      <p className="type-caption text-subtle">
        Seven complete colour themes, including Black. There is no separate Light / Dark / System
        switch — each theme is its own full palette and persists across reloads.
      </p>
    </div>
  );
}
