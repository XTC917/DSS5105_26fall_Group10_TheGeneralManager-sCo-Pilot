/**
 * Static sample content for the Phase 5A design preview.
 * Nothing here touches the API, the database or the real conversation store.
 */

export const NAV_ITEMS = [
  { key: "ask", label: "Ask AI", icon: "chat" },
  { key: "overview", label: "Overview", icon: "grid" },
  { key: "data", label: "Data Management", icon: "database" },
  { key: "users", label: "User Management", icon: "users" },
  { key: "settings", label: "Settings", icon: "settings" },
];

export const WATCHES = [
  {
    order: "ORD-120",
    label: "No movement by 22 Aug",
    tone: "danger",
    status: "Triggered",
  },
  {
    order: "ORD-005",
    label: "Watch until Thursday",
    tone: "warning",
    status: "Watching",
  },
];

export const CONVERSATIONS = [
  { id: "trendcart", title: "TrendCart at-risk orders", time: "2m", preview: "3 orders · Assembly constraint" },
  { id: "morning", title: "Morning briefing · 18 Aug", time: "12m", preview: "Factory-wide summary" },
  { id: "feasibility", title: "Feasibility — 800 hoodies", time: "1h", preview: "Capacity check" },
  { id: "ord5", title: "ORD-005 watch", time: "Yesterday", preview: "Watch until Thursday" },
];

export const DESKTOP_SUGGESTIONS = [
  {
    icon: "alert",
    tone: "danger",
    title: "Which orders are at risk right now?",
    meta: "3 flagged today",
  },
  {
    icon: "sun",
    tone: "accent",
    title: "Give me this morning's briefing",
    meta: "Morning · 2 min read",
  },
  {
    icon: "zap",
    tone: "warning",
    title: "Can we take 800 hoodies by 25 Aug?",
    meta: "Feasibility check",
  },
  {
    icon: "package",
    tone: "neutral",
    title: "How is ORD-120 doing?",
    meta: "Order detail",
  },
];

export const MOBILE_SUGGESTIONS = [
  {
    icon: "alert",
    tone: "danger",
    title: "Which orders are at risk?",
    meta: "3 flagged today",
  },
  {
    icon: "sun",
    tone: "accent",
    title: "Morning briefing",
    meta: "Today, 07:30",
  },
  {
    icon: "zap",
    tone: "warning",
    title: "800 hoodies by 25 Aug?",
    meta: "Feasibility",
  },
];

export const METRICS = [
  {
    label: "On-time orders",
    value: "94.2%",
    delta: "+2.4%",
    tone: "success",
    icon: "check",
    spark: [88, 89, 90, 89, 92, 93, 94],
  },
  {
    label: "At-risk orders",
    value: "6",
    delta: "−3",
    tone: "danger",
    icon: "alert",
    spark: [11, 10, 9, 8, 9, 7, 6],
  },
  {
    label: "Open watches",
    value: "4",
    delta: "2 triggered",
    tone: "warning",
    icon: "bell",
    spark: [2, 2, 3, 3, 3, 4, 4],
  },
  {
    label: "Avg. cycle time",
    value: "2.8d",
    delta: "−0.4d",
    tone: "accent",
    icon: "clock",
    spark: [3.4, 3.3, 3.2, 3.1, 3.0, 2.9, 2.8],
  },
];

export const MORNING_BRIEFING = {
  title: "Morning briefing",
  date: "18 Aug 2026 · 07:30",
  summary:
    "The factory is broadly stable, but Assembly is carrying the morning risk. Two TrendCart orders need a decision before the 10:00 production huddle.",
  points: [
    {
      tone: "danger",
      icon: "alert",
      title: "Assembly is the constraint",
      body: "Last working day closed at 68% of its 30-day median. ORD-120 is the largest exposure at 1,200 pieces.",
    },
    {
      tone: "warning",
      icon: "clock",
      title: "Two orders due this week",
      body: "ORD-120 and ORD-118 will miss their promised date if Finishing stays at today's rate.",
    },
    {
      tone: "success",
      icon: "check",
      title: "Material intake is healthy",
      body: "No new fabric risk was flagged overnight. The next delivery lands on 20 Aug.",
    },
  ],
};

export const WEEKLY_BRIEFING = {
  title: "Weekly briefing",
  date: "11 – 17 Aug 2026 · Week 33",
  summary:
    "On-time delivery improved for the third week running. Assembly remains the bottleneck, and three of the four late orders passed through it.",
  points: [
    {
      tone: "success",
      icon: "trendUp",
      title: "On-time delivery up 2.4 points",
      body: "The improvement is concentrated in Cutting and Finishing, which both cleared their weekly targets.",
    },
    {
      tone: "warning",
      icon: "layers",
      title: "Assembly still constrains output",
      body: "Median daily output fell from 410 to 372 pieces. Three of four late orders were waiting at Assembly.",
    },
    {
      tone: "accent",
      icon: "zap",
      title: "Feasibility outlook",
      body: "The 800-hoodie enquiry is feasible only if Assembly recovers above 390 pieces/day by 20 Aug.",
    },
  ],
};

export const TOP_ISSUES = [
  {
    priority: "P1",
    title: "Assembly stalled for 3 days",
    meta: "TrendCart · ORD-120 · 1,200 pcs · due 22 Aug",
    risk: "Overdue",
    tone: "danger",
    detail: "68% of 30-day median",
  },
  {
    priority: "P1",
    title: "Cutting queue is building",
    meta: "Northwind · ORD-118 · 640 pcs · due 21 Aug",
    risk: "At risk",
    tone: "warning",
    detail: "2.4 days behind plan",
  },
  {
    priority: "P2",
    title: "Finishing output dipping",
    meta: "Factory-wide · median 410 → 268 pieces",
    risk: "Watch",
    tone: "accent",
    detail: "4 of 7 days below threshold",
  },
  {
    priority: "P3",
    title: "Fabric receipt is late",
    meta: "BlueLoom · ORD-095 · 480 pcs · due 28 Aug",
    risk: "Watch",
    tone: "warning",
    detail: "ETA moved by 1 day",
  },
];

export const THROUGHPUT = [
  { day: "Mon", actual: 412, median: 405 },
  { day: "Tue", actual: 398, median: 405 },
  { day: "Wed", actual: 362, median: 402 },
  { day: "Thu", actual: 288, median: 400 },
  { day: "Fri", actual: 312, median: 398 },
  { day: "Sat", actual: 340, median: 396 },
  { day: "Sun", actual: 356, median: 394 },
];

export const RISK_MIX = [
  { label: "Overdue", value: 3, total: 51, tone: "danger" },
  { label: "At risk", value: 7, total: 51, tone: "warning" },
  { label: "Watch", value: 5, total: 51, tone: "accent" },
  { label: "On track", value: 36, total: 51, tone: "success" },
];

export const ORDER_ROWS = [
  {
    order: "ORD-120",
    due: "22 Aug",
    stage: "Assembly",
    status: "Overdue",
    tone: "danger",
    pieces: "1,200",
    progress: 68,
  },
  {
    order: "ORD-118",
    due: "21 Aug",
    stage: "Cutting",
    status: "At risk",
    tone: "warning",
    pieces: "640",
    progress: 54,
  },
  {
    order: "ORD-115",
    due: "25 Aug",
    stage: "Fabric",
    status: "Watch",
    tone: "accent",
    pieces: "900",
    progress: 41,
  },
  {
    order: "ORD-105",
    due: "28 Aug",
    stage: "Finishing",
    status: "On track",
    tone: "success",
    pieces: "480",
    progress: 86,
  },
];

export const CLARIFICATION_OPTIONS = [
  {
    id: "revenue",
    label: "By revenue at risk",
    hint: "Highest exposure first",
  },
  {
    id: "due",
    label: "By days until due",
    hint: "Most urgent first",
  },
  {
    id: "stage",
    label: "By production stage",
    hint: "Group the constraint",
  },
];

export const TRACE_STEPS = [
  {
    title: "Start from the question",
    body: "The GM asked which TrendCart orders are at risk today.",
  },
  {
    title: "Read what the data says",
    body: "orders.csv was filtered to account = TrendCart. production_log.csv was read for the last 30 working days.",
  },
  {
    title: "Check the calculation",
    body: "ORD-120 has 3 consecutive days below 70% of its 30-day median. ORD-118 is 2.4 days behind plan.",
  },
  {
    title: "Why the conclusion follows",
    body: "Each order is flagged because its current stage is behind its own recent baseline, not because of a due-date heuristic.",
  },
];

export const TRACE_SOURCES = [
  { name: "orders.csv", meta: "account, due date, pieces" },
  { name: "production_log.csv", meta: "stage output · 30 working days" },
];

/* ---- Go Deeper follow-up prompts (fill-only, never auto-sent) ----------- */
export const GO_DEEPER = [
  { id: "watch", icon: "bell", title: "Create a watch on ORD-120 until 22 Aug" },
  { id: "fix", icon: "zap", title: "What would recover Assembly to 390/day?" },
  { id: "compare", icon: "layers", title: "Compare ORD-120 with its last 3 runs" },
  { id: "customer", icon: "package", title: "Draft a customer update for TrendCart" },
];

/* ---- Composer Suggestions popover (same data source shape) -------------- */
export const COMPOSER_SUGGESTIONS = [
  "Which orders are at risk right now?",
  "Give me this morning's briefing",
  "How is ORD-120 doing?",
  "Can we take 800 hoodies by August 25?",
  "List the TrendCart orders",
  "Why is ORD-120 considered risky?",
  "What should I be concerned about right now?",
  "Cancel the watch on ORD-005",
];

/* ---- Alerts surface (used by rail > Alerts and the mobile drawer) ------- */
export const TRIGGERED_ALERTS = [
  {
    id: "a1",
    order: "ORD-120",
    title: "No movement in Assembly for 3 working days",
    meta: "TrendCart · 1,200 pcs · due 22 Aug",
    tone: "danger",
    status: "Triggered",
    time: "07:31",
  },
  {
    id: "a2",
    order: "ORD-118",
    title: "Cutting queue is 2.4 days behind plan",
    meta: "Northwind · 640 pcs · due 21 Aug",
    tone: "warning",
    status: "Triggered",
    time: "07:31",
  },
];

export const ACTIVE_WATCHES = [
  {
    id: "w1",
    order: "ORD-120",
    label: "Check daily until past Assembly, or 22 Aug",
    tone: "danger",
    status: "Triggered",
    created: "14 Aug",
  },
  {
    id: "w2",
    order: "ORD-005",
    label: "Watch until Thursday for movement",
    tone: "warning",
    status: "Watching",
    created: "16 Aug",
  },
];

export const WATCH_HISTORY = [
  { id: "h1", order: "ORD-098", label: "Cleared Cutting on schedule", result: "Resolved", time: "17 Aug" },
  { id: "h2", order: "ORD-081", label: "Fabric arrived, watch closed", result: "Resolved", time: "15 Aug" },
  { id: "h3", order: "ORD-073", label: "Cancelled by GM", result: "Cancelled", time: "12 Aug" },
];

/* ---- Settings surface --------------------------------------------------- */
export const SETTINGS_SECTIONS = [
  { id: "appearance", label: "Appearance", icon: "sun" },
  { id: "account", label: "Account", icon: "users" },
  { id: "security", label: "Security", icon: "shield" },
  { id: "session", label: "Session", icon: "clock" },
];

export const ACCOUNT_PROFILE = {
  name: "Mei Chen",
  role: "General Manager",
  email: "mei.chen+preview@example.com",
  factory: "Factory 12",
  initials: "MC",
};

export const SECURITY_ROWS = [
  { id: "pw", label: "Password", value: "Updated 24 days ago", action: "Change" },
  { id: "2fa", label: "Two-factor authentication", value: "Not enabled", action: "Set up" },
  { id: "devices", label: "Active devices", value: "2 devices", action: "Review" },
];
