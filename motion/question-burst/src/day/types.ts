export type SceneInput = {
  id: string;
  time: string;
  /** Short spoken beat between scenes. This is the cut, not the question. */
  bridge: string;
  /** Lower-third label while the recording plays. */
  task: string;
  question: string;
  /** Path under public/, for example "clips/0940.mp4". Null looks for public/clips/{id}.mp4. */
  clip: string | null;
  /** Frames to skip at the start of the recording. */
  trimBeforeFrames?: number;
  /** Used only when clip is missing. */
  holdFrames?: number;
  /** Cap a long recording. Omit to play the whole file after the trim. */
  maxFrames?: number;
};

export type DayConfig = {
  width: number;
  height: number;
  fps: number;
  introFrames: number;
  cardFrames: number;
  outroFrames: number;
  placeholderFrames: number;
  showClockOnClip: boolean;
  intro: { kicker: string; title: string; subtitle: string };
  outro: { title: string; subtitle: string };
  colors: {
    paper: string;
    ink: string;
    brass: string;
    muted: string;
    white: string;
  };
  scenes: SceneInput[];
};

export type ResolvedScene = SceneInput & {
  hasClip: boolean;
  missingClip: boolean;
  durationInFrames: number;
};
