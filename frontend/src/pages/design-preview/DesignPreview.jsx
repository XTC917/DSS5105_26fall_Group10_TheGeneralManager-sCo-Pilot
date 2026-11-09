import { useState } from "react";
import DesktopWorkspace from "./DesktopWorkspace.jsx";
import MobileAskAI from "./MobileAskAI.jsx";
import { BrandMark, Icon } from "./bits.jsx";
import { usePreviewTheme } from "./previewTheme.js";
import ThemePicker from "./ThemePicker.jsx";
import "./preview.css";

const SECTIONS = [
  {
    id: "desktop",
    label: "Desktop workspace",
    hint: "Navigation rail · context panel · welcome",
    icon: "chat",
  },
  {
    id: "conversation",
    label: "Conversation",
    hint: "Markdown · charts · tables · go deeper · stop",
    icon: "layers",
  },
  {
    id: "overview",
    label: "Overview",
    hint: "Top issues · briefings · metrics · risk",
    icon: "grid",
  },
  {
    id: "mobile",
    label: "Mobile",
    hint: "3-item nav · center Ask AI · alerts drawer",
    icon: "monitor",
  },
];

function ThemeDna() {
  return (
    <div className="dp-card p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="dp-eyebrow">Theme DNA</p>
        <span className="text-[8px] text-subtle">live tokens</span>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-1.5">
        <div>
          <span className="dp-swatch block bg-accent" />
          <span className="mt-1 block text-[8px] text-muted">Primary</span>
        </div>
        <div>
          <span className="dp-swatch block" style={{ background: "rgb(var(--dp-secondary))" }} />
          <span className="mt-1 block text-[8px] text-muted">Secondary</span>
        </div>
        <div>
          <span className="dp-swatch block bg-accentSoft" />
          <span className="mt-1 block text-[8px] text-muted">Accent soft</span>
        </div>
      </div>

      <div className="mt-3">
        <div className="dp-gradient-bar" />
        <div className="mt-1 flex items-center justify-between text-[8px] text-subtle">
          <span>Gradient start</span>
          <span>Gradient end</span>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-1.5">
        <div className="rounded-xl border border-line/70 p-2">
          <p className="text-[8px] text-muted">Surface tint</p>
          <span className="mt-1.5 block h-4 rounded-md" style={{ background: "var(--dp-tint)" }} />
        </div>
        <div className="rounded-xl border border-line/70 p-2">
          <p className="text-[8px] text-muted">Glow</p>
          <span
            className="mt-1.5 block h-4 rounded-md"
            style={{ background: "rgb(var(--surface))", boxShadow: "0 8px 18px -6px var(--dp-glow)" }}
          />
        </div>
        <div className="rounded-xl border border-line/70 p-2">
          <p className="text-[8px] text-muted">Border</p>
          <span className="mt-1.5 block h-4 rounded-md border" style={{ borderColor: "var(--dp-border-strong)" }} />
        </div>
        <div className="rounded-xl border border-line/70 p-2">
          <p className="text-[8px] text-muted">Shadow</p>
          <span className="dp-shadow-sample mt-1.5 block h-4 w-full" />
        </div>
      </div>

      <div className="mt-3 flex items-end justify-between gap-2 border-t border-line/60 pt-3">
        <div>
          <p className="text-[9px] font-medium text-muted">Refined type</p>
          <p className="mt-1 text-[8px] leading-3 text-subtle">
            IBM Plex Sans · 600
            <br />−3.5% display tracking
          </p>
        </div>
        <span className="text-[30px] font-semibold leading-none tracking-[-0.055em] text-foreground">Aa</span>
      </div>
    </div>
  );
}

function SectionNav({ active, onSelect, compact = false }) {
  if (compact) {
    return (
      <div className="flex gap-1.5 overflow-x-auto pb-1">
        {SECTIONS.map((section) => (
          <button
            key={section.id}
            type="button"
            onClick={() => onSelect(section.id)}
            className={`shrink-0 rounded-full border px-3 py-1.5 text-[10.5px] font-medium transition-colors ${
              active === section.id
                ? "border-accent-300/60 bg-accentSoft/50 text-accentText"
                : "border-line bg-surface/60 text-muted hover:text-foreground"
            }`}
          >
            {section.label}
          </button>
        ))}
      </div>
    );
  }

  return (
    <nav className="space-y-1" aria-label="Preview sections">
      {SECTIONS.map((section, index) => (
        <button
          key={section.id}
          type="button"
          onClick={() => onSelect(section.id)}
          className={`dp-section-tab focus-ring ${active === section.id ? "is-active" : ""}`}
          aria-current={active === section.id ? "true" : undefined}
        >
          <span className="dp-section-index">{String(index + 1).padStart(2, "0")}</span>
          <span className="min-w-0 flex-1">
            <span className="block text-[11px] font-semibold leading-tight text-foreground">{section.label}</span>
            <span className="mt-1 block text-[8.5px] leading-3.5 text-muted">{section.hint}</span>
          </span>
        </button>
      ))}
    </nav>
  );
}

function renderSection(section, theme, onTheme) {
  if (section === "mobile") return <MobileAskAI theme={theme} onTheme={onTheme} />;
  if (section === "overview") {
    return <DesktopWorkspace key="overview" initialNav="overview" theme={theme} onTheme={onTheme} />;
  }
  if (section === "conversation") {
    return (
      <DesktopWorkspace
        key="conversation"
        initialNav="ask"
        initialConversation="trendcart"
        theme={theme}
        onTheme={onTheme}
      />
    );
  }
  return <DesktopWorkspace key="desktop" initialNav="ask" theme={theme} onTheme={onTheme} />;
}

export default function DesignPreview() {
  const [section, setSection] = useState("desktop");
  const { theme, setTheme } = usePreviewTheme();
  const active = SECTIONS.find((item) => item.id === section) || SECTIONS[0];

  return (
    <div className="design-preview" data-dp-theme={theme}>
      <header className="dp-toolbar">
        <div className="mx-auto flex max-w-[1480px] flex-wrap items-center justify-between gap-3 px-4 py-3 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <BrandMark size={38} />
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <p className="truncate text-[12.5px] font-semibold tracking-[-0.01em] text-foreground">SweaterCo</p>
                <span className="rounded-full border border-accent-300/50 bg-accentSoft/50 px-1.5 py-0.5 text-[7.5px] font-bold uppercase tracking-[0.14em] text-accentText">
                  Dev
                </span>
              </div>
              <p className="truncate text-[9px] font-medium uppercase tracking-[0.16em] text-muted">
                Soft Intelligence · Phase 5A · Round 2
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="hidden items-center gap-2 rounded-full border border-line bg-surface/60 px-2.5 py-1.5 md:flex">
              <span className="dp-eyebrow pr-1">Theme</span>
              <ThemePicker theme={theme} onChange={setTheme} />
            </div>
            <a href="./" className="dp-pill focus-ring" title="Leave the design preview">
              <Icon name="arrowLeft" size={12} />
              Back to app
            </a>
          </div>
        </div>
      </header>

      <div className="mx-auto w-full max-w-[1480px] px-4 py-5 lg:px-8 lg:py-6">
        <div className="flex gap-6">
          <aside className="hidden w-[230px] shrink-0 xl:block">
            <div className="sticky top-[88px] space-y-3">
              <SectionNav active={section} onSelect={setSection} />

              <div className="dp-card p-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="dp-eyebrow">Colour theme</p>
                  <span className="text-[8px] text-subtle">7 total</span>
                </div>
                <div className="mt-2.5">
                  <ThemePicker variant="list" theme={theme} onChange={setTheme} />
                </div>
                <p className="mt-2.5 text-[8.5px] leading-4 text-subtle">
                  No Light / Dark / System toggle. Each theme — Black included — is a complete, independent palette.
                </p>
              </div>

              <ThemeDna />

              <div className="dp-card p-4">
                <div className="flex items-center gap-2">
                  <span className="dp-icon-tile dp-icon-tile-sm dp-tone-success">
                    <Icon name="check" size={12} strokeWidth={2.4} />
                  </span>
                  <p className="dp-eyebrow">Static preview</p>
                </div>
                <p className="mt-2 text-[9px] leading-4 text-muted">
                  No API calls, no database reads and no changes to production pages. Theme choices persist to
                  localStorage only.
                </p>
                <div className="mt-2.5 flex flex-wrap gap-1">
                  <span className="dp-chip">Static sample data</span>
                  <span className="dp-chip">No production changes</span>
                </div>
              </div>
            </div>
          </aside>

          <main className="min-w-0 flex-1">
            <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="dp-eyebrow">
                  Phase 5A · Section {String(SECTIONS.findIndex((item) => item.id === section) + 1).padStart(2, "0")}
                </p>
                <h1 className="mt-1 text-[24px] font-semibold leading-tight tracking-[-0.035em] text-foreground">
                  {active.label}
                </h1>
                <p className="mt-1 max-w-[620px] text-[11.5px] leading-5 text-muted">{active.hint}</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="dp-status">
                  <span className="h-1.5 w-1.5 rounded-full bg-success" />
                  Static sample data
                </span>
                <span className="dp-chip">No production changes</span>
              </div>
            </div>

            <div className="mb-4 xl:hidden">
              <SectionNav active={section} onSelect={setSection} compact />
            </div>

            <section aria-label={active.label}>{renderSection(section, theme, setTheme)}</section>

            <footer className="mt-6 flex flex-wrap items-center justify-between gap-2 border-t border-line/60 pt-4 text-[9px] text-subtle">
              <span>Phase 5A · Soft Intelligence visual preview · static content</span>
              <span className="inline-flex items-center gap-1.5">
                <Icon name="shield" size={10} />
                Production UI, API and agent untouched
              </span>
            </footer>
          </main>
        </div>
      </div>
    </div>
  );
}
