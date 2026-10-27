import React from "react";
import { AbsoluteFill, Series } from "remotion";
import { loadFont as loadSans } from "@remotion/google-fonts/Inter";
import { loadFont as loadSerif } from "@remotion/google-fonts/Newsreader";
import { ClipStage } from "./ClipStage";
import { TimeCard, TitleCard } from "./Cards";
import type { DayConfig, ResolvedScene } from "./types";

const sans = loadSans("normal", { weights: ["500", "600"], subsets: ["latin"] });
const serif = loadSerif("normal", { weights: ["500"], subsets: ["latin"] });

export type DayProps = DayConfig & { resolvedScenes: ResolvedScene[] };

export const Day: React.FC<DayProps> = (props) => {
  const scenes = props.resolvedScenes;
  const questionFont = sans.fontFamily;
  const titleFont = serif.fontFamily;
  const beats = scenes.flatMap((scene, index) => [
    <Series.Sequence key={`${scene.id}-card`} durationInFrames={props.cardFrames}>
      <TimeCard
        config={props}
        scene={scene}
        index={index}
        duration={props.cardFrames}
        questionFont={questionFont}
        titleFont={titleFont}
      />
    </Series.Sequence>,
    <Series.Sequence key={`${scene.id}-clip`} durationInFrames={scene.durationInFrames}>
      <ClipStage
        config={props}
        scene={scene}
        index={index}
        duration={scene.durationInFrames}
        questionFont={questionFont}
        titleFont={titleFont}
      />
    </Series.Sequence>,
  ]);

  return (
    <AbsoluteFill style={{ backgroundColor: props.colors.paper }}>
      <Series>
        <Series.Sequence durationInFrames={props.introFrames}>
          <TitleCard
            config={props}
            kicker={props.intro.kicker}
            title={props.intro.title}
            subtitle={props.intro.subtitle}
            duration={props.introFrames}
            questionFont={questionFont}
            titleFont={titleFont}
            times={scenes.map((scene) => scene.time)}
          />
        </Series.Sequence>
        {beats}
        <Series.Sequence durationInFrames={props.outroFrames}>
          <TitleCard
            config={props}
            kicker={props.intro.kicker}
            title={props.outro.title}
            subtitle={props.outro.subtitle}
            duration={props.outroFrames}
            questionFont={questionFont}
            titleFont={titleFont}
          />
        </Series.Sequence>
      </Series>
    </AbsoluteFill>
  );
};
