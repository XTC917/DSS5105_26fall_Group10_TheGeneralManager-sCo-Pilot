import { getVideoMetadata } from "@remotion/media-utils";
import { getStaticFiles, staticFile } from "remotion";
import type { DayConfig, ResolvedScene, SceneInput } from "./types";

const holdFor = (scene: SceneInput, config: DayConfig) => scene.holdFrames ?? config.placeholderFrames;

const hasFile = (relative: string) => {
  const target = relative.replace(/\\/g, "/");
  return getStaticFiles().some((file) => file.name.replace(/\\/g, "/") === target);
};

export async function resolveScenes(config: DayConfig): Promise<ResolvedScene[]> {
  return Promise.all(
    config.scenes.map(async (scene) => {
      const automatic = `clips/${scene.id}.mp4`;
      const clip = scene.clip ?? (hasFile(automatic) ? automatic : null);
      if (!clip) {
        return { ...scene, hasClip: false, missingClip: false, durationInFrames: holdFor(scene, config) };
      }
      if (!hasFile(clip)) {
        return { ...scene, hasClip: false, missingClip: true, durationInFrames: holdFor(scene, config) };
      }
      try {
        const meta = await getVideoMetadata(staticFile(clip));
        const trim = scene.trimBeforeFrames ?? 0;
        const available = Math.max(1, Math.round(meta.durationInSeconds * config.fps) - trim);
        const durationInFrames = scene.maxFrames ? Math.min(available, scene.maxFrames) : available;
        return { ...scene, clip, hasClip: true, missingClip: false, durationInFrames };
      } catch {
        return { ...scene, hasClip: false, missingClip: true, durationInFrames: holdFor(scene, config) };
      }
    }),
  );
}

export function dayLength(config: DayConfig, scenes: ResolvedScene[]): number {
  const scenesLength = scenes.reduce((sum, scene) => sum + config.cardFrames + scene.durationInFrames, 0);
  return config.introFrames + scenesLength + config.outroFrames;
}
