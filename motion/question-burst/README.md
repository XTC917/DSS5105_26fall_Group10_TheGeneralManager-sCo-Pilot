# Question burst

A 6-second kinetic type opener. Questions enter from fixed directions, overlap, then clear for one line in the center. Edit `src/opening.json` only. The layout is a function of how many questions there are and their order, not of the wording and not of a random seed.

Default output is 1920×1080 at 30 fps, 180 frames.

## Setup

From this folder:

```bash
npm install
```

The first preview downloads Inter and Newsreader. Those two names are bundled. Any other `fontFamily` is used as a font already installed on the machine.

## Preview

```bash
npm run preview
```

Remotion Studio opens in the browser. Change `src/opening.json` and save. The studio reloads. Scrub the timeline to check the rhythm before rendering.

## Render

```bash
npm run render
```

The file is written to `out/opening.mp4`. A single frame of the title is:

```bash
npm run still
```

## What to edit

| Field | Effect |
|---|---|
| `questions` | The lines that enter. A string or `{ "text": "...", "scale": 1.1 }`. `scale` is optional. Larger means closer. |
| `finalTitle`, `finalSubtitle` | The line left after the questions fade. An empty subtitle is omitted. |
| `colors` | Background, question ink, title ink. |
| `typography` | Families and sizes. Long lines shrink down to `minSize` so they stay inside their slot. |
| `timing` | When the first question starts, the gap between questions, and when the fade and title begin. Extra questions tighten the gap so they still finish before the fade. |
| `motion.travel`, `motion.blur`, `motion.trail` | How far a line flies in, how soft it is while moving, and how many trailing copies it leaves. |
| `width`, `height`, `fps`, `durationInFrames` | The composition itself. Keep duration and fps together if you change the length. |

Order is the composition. Swapping two questions swaps their slots. Rewriting a question in place keeps its slot.

## Day demo

`src/demo.json` is the whole film. It follows one Monday the way [A day with Claude](https://www.youtube.com/watch?v=oqUclC3gqKs) follows Maggie: a short line at each hour, then the product on the desk. The room light moves from morning to evening. The recording is the only part that changes.

Put a file at `public/clips/{id}.mp4` and leave `clip` null. The id is the scene's `id`, for example `public/clips/0940-trendcart.mp4`. To use another filename:

```json
"clip": "clips/0940-trendcart.mp4"
```

Optional on the same object:

| Field | Effect |
|---|---|
| `trimBeforeFrames` | Skip this many frames at the start of the file. |
| `maxFrames` | Stop the recording early. Omit it to play the rest of the file. |
| `holdFrames` | How long the empty slot stays when there is no file. |

`npm run demo` writes `out/day.mp4`. `npm run preview` and choose the **Day** composition to scrub it. Changing the question text or the five times does not require a code change. A new hour is another object in `scenes`.
