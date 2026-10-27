import React from "react";
import { CalculateMetadataFunction, Composition } from "remotion";
import demoJson from "./demo.json";
import opening from "./opening.json";
import { Day, DayProps } from "./day/Day";
import { dayLength, resolveScenes } from "./day/resolve";
import type { DayConfig, ResolvedScene } from "./day/types";
import { Opening } from "./Opening";
import type { OpeningConfig } from "./types";

const config = opening as OpeningConfig;
const demo = demoJson as DayConfig;

const fallbackScenes: ResolvedScene[] = demo.scenes.map((scene) => ({
  ...scene,
  hasClip: false,
  missingClip: false,
  durationInFrames: scene.holdFrames ?? demo.placeholderFrames,
}));

const calculateDay: CalculateMetadataFunction<DayProps> = async () => {
  const resolvedScenes = await resolveScenes(demo);
  return {
    durationInFrames: dayLength(demo, resolvedScenes),
    fps: demo.fps,
    width: demo.width,
    height: demo.height,
    props: { ...demo, resolvedScenes },
  };
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="Opening"
        component={Opening}
        durationInFrames={config.durationInFrames}
        fps={config.fps}
        width={config.width}
        height={config.height}
        defaultProps={config}
      />
      <Composition
        id="Day"
        component={Day}
        durationInFrames={dayLength(demo, fallbackScenes)}
        fps={demo.fps}
        width={demo.width}
        height={demo.height}
        defaultProps={{ ...demo, resolvedScenes: fallbackScenes }}
        calculateMetadata={calculateDay}
      />
    </>
  );
};
