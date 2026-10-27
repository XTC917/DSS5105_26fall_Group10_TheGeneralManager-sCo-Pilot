import type { OpeningConfig, Placement, QuestionInput } from "./types";

/** Fixed cycles. Index decides the slot, so editing the words does not move them. */
const DEPTH = [1.18, 0.74, 0.98, 0.64, 1.08, 0.82, 0.58, 1.12, 0.7, 0.9, 0.78, 1.02];
const DIRECTIONS = [
  { dx: -1, dy: 0.12 },
  { dx: 1, dy: -0.08 },
  { dx: 0.16, dy: -1 },
  { dx: -0.12, dy: 1 },
  { dx: 1, dy: 0.28 },
  { dx: -1, dy: -0.22 },
  { dx: 0.32, dy: 1 },
  { dx: -0.28, dy: -1 },
];
const JITTER = [
  { x: -0.16, y: 0.08 },
  { x: 0.14, y: -0.1 },
  { x: 0.04, y: 0.14 },
  { x: -0.12, y: -0.08 },
  { x: 0.18, y: 0.02 },
  { x: -0.06, y: 0.12 },
  { x: 0.1, y: -0.14 },
  { x: -0.18, y: 0.04 },
];

export function normalizeQuestions(questions: Array<QuestionInput | string>): QuestionInput[] {
  return questions
    .map((item) => (typeof item === "string" ? { text: item } : item))
    .filter((item) => item.text.trim().length > 0);
}

/** Designed slots, in entry order. Extra questions continue on a grid after these. */
const SLOTS = [
  { x: 0.26, y: 0.3, scale: 1.16 },
  { x: 0.74, y: 0.24, scale: 0.72 },
  { x: 0.5, y: 0.16, scale: 0.9 },
  { x: 0.22, y: 0.7, scale: 0.64 },
  { x: 0.76, y: 0.68, scale: 1.05 },
  { x: 0.42, y: 0.46, scale: 0.78 },
  { x: 0.64, y: 0.56, scale: 0.6 },
  { x: 0.12, y: 0.48, scale: 0.84 },
  { x: 0.88, y: 0.44, scale: 1.08 },
  { x: 0.36, y: 0.86, scale: 0.7 },
  { x: 0.66, y: 0.84, scale: 0.96 },
  { x: 0.5, y: 0.38, scale: 0.66 },
];

/** Pack entrances into the frames before the fade, without changing who comes from where. */
export function startFrames(count: number, config: OpeningConfig): number[] {
  const { firstFrame, staggerFrames, enterFrames, fadeStartFrame } = config.timing;
  if (count <= 0) {
    return [];
  }
  const room = Math.max(0, fadeStartFrame - firstFrame - Math.floor(enterFrames * 0.45));
  const stagger = count === 1 ? 0 : Math.min(staggerFrames, Math.floor(room / (count - 1)));
  const step = Math.max(2, stagger);
  return Array.from({ length: count }, (_, index) => firstFrame + index * step);
}

function slotFor(index: number): { x: number; y: number; scale: number } {
  if (index < SLOTS.length) {
    return SLOTS[index];
  }
  const extra = index - SLOTS.length;
  const cols = 4;
  const col = extra % cols;
  const row = Math.floor(extra / cols);
  const jitter = JITTER[index % JITTER.length];
  return {
    x: 0.16 + col * 0.22 + jitter.x * 0.04,
    y: 0.2 + (row % 4) * 0.18 + jitter.y * 0.04,
    scale: DEPTH[index % DEPTH.length],
  };
}

export function placeQuestions(config: OpeningConfig): Placement[] {
  const questions = normalizeQuestions(config.questions);
  const { width, height, typography } = config;
  const starts = startFrames(questions.length, config);

  return questions.map((question, index) => {
    const slot = slotFor(index);
    const direction = DIRECTIONS[index % DIRECTIONS.length];
    const scale = question.scale ?? slot.scale;
    const x = slot.x * width;
    const y = slot.y * height;
    const maxWidth = Math.max(280, Math.min(760, Math.min(x, width - x) * 1.8));
    const preferred = typography.baseSize * scale;
    const lines = Math.max(1, Math.ceil(question.text.length / 28));
    const fitted = maxWidth / Math.max(question.text.length / lines, 8) / 0.56;
    const fontSize = Math.max(typography.minSize, Math.min(preferred, fitted));
    return {
      text: question.text,
      x,
      y,
      scale,
      fontSize,
      maxWidth,
      dx: direction.dx,
      dy: direction.dy,
      startFrame: starts[index],
    };
  });
}
