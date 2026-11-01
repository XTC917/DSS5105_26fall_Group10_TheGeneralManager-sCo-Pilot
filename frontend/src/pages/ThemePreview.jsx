import { useState } from "react";
import {
  AccentPicker,
  Badge,
  Button,
  Card,
  IconButton,
  Input,
  LoadingState,
  Modal,
  ModeToggle,
  Skeleton,
  SkeletonLines,
  Textarea,
} from "../components/ui/index.js";

function SearchIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
      <path d="M20 20l-3.5-3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function MailIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" strokeWidth="2" />
      <path d="M3 7l9 6 9-6" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
    </svg>
  );
}

const CHART_TOKENS = ["--chart-1", "--chart-2", "--chart-3", "--chart-4", "--chart-5", "--chart-6"];

export default function ThemePreview() {
  const [modalOpen, setModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("ada@sweaterco.example");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("Please enter a valid order id.");

  return (
    <div className="min-h-screen bg-canvas text-foreground">
      <header className="sticky top-0 z-30 border-b border-line bg-canvas/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-3">
          <div className="flex items-center gap-3">
            <a
              href="./"
              className="focus-ring rounded-md px-2 py-1 type-sm text-muted hover:text-foreground"
            >
              ← Back to app
            </a>
            <div>
              <p className="type-overline text-accentText">Design System · Dev Preview</p>
              <h1 className="type-h2 text-foreground">Theme & Component Playground</h1>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <ModeToggle />
            <AccentPicker />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 px-5 py-6">
        <Card className="bg-surface">
          <p className="type-overline text-muted">Overview</p>
          <p className="type-body mt-2 text-foreground/90">
            Switch appearance and accent above — every surface, button, input and
            chart token below updates instantly. Settings persist across reloads.
          </p>
        </Card>

        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {/* Typography */}
          <Card>
            <p className="type-overline text-muted">Typography</p>
            <div className="mt-3 space-y-1.5">
              <p className="type-display text-foreground">Display</p>
              <h1 className="type-h1 text-foreground">Heading 1</h1>
              <h2 className="type-h2 text-foreground">Heading 2</h2>
              <h3 className="type-h3 text-foreground">Heading 3</h3>
              <p className="type-body text-foreground/90">
                Body text for narrative answers and operational context. Numbers
                like <span className="type-metric inline-block align-middle">1,284</span>{" "}
                stay scannable.
              </p>
              <p className="type-sm text-muted">Small supporting copy for secondary context.</p>
              <p className="type-caption text-muted">Caption · 12px · +1% tracking</p>
              <p className="type-overline text-muted">Overline label</p>
              <div className="mt-3 rounded-control bg-surfaceMuted p-3">
                <p className="type-caption text-muted mb-1">Tabular numerals</p>
                <p className="type-body tabular text-foreground">
                  0001 · 0042 · 1203 · 9999 · 12,480
                </p>
              </div>
            </div>
          </Card>

          {/* Buttons */}
          <Card>
            <p className="type-overline text-muted">Buttons</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button variant="primary">Primary</Button>
              <Button variant="secondary">Secondary</Button>
              <Button variant="subtle">Subtle</Button>
              <Button variant="ghost">Ghost</Button>
              <Button variant="danger">Danger</Button>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button size="sm">Small</Button>
              <Button size="md">Medium</Button>
              <Button size="lg">Large</Button>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button loading>Loading</Button>
              <Button disabled>Disabled</Button>
              <Button leadingIcon={<MailIcon />}>With icon</Button>
              <Button variant="secondary" trailingIcon={<SearchIcon />} fullWidth>
                Full width
              </Button>
            </div>
          </Card>

          {/* Icon buttons */}
          <Card>
            <p className="type-overline text-muted">Icon buttons</p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <IconButton aria-label="Search"><SearchIcon /></IconButton>
              <IconButton variant="secondary" aria-label="Mail"><MailIcon /></IconButton>
              <IconButton variant="accent" aria-label="Mail"><MailIcon /></IconButton>
              <IconButton size="lg" aria-label="Search"><SearchIcon /></IconButton>
            </div>
            <p className="mt-3 type-caption text-muted">
              All icon buttons require an <code>aria-label</code> and expose a visible
              focus ring on keyboard focus.
            </p>
          </Card>

          {/* Inputs */}
          <Card>
            <p className="type-overline text-muted">Inputs</p>
            <div className="mt-3 space-y-3">
              <Input
                label="Order id"
                placeholder="e.g. ORD-120"
                leadingIcon={<SearchIcon />}
                hint="Start typing an order number."
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <Input
                label="Email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <Input
                label="At-risk threshold"
                type="number"
                error={error}
                value="800"
                readOnly
              />
              <Input label="Disabled field" disabled value="Read only" />
              <Textarea
                label="Note"
                placeholder="Add a short note about this order…"
                hint="Notes are saved per user."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>
          </Card>

          {/* Badges */}
          <Card>
            <p className="type-overline text-muted">Badges</p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Badge variant="neutral">Neutral</Badge>
              <Badge variant="accent" dot>Accent</Badge>
              <Badge variant="success" dot>On track</Badge>
              <Badge variant="warning" dot>At risk</Badge>
              <Badge variant="danger" dot>Overdue</Badge>
              <Badge variant="solid">Solid</Badge>
              <Badge size="sm" variant="accent">Small</Badge>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Badge variant="accent">ORD-120</Badge>
              <Badge variant="warning">Overdue by 3 days</Badge>
              <Badge variant="danger">Stalled</Badge>
              <Badge variant="success">Feasible</Badge>
            </div>
          </Card>

          {/* Cards / elevation */}
          <Card>
            <p className="type-overline text-muted">Cards & elevation</p>
            <div className="mt-3 grid gap-3">
              <Card padding="sm" className="shadow-xs">
                <p className="type-sm text-muted">Default surface</p>
                <p className="type-metric mt-1 text-foreground">24</p>
                <p className="type-caption text-muted">active watches</p>
              </Card>
              <Card padding="sm" interactive className="shadow-soft">
                <p className="type-sm text-muted">Interactive (hover me)</p>
                <p className="type-h3 mt-1 text-foreground">Clickable card</p>
                <p className="type-caption text-muted mt-1">Elevates on hover, keyboard focusable.</p>
              </Card>
              <Card padding="sm" className="shadow-card">
                <p className="type-sm text-muted">Raised surface</p>
                <p className="type-body mt-1 text-foreground">shadow-card token</p>
              </Card>
            </div>
          </Card>

          {/* Skeleton / loading */}
          <Card>
            <p className="type-overline text-muted">Skeleton & loading</p>
            <div className="mt-3 space-y-3">
              <SkeletonLines lines={3} />
              <div className="flex items-center gap-3">
                <Skeleton width={40} height={40} rounded="full" />
                <div className="flex-1 space-y-2">
                  <Skeleton height={12} style={{ width: "70%" }} />
                  <Skeleton height={10} style={{ width: "45%" }} />
                </div>
              </div>
              <LoadingState label="Fetching briefing…" />
            </div>
          </Card>

          {/* Modal */}
          <Card>
            <p className="type-overline text-muted">Modal & focus ring</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button onClick={() => setModalOpen(true)}>Open modal</Button>
              <button
                type="button"
                className="focus-ring rounded-control border border-line px-3 py-2 type-sm text-foreground hover:bg-surfaceMuted"
              >
                Focus ring demo
              </button>
            </div>
            <p className="mt-3 type-caption text-muted">
              Press <kbd className="rounded bg-surfaceMuted px-1.5 py-0.5 type-caption">Tab</kbd> to move focus; the accent
              ring follows the active accent. Press <kbd className="rounded bg-surfaceMuted px-1.5 py-0.5 type-caption">Esc</kbd>{" "}
              to close the modal.
            </p>
          </Card>

          {/* Chart tokens */}
          <Card className="md:col-span-2 xl:col-span-1">
            <p className="type-overline text-muted">Chart tokens</p>
            <p className="mt-1 type-caption text-muted">
              chart-1 follows the accent; the rest are theme-aware.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {CHART_TOKENS.map((token, index) => (
                <div key={token} className="flex items-center gap-2">
                  <span
                    className="h-9 w-9 rounded-md ring-1 ring-line"
                    style={{ backgroundColor: `rgb(var(${token}))` }}
                    aria-hidden="true"
                  />
                  <span className="type-caption text-muted">{token}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Full-width card: responsive grid demo */}
        <Card>
          <p className="type-overline text-muted">Responsive container</p>
          <p className="mt-2 type-body text-foreground/90">
            The preview uses the same max-width and padding conventions as the app
            shell. Resize the window — nothing overflows at 360 px.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge variant="accent">360 px</Badge>
            <Badge variant="neutral">768 px</Badge>
            <Badge variant="neutral">1024 px</Badge>
            <Badge variant="neutral">1280 px</Badge>
          </div>
        </Card>
      </main>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Confirm action"
        description="This dialog demonstrates the modal surface, focus management and reduced-motion behaviour."
        footer={
          <>
            <Button variant="ghost" onClick={() => setModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => setModalOpen(false)}>Confirm</Button>
          </>
        }
      >
        <p className="type-body text-foreground/90">
          Modal content inherits the surface tokens and stays readable in both
          light and dark. Press Escape or click the backdrop to close.
        </p>
      </Modal>
    </div>
  );
}
