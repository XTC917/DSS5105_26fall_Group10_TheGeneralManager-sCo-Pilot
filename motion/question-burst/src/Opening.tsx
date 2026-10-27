import React from "react";
import { AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { loadFont as loadSans } from "@remotion/google-fonts/Inter";
import { loadFont as loadSerif } from "@remotion/google-fonts/Newsreader";
import { placeQuestions } from "./layout";
import { QuestionLine } from "./QuestionLine";
import type { OpeningConfig } from "./types";

const sans = loadSans("normal", { weights: ["500", "600"], subsets: ["latin"] });
const serif = loadSerif("normal", { weights: ["500"], subsets: ["latin"] });

const clamp = {
  extrapolateLeft: "clamp" as const,
  extrapolateRight: "clamp" as const,
};

const resolveFamily = (requested: string, bundledName: string, bundledFamily: string) => {
  return requested === bundledName ? bundledFamily : requested;
};

export const Opening: React.FC<OpeningConfig> = (config) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const questions = placeQuestions(config);
  const questionFont = resolveFamily(config.typography.fontFamily, "Inter", sans.fontFamily);
  const titleFont = resolveFamily(config.typography.titleFontFamily, "Newsreader", serif.fontFamily);
  const titleEnter = spring({
    frame: frame - config.timing.titleStartFrame,
    fps,
    config: { damping: 20, stiffness: 88, mass: 0.9 },
  });
  const titleOpacity = interpolate(titleEnter, [0, 0.45], [0, 1], clamp);
  const titleY = interpolate(titleEnter, [0, 1], [28, 0]);
  const subtitleOpacity = interpolate(
    frame,
    [config.timing.titleStartFrame + 10, config.timing.titleStartFrame + 24],
    [0, 1],
    { ...clamp, easing: Easing.out(Easing.cubic) },
  );

  return (
    <AbsoluteFill style={{ backgroundColor: config.colors.background, overflow: "hidden" }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse at 50% 42%, ${config.colors.backgroundGlow} 0%, ${config.colors.background} 58%)`,
        }}
      />
      <AbsoluteFill style={{ opacity: 0.18, pointerEvents: "none" }}>
        <svg width="100%" height="100%">
          <filter id="grain">
            <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="4" stitchTiles="stitch" />
          </filter>
          <rect width="100%" height="100%" filter="url(#grain)" opacity="0.35" />
        </svg>
      </AbsoluteFill>
      {questions.map((placement) => (
        <QuestionLine
          key={`${placement.startFrame}-${placement.x}-${placement.y}`}
          placement={placement}
          config={config}
          fontFamily={questionFont}
        />
      ))}
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div
          style={{
            opacity: titleOpacity,
            transform: `translateY(${titleY}px)`,
            textAlign: "center",
            maxWidth: config.width * 0.72,
          }}
        >
          <div
            style={{
              fontFamily: titleFont,
              fontSize: config.typography.titleSize,
              fontWeight: 500,
              letterSpacing: "-0.035em",
              lineHeight: 1.02,
              color: config.colors.title,
            }}
          >
            {config.finalTitle}
          </div>
          {config.finalSubtitle ? (
            <div
              style={{
                marginTop: 22,
                opacity: subtitleOpacity,
                fontFamily: questionFont,
                fontSize: config.typography.subtitleSize,
                fontWeight: 500,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: config.colors.subtitle,
              }}
            >
              {config.finalSubtitle}
            </div>
          ) : null}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
