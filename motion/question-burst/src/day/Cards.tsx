import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { DayIcon } from "./icons";
import { lightFor } from "./light";
import type { DayConfig, ResolvedScene } from "./types";

const clamp = { extrapolateLeft: "clamp" as const, extrapolateRight: "clamp" as const };

export const Room: React.FC<{ index: number; children?: React.ReactNode }> = ({ index, children }) => {
  const light = lightFor(index);
  return (
    <AbsoluteFill style={{ backgroundColor: light.desk }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse at 50% 18%, ${light.glow} 0%, ${light.sky} 42%, ${light.desk} 78%)`,
        }}
      />
      {children}
    </AbsoluteFill>
  );
};

export const DayMarks: React.FC<{
  times: string[];
  active: number;
  fontFamily: string;
  color: string;
}> = ({ times, active, fontFamily, color }) => {
  return (
    <div style={{ display: "flex", gap: 22, alignItems: "center" }}>
      {times.map((time, index) => (
        <div key={time} style={{ display: "flex", alignItems: "center", gap: 22 }}>
          <div style={{ textAlign: "center", color, opacity: index === active ? 1 : index < active ? 0.72 : 0.32 }}>
            <div style={{ marginBottom: 8 }}>
              <DayIcon index={index} size={30} />
            </div>
            <div style={{ fontFamily, fontSize: 16, letterSpacing: "-0.02em" }}>{time}</div>
          </div>
          {index < times.length - 1 ? <div style={{ width: 36, height: 1, marginTop: 15, backgroundColor: color, opacity: 0.25 }} /> : null}
        </div>
      ))}
    </div>
  );
};

export const TimeCard: React.FC<{
  config: DayConfig;
  scene: ResolvedScene;
  index: number;
  duration: number;
  questionFont: string;
  titleFont: string;
}> = ({ config, scene, index, duration, questionFont, titleFont }) => {
  const frame = useCurrentFrame();
  const fadeIn = interpolate(frame, [0, 10], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const fadeOut = interpolate(frame, [duration - 8, duration], [1, 0], clamp);
  const rise = interpolate(frame, [0, 14], [16, 0], { ...clamp, easing: Easing.out(Easing.cubic) });

  return (
    <AbsoluteFill style={{ opacity: fadeIn * fadeOut }}>
      <Room index={index}>
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
          <div style={{ transform: `translateY(${rise}px)`, textAlign: "center" }}>
            <div style={{ color: config.colors.ink }}>
              <DayIcon index={index} size={72} />
            </div>
            <div style={{ marginTop: 16, fontFamily: questionFont, fontSize: 18, letterSpacing: "0.22em", textTransform: "uppercase", color: config.colors.muted }}>
              {config.intro.kicker}
            </div>
            <div style={{ marginTop: 10, fontFamily: titleFont, fontSize: 92, lineHeight: 0.92, letterSpacing: "-0.045em", color: config.colors.ink }}>
              {scene.time}
            </div>
            <div style={{ marginTop: 18, fontFamily: titleFont, fontSize: 40, color: config.colors.ink }}>{scene.bridge}</div>
          </div>
          <div style={{ position: "absolute", bottom: 64 }}>
            <DayMarks times={config.scenes.map((item) => item.time)} active={index} fontFamily={questionFont} color={config.colors.ink} />
          </div>
        </AbsoluteFill>
      </Room>
    </AbsoluteFill>
  );
};

export const TitleCard: React.FC<{
  config: DayConfig;
  kicker: string;
  title: string;
  subtitle: string;
  duration: number;
  questionFont: string;
  titleFont: string;
  times?: string[];
}> = ({ config, kicker, title, subtitle, duration, questionFont, titleFont, times }) => {
  const frame = useCurrentFrame();
  const fadeIn = interpolate(frame, [0, 12], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const fadeOut = interpolate(frame, [duration - 10, duration], [1, 0], clamp);
  const rise = interpolate(frame, [0, 16], [14, 0], { ...clamp, easing: Easing.out(Easing.cubic) });
  const hour = times ? 0 : config.scenes.length - 1;

  return (
    <AbsoluteFill style={{ opacity: fadeIn * fadeOut }}>
      <Room index={hour}>
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
          <div style={{ transform: `translateY(${rise}px)`, textAlign: "center", maxWidth: 1100 }}>
            <div style={{ fontFamily: questionFont, fontSize: 18, letterSpacing: "0.24em", textTransform: "uppercase", color: config.colors.muted }}>{kicker}</div>
            <div style={{ marginTop: 16, fontFamily: titleFont, fontSize: 84, lineHeight: 0.98, letterSpacing: "-0.04em", color: config.colors.ink }}>{title}</div>
            {subtitle ? (
              <div style={{ marginTop: 18, fontFamily: questionFont, fontSize: 22, letterSpacing: "0.14em", textTransform: "uppercase", color: config.colors.muted }}>{subtitle}</div>
            ) : null}
          </div>
          {times && times.length > 0 ? (
            <div style={{ position: "absolute", bottom: 64 }}>
              <DayMarks times={times} active={-1} fontFamily={questionFont} color={config.colors.ink} />
            </div>
          ) : null}
        </AbsoluteFill>
      </Room>
    </AbsoluteFill>
  );
};
