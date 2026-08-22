function Card({ title, children }) {
  return (
    <section className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-ink/50">{title}</h2>
      <div className="mt-2 text-sm text-ink/70">{children}</div>
    </section>
  );
}

export default function Sidebar() {
  return (
    <aside className="space-y-3">
      <Card title="Morning briefing">
        Not in this MVP. The next slice will generate it from discovery tools, not a fixed
        template.
      </Card>
      <Card title="Important alerts">
        Ask in chat: <span className="font-medium text-ink">Which orders are at risk?</span>
      </Card>
      <Card title="Recent actions">
        Email, notes, and reminders are not wired yet. Side effects will require confirmation.
      </Card>
      <Card title="Watches / reminders">Coming in a later increment.</Card>
    </aside>
  );
}
