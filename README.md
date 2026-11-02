# Talking-head reel skill for Claude Code

This skill lets Claude edit your talking-to-camera videos into finished reels. You get captions, punch-in cuts,
chapter cards, a cover thumbnail and clean audio.

## What you need
- A Mac with **Claude Code**: either the Claude desktop app's **Code** tab, or `claude` in Terminal.
- **Google Chrome**, and **Homebrew** (https://brew.sh).
- About 1 GB free while a reel renders.

## Install (once)
1. In Terminal:
   ```
   git clone https://github.com/waddle36/talking-head-reel.git ~/.claude/skills/talking-head-reel
   ```
   Or click **Code > Download ZIP** on GitHub, unzip it, name the folder `talking-head-reel`, and put it in
   `~/.claude/skills/`.
2. Make a folder for your reels, e.g. `~/Reels`, and open Claude Code in it.
3. The first time, Claude checks your setup and asks before installing anything. It installs ffmpeg, Whisper and uv
   with Homebrew, and downloads a ~466 MB speech model.

To update the skill later: `git -C ~/.claude/skills/talking-head-reel pull`

## Use it
Tell Claude something like:
> Edit this into a reel: ~/Downloads/IMG_1234.mov

Claude transcribes the clip, plans the edit, shows you stills, renders the reel (about 10 minutes) and makes the
cover. Watch it once with sound before posting, because Claude can't hear the result.

## Filming tips that make the edit better
- One take, phone at eye level, in good light, with a mic close to your mouth. Film in 1080p or 4K: a 720p clip
  goes soft on the tight shots.
- Say the structure out loud ("Number one…", "Number two…"). Those become chapter cards and a "2/3" tracker.
- Turn off HDR video (Settings > Camera > Record Video), or Claude will convert the clip first.
- Give Claude the sources for any numbers you want on a fact card. It only puts verified facts on screen.

## Music (optional)
By default there's no music in the file; add an Instagram sound at low volume when you post. If you have an
ElevenLabs account, add `export ELEVENLABS_API_KEY=...` to `~/.zshrc`. Claude can then generate a custom
background track that follows the edit's sections, at about $0.26 per take, and it asks you before spending.

Claude keeps notes on your preferences in `~/Reels/REEL-NOTES.md`, so each reel starts from what you liked last
time.
