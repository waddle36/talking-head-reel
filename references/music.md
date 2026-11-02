# Music

Three ways to do it. Ask the user which one; never download music from the web.

1. **An Instagram sound (the default).** The file goes out with voice and SFX only, and the user adds a track in
   Instagram at low volume (5 to 10%, instrumental). It's free and licensed for personal and creator accounts.
   Business accounts only get Meta's royalty-free library. Instagram plays the track at one flat level and the
   license stays on Instagram.
2. **Their own licensed track.** They put a WAV, MP3 or M4A they have the rights to in `<reel>/music/`. Set
   `"music": {"file": "music/<name>"}` in edit.json, then run `reel build` and `reel remix`. There's no re-render:
   the new audio goes under the same picture in seconds.
3. **Generated with ElevenLabs Music**, with the user's own account and `ELEVENLABS_API_KEY` in their environment.
   This is the best result, because the music is planned around the edit.

## How the bed is mixed (for 2 and 3)
- It's carved out of the voice band (−3 dB at 2.5 kHz), with a slow 2.5:1 compressor so its sections don't
  swing.
- The body section, from chapter 1 to the outro, is set to −25 LUFS.
- It's ducked 5 dB whenever they speak (80 ms attack, 400 ms release), and fades out over the last 1.2 s.
- The result sits about 16 LU under the voice: clear on headphones, subtle on a phone speaker. Change it with
  `"lufs"` (−22 is louder, −28 quieter) and `"duck_db"`.

## Generating with ElevenLabs
```
reel music-plan <reel> --flavor A        # A documentary pulse, B ticking clock, C minimal piano
reel music-gen  <reel> --flavor A --seed 11          # prints the cost, spends nothing
reel music-gen  <reel> --flavor A --seed 11 --yes    # only after the user OKs that cost
```
- The plan has one section per part of the edit: an intro under the hook, one act per chapter, rising tension under
  the tags, and a warm resolve for the close. The music changes where the edit changes.
- It costs about $0.15 per minute at the API list price, so a 100 s reel is about $0.26 a take. On a subscription
  it uses plan credits.
- Each call is logged in `<reel>/music/ledger.csv`. Keep the plan and the seed: the same pair has regenerated an
  identical track.
- Making two or three flavors costs under $1. Let the user pick by ear. You can't hear them, so describe each one
  from the plan and from measurements: LUFS per section, and energy in the voice band, which should be under 5%.
- Whether to label AI-generated music on the post is the user's call.

## Measuring a take without ears
Use ffmpeg `ebur128` per section, from the timeline's section times. Look for:
- a quiet intro
- an even body
- a lift under the tension section
- a softer resolve
- a clean decay to silence at the end

Then check how much energy sits in the 1 to 4 kHz band. If it's high, the track will fight the voice, so try
another seed.
