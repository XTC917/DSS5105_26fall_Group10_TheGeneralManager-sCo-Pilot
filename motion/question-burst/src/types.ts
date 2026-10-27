export type QuestionInput = {
  text: string;
  /** Optional depth. 1 is the base size. Larger means closer. */
  scale?: number;
};

export type OpeningConfig = {
  width: number;
  height: number;
  fps: number;
  durationInFrames: number;
  questions: QuestionInput[];
  finalTitle: string;
  finalSubtitle: string;
  colors: {
    background: string;
    backgroundGlow: string;
    question: string;
    questionMuted: string;
    title: string;
    subtitle: string;
  };
  typography: {
    fontFamily: string;
    titleFontFamily: string;
    baseSize: number;
    minSize: number;
    titleSize: number;
    subtitleSize: number;
    questionWeight: number;
  };
  timing: {
    firstFrame: number;
    staggerFrames: number;
    enterFrames: number;
    fadeStartFrame: number;
    fadeOutFrames: number;
    titleStartFrame: number;
  };
  motion: {
    travel: number;
    blur: number;
    trail: number;
  };
};

export type Placement = {
  text: string;
  x: number;
  y: number;
  scale: number;
  fontSize: number;
  maxWidth: number;
  dx: number;
  dy: number;
  startFrame: number;
};
