---
name: talking-head-reel
description: Edit a raw talking-to-camera phone video into a polished vertical reel for Instagram Reels, TikTok or YouTube Shorts. Tightens pauses without cutting words, adds punch-in framing on every jump cut, word-by-word serif captions with a highlighted keyword, numbered chapter cards and a progress tracker, fact cards, an end prompt, a title cover thumbnail, clean -14 LUFS audio and optional music. Use this whenever someone drops a selfie or talking-head clip and asks to edit it, caption it, cut it down, "make it a reel", make it more engaging or professional, add a thumbnail, or redo an earlier reel, even if they only say "edit this video". Runs locally in Claude Code on a Mac.
---

# Talking-head reel

Turns one take of someone talking to camera into a 1080x1920, 30 fps MP4, a cover JPG and a phone preview.

The look is editorial, not auto-captions: serif captions build word by word on the spoken onset, one keyword in the
accent color, the framing changes at every cut, a "Mistake 2/3"-style tracker shows the structure, and fact cards
make viewers pause. `references/style.md` has the full look and the reasons behind it.

**SKILL_DIR** is this file's folder (e.g. `~/.claude/skills/talking-head-reel`). Everything runs through
`SKILL_DIR/reel <command> <reel-dir>`. Each video gets its own **reel folder**, e.g. `~/Reels/2026-11-05-<slug>/`.
The folder name becomes the output file name.

## 0. First time on this Mac
Run `sh SKILL_DIR/scripts/setup.sh`. It only checks. If anything is missing, tell the user what
`sh SKILL_DIR/scripts/setup.sh --install` will do, and run it only with their OK. It runs
`brew install ffmpeg whisper-cpp uv` and downloads the Whisper model (about 466 MB). The user installs Homebrew and
Google Chrome themselves if those are missing. The first `SKILL_DIR/reel` run also fetches Python packages through
uv. If it says permission denied, run `chmod +x SKILL_DIR/reel` (an unzip can drop the flag).

## 1. Read the notes
If `~/Reels/REEL-NOTES.md` exists, read it before anything else. It holds the user's standing decisions (accent
color, caption tweaks, what performed, things to avoid) and the lessons from past reels. Follow it over the
defaults here.

## 2. Analyze the clip
```
SKILL_DIR/reel analyze <reel-dir> --source <clip> [--prompt "Names, brands, jargon"]
```
That takes about 2 minutes for 2 minutes of video. `--prompt` helps Whisper spell names. It writes `analysis/` and a
starter `edit.json`. Leave the clip where it is (edit.json keeps its absolute path); move it into `<reel>/raw/` only
if the user wants a self-contained folder.

Then look before deciding anything:
- **Mirror check.** Read `analysis/frame_top.jpg`, the top of one full-resolution frame. If any background text reads
  backwards, the front camera mirrored it: set `"mirror": true`. The contact sheets are too small to tell.
- **Contact sheets** (`analysis/sheet_*.jpg`, 1 frame per second). Note where the face sits, what's behind it, the
  lighting, and the clothing color against the accent.
- **Warnings.** An HDR warning means make an SDR copy first (see `references/lessons.md`). A "warm colour cast" line
  suggests the `warm-room` grade.
- **The transcript.** Read `analysis/transcript.txt` and the numbered word list. The numbers are how every decision
  is anchored. The "possible mishears" list holds words Whisper was unsure of: check each in context. A real
  mishear ("in" for "to", a garbled name) gets the right word in captions.txt.

## 3. Write the edit: `edit.json` + `captions.txt`
The exact format is in `references/edit-format.md`. A complete worked example is in
`assets/templates/edit.example.json` and `captions.example.txt`; read it once for the format. It's a different video:
never copy its words or chapter titles. Its fact cards are placeholders, because a real card carries only facts the
user gives you.

The decisions that matter:
- **Keep their words.** Pauses are tightened automatically (24 gaps saved 5 s on a 108 s take). Cut content only if
  the user asks. Fix only misheard words, such as names or "than" for "that".
- **Hook first.** The opening sentence is a `[hook]` group, so it's readable from frame 0. If it's a question or a
  warning, make the keyword huge.
- **Find the structure.** "First thing… number two… number three" becomes `[chapter:N]` cards and a tracker.
  The chapter label is the speaker's own word for the points ("Red flag", "Mistake", "Myth", "Step"); leave it
  empty if they don't use one. Without spoken numbers there are no chapters: lean on captions, punch-ins and one or
  two cards instead.
- **Captions.** 2 to 6 words per group, broken at phrase boundaries, 2 lines max. Mark one keyword per group, on the
  word that carries the meaning. Use `[big]` for a question to the viewer or a punchline.
- **Framing.**
  - Every cut already changes framing on its own. Your requests set the character: tight (T) for the hook and
    emotional lines, wide (W) for setup, medium (M) in between.
  - Add a request wherever `reel build` reports a long shot, so nothing runs past about 4 s without a change.
  - Don't sit on T while the end prompt or tags are up: top text lands on the head.
  - Use 4 to 8 snap zooms, on punchlines only.
- **Fact cards** only carry facts the user gave you or confirmed, from a real source, and the card says only what
  the source says. Never invent a number or mock up a journal page or a screenshot.
  - Aim for one every 15 to 25 s, each covering 3 to 5 s of speech.
  - With no verified facts, skip cards; the edit holds up without them.
- **Lists and rapid-fire questions.** When they list items, use `[list]`. When they fire off questions, use
  `[tags]`, worded as the viewer's own thoughts ("What's my level?").
- **End.** One ask, on screen for the last 3 to 5 s, usually a question about the content that takes a one-word or
  number answer ("Which one surprised you most? Comment 1, 2 or 3"). Don't ask viewers to reveal anything personal.
  No end card, no logo.
- **Cover.** Pick the most expressive frame. Write a 2 to 6 word title with the punch in `line2`.
- **Style.** Default accent: green `#4FAE50`. Use the user's notes if they set another color.

## 4. Build and look (cheap, so iterate here)
```
SKILL_DIR/reel build  <reel-dir>
SKILL_DIR/reel stills <reel-dir> 30,450,700,1300,2100,3000 --guides
```
- `build` prints the cuts, shots, cards, chapters and tracker, then what to look at. Fix whatever it reports: a
  word-count mismatch, a long shot, top text over a tight shot, a caption group over 7 words, a card under 3 s.
- `stills` writes full-res PNGs and `build/stills_sheet.jpg`, in half-size tiles, 4 per row. Pick frames for the
  hook, each chapter card, each card (about 20 frames into it), the list, the tags, the end prompt and the last frame.
- With `--guides`, Instagram's UI zones are shaded and a red dashed box marks the face and hair. Check that text
  fits, nothing important sits in a shaded zone, the keyword is readable over the clothes, and no tag, tracker or
  end prompt overlaps the face box. Read a single PNG at full size when the sheet leaves doubt; a 9-minute
  re-render costs more than a closer look.

## 5. Render and check
```
SKILL_DIR/reel render <reel-dir>    # run in the background: 9-10 min for 100 s on an Intel Mac, faster on M-series
SKILL_DIR/reel check  <reel-dir>    # three PASS lines: caption sync, loudness (-14 LUFS), true peak (<= -1.0 dBTP)
SKILL_DIR/reel sheet  <reel-dir>    # frames across the whole master; read them
SKILL_DIR/reel cover  <reel-dir>    # read build/cover_grid_check.jpg: the right side is a real phone grid tile
SKILL_DIR/reel preview <reel-dir>   # optional: exports/<reel>-preview.mp4, 720p under 30 MB, for a phone
```
`render` runs longer than a 10-minute tool timeout, so start it in the background and wait for it to finish. Render
one reel at a time.

## 6. Deliver
- **Files:** `exports/<reel>.mp4` and `exports/<reel>-cover.jpg`. The cover goes in at Edit cover, then Add from
  camera roll.
- **What you did:** a few lines, plus any word you respelled.
- **What to check by ear:** you can't hear the result, so the user should watch it once with sound, for the voice
  processing, the SFX and any music.
- **What's left:** the post caption, and music if there's none.

Then append 3 to 5 lines to `~/Reels/REEL-NOTES.md`: decisions the user made, what you had to fix, and what to do
from the start next time. Create the file if it's missing. This is how the next reel starts smarter.

## Music
By default the file has no music, and the user adds an Instagram sound at low volume. They can also drop a track
they own into `music/`, or generate one with ElevenLabs on their own key; ask before spending. Either way, set
`"music"` in edit.json and run `reel build`. Before the first render, `reel render` picks it up. After a render,
`reel remix` swaps the audio under the same picture in seconds, so a music change never needs a re-render.
Details are in `references/music.md`. Never download music from the web.

## Limits
- You can't hear audio. Say so, and measure what you can.
- macOS only: Avenir Next Condensed is a system font, and Chrome renders the frames.
- Built for a single take to camera. With B-roll or multiple angles, ask how to handle them, and never use stock
  footage the user didn't supply.

## References
- `references/edit-format.md`: every field of edit.json and the captions markup.
- `references/style.md`: the look (type, color, layout, Instagram safe zones, motion, cover) and why.
- `references/music.md`: the three music options, the mixing, and the ElevenLabs flow and costs.
- `references/lessons.md`: mirrored cameras, HDR, Whisper timing, audio and render gotchas.
