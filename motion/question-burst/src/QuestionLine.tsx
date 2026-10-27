import React from "react";
import { Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { OpeningConfig, Placement } from "./types";

const clamp = {
  extrapolateLeft: "clamp" as const,
  extrapolateRight: "clamp" as const,
};

export const QuestionLine: React.FC<{
  placement: Placement;
  config: OpeningConfig;
  fontFamily: string;
}> = ({ placement, config, fontFamily }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { fadeStartFrame, fadeOutFrames } = config.timing;
  const local = frame - placement.startFrame;
  const enter = spring({
    frame: local,
    fps,
    config: { damping: 18, stiffness: 128, mass: 0.72 },
  });
  const fade = interpolate(
    frame,
    [fadeStartFrame, fadeStartFrame + fadeOutFrames],
    [1, 0],
    { ...clamp, easing: Easing.in(Easing.cubic) },
  );
  const opacity = interpolate(enter, [0, 0.28], [0, 1], clamp) * fade;
  const travel = config.motion.travel * (1.05 - Math.min(placement.scale, 1.15) * 0.25);
  const offsetX = placement.dx * travel * (1 - enter);
  const offsetY = placement.dy * travel * (1 - enter);
  const exitDrift = interpolate(frame, [fadeStartFrame, fadeStartFrame + fadeOutFrames], [0, 1], clamp);
  const blur = interpolate(enter, [0, 0.2, 1], [config.motion.blur, config.motion.blur * 0.35, 0], clamp);
  const scale = interpolate(enter, [0, 1], [0.94, 1]) * interpolate(exitDrift, [0, 1], [1, 0.97]);
  const driftX = placement.dx * -28 * exitDrift;
  const driftY = placement.dy * -12 * exitDrift;
  const trail = Math.max(0, Math.round(config.motion.trail));
  const textStyle: React.CSSProperties = {
    width: placement.maxWidth,
    fontFamily,
    fontSize: placement.fontSize,
    fontWeight: config.typography.questionWeight,
    letterSpacing: "-0.03em",
    lineHeight: 1.12,
    textAlign: "center",
  };

  return (
    <div
      style={{
        position: "absolute",
        left: placement.x,
        top: placement.y,
        width: placement.maxWidth,
        transform: "translate(-50%, -50%)",
      }}
    >
      {Array.from({ length: trail }, (_, index) => {
        const lagged = Math.max(0, enter - (index + 1) * 0.07);
        const trailOpacity = opacity * Math.max(0, 0.2 - index * 0.04) * Math.min(blur, 1);
        if (trailOpacity <= 0.01) {
          return null;
        }
        const x = placement.dx * travel * (1 - lagged) + driftX;
        const y = placement.dy * travel * (1 - lagged) + driftY;
        return (
          <div
            key={index}
            style={{
              ...textStyle,
              position: "absolute",
              left: 0,
              top: 0,
              transform: `translate(${x}px, ${y}px) scale(${scale})`,
              opacity: trailOpacity,
              filter: `blur(${blur + (index + 1) * 1.5}px)`,
              color: config.colors.questionMuted,
            }}
          >
            {placement.text}
          </div>
        );
      })}
      <div
        style={{
          ...textStyle,
          transform: `translate(${offsetX + driftX}px, ${offsetY + driftY}px) scale(${scale})`,
          opacity,
          filter: `blur(${blur}px)`,
          color: config.colors.question,
        }}
      >
        {placement.text}
      </div>
    </div>
  );
};
