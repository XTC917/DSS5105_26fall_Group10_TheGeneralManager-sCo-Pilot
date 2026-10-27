import React from "react";
import { AbsoluteFill, OffthreadVideo, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Room } from "./Cards";
import { DayIcon } from "./icons";
import type { DayConfig, ResolvedScene } from "./types";

const clamp = { extrapolateLeft: "clamp" as const, extrapolateRight: "clamp" as const };

export const ClipStage: React.FC<{
  config: DayConfig;
  scene: ResolvedScene;
  index: number;
  duration: number;
  questionFont: string;
  titleFont: string;
}> = ({ config, scene, index, duration, questionFont, titleFont }) => {
  const frame = useCurrentFrame();
  const fadeIn = interpolate(frame, [0, 8], [0, 1], clamp);
  const fadeOut = interpolate(frame, [duration - 8, duration], [1, 0], clamp);
  return (
    <AbsoluteFill style={{ opacity: fadeIn * fadeOut }}>
      <Room index={index}>
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
          <div
            style={{
              width: 1500,
              height: 860,
              borderRadius: 28,
              backgroundColor: "#1c1917",
              padding: "18px 18px 42px",
              boxShadow: "0 30px 70px rgba(40, 24, 10, 0.28)",
            }}
          >
            <div style={{ height: "100%", borderRadius: 12, overflow: "hidden", backgroundColor: "#ece7df" }}>
              {scene.hasClip && scene.clip ? (
                <OffthreadVideo
                  src={staticFile(scene.clip)}
                  trimBefore={scene.trimBeforeFrames ?? 0}
                  style={{ width: "100%", height: "100%", objectFit: "contain", backgroundColor: "#ece7df" }}
                />
              ) : (
                <Placeholder config={config} scene={scene} questionFont={questionFont} />
              )}
            </div>
          </div>
        </AbsoluteFill>
        {config.showClockOnClip ? (
          <div
            style={{
              position: "absolute",
              left: 48,
              bottom: 36,
              display: "flex",
              alignItems: "center",
              gap: 14,
              color: config.colors.ink,
            }}
          >
            <DayIcon index={index} size={34} />
            <div style={{ fontFamily: titleFont, fontSize: 42, letterSpacing: "-0.04em" }}>{scene.time}</div>
            <div style={{ fontFamily: questionFont, fontSize: 18, letterSpacing: "0.08em", textTransform: "uppercase", color: config.colors.muted }}>{scene.task}</div>
          </div>
        ) : null}
      </Room>
    </AbsoluteFill>
  );
};

const Placeholder: React.FC<{
  config: DayConfig;
  scene: ResolvedScene;
  questionFont: string;
}> = ({ config, scene, questionFont }) => {
  const file = scene.clip ?? `clips/${scene.id}.mp4`;
  return (
    <AbsoluteFill style={{ backgroundColor: "#f6f3ee", fontFamily: questionFont, color: config.colors.ink }}>
      <div style={{ display: "flex", height: "100%" }}>
        <aside style={{ width: 250, backgroundColor: config.colors.ink, color: config.colors.paper, padding: "26px 20px" }}>
          <div style={{ fontSize: 18, fontWeight: 600 }}>SweaterCo</div>
          <div style={{ marginTop: 6, fontSize: 12, letterSpacing: "0.12em", textTransform: "uppercase", color: config.colors.brass }}>Factory</div>
          <div style={{ marginTop: 28, padding: "10px 12px", borderRadius: 8, backgroundColor: "rgba(244,239,230,0.12)", fontSize: 14 }}>Morning briefing</div>
        </aside>
        <section style={{ flex: 1, display: "flex", flexDirection: "column", padding: "28px 32px 24px" }}>
          <div style={{ fontSize: 13, letterSpacing: "0.14em", textTransform: "uppercase", color: config.colors.muted }}>{scene.task}</div>
          <div style={{ marginTop: 28, alignSelf: "flex-end", maxWidth: 760, padding: "16px 18px", borderRadius: 16, backgroundColor: config.colors.ink, color: config.colors.paper, fontSize: 26, lineHeight: 1.3 }}>
            {scene.question}
          </div>
          <div style={{ marginTop: 22, maxWidth: 680, fontSize: 18, lineHeight: 1.45, color: "#8a8176" }}>The recorded answer plays in this screen.</div>
          <div style={{ marginTop: "auto", fontSize: 15, color: config.colors.muted }}>
            {scene.missingClip ? `Missing ${file}` : `public/${file}`}
          </div>
        </section>
      </div>
    </AbsoluteFill>
  );
};
