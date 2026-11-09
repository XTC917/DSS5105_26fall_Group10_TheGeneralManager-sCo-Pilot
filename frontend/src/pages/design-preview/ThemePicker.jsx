import { PREVIEW_THEMES } from "./previewTheme.js";
import { Icon } from "./bits.jsx";

/**
 * Preview-only colour picker. There is no Light / Dark / System toggle — the
 * seven themes each ship their own complete visual language (Black included).
 */
export function ThemePicker({ theme, onChange, variant = "row", className = "" }) {
  if (variant === "list") {
    return (
      <div className={`space-y-1.5 ${className}`} role="group" aria-label="Colour theme">
        {PREVIEW_THEMES.map((item) => {
          const active = item.id === theme;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onChange(item.id)}
              aria-pressed={active}
              className={`dp-theme-card focus-ring ${active ? "is-active" : ""}`}
            >
              <span className="dp-theme-card-swatch !h-6 !w-6 !rounded-lg" style={{ background: item.swatch }} />
              <span className="min-w-0 flex-1 text-left">
                <span className="block text-[11px] font-semibold leading-tight text-foreground">{item.name}</span>
              </span>
              {active && (
                <span className="dp-theme-check !h-4 !w-4">
                  <Icon name="check" size={10} strokeWidth={2.6} />
                </span>
              )}
            </button>
          );
        })}
      </div>
    );
  }

  if (variant === "grid") {
    return (
      <div className={`grid grid-cols-2 gap-2 ${className}`} role="group" aria-label="Colour theme">
        {PREVIEW_THEMES.map((item) => {
          const active = item.id === theme;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onChange(item.id)}
              aria-pressed={active}
              className={`dp-theme-card focus-ring ${active ? "is-active" : ""}`}
            >
              <span className="dp-theme-card-swatch" style={{ background: item.swatch }} />
              <span className="min-w-0 flex-1 text-left">
                <span className="block text-[11.5px] font-semibold leading-tight text-foreground">
                  {item.name}
                </span>
                <span className="mt-0.5 block truncate text-[9px] text-muted">{item.caption}</span>
              </span>
              {active && (
                <span className="dp-theme-check">
                  <Icon name="check" size={11} strokeWidth={2.6} />
                </span>
              )}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div className={`flex flex-wrap items-center gap-2 ${className}`} role="group" aria-label="Colour theme">
      {PREVIEW_THEMES.map((item) => {
        const active = item.id === theme;
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onChange(item.id)}
            aria-pressed={active}
            aria-label={`${item.name} theme`}
            title={`${item.name} — ${item.caption}`}
            className={`dp-theme-dot focus-ring ${active ? "is-active" : ""}`}
            style={{ background: item.swatch }}
          >
            {active && (
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  d="M5 12.5l4.4 4.4L19 7.5"
                  stroke={item.id === "black" ? "#e8ebef" : "#fff"}
                  strokeWidth="2.6"
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

export default ThemePicker;
