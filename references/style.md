# The look, and why

An editorial look: serif captions with one colored italic keyword, a numbered list, wide/tight cuts every few
seconds, and off-white fact cards. It was refined on a 103 s talking head in October 2026. The aim is editorial,
not template: it should read like a magazine designed it, not like auto-captions.

## What holds attention, in order of weight
1. **The hook is on screen from frame 0.** People read faster than they listen, and the feed autoplays muted. The
   whole opening question sits big in the lower middle before the first word is spoken.
2. **A visible structure.** "3 mistakes" at the top, then "Mistake 2/3" and the point's title, so the viewer
   always knows there's more coming. A chapter card (big numeral over the blurred shot) marks each new point.
3. **Something changes every 2 to 4 s.** The framing changes at every jump cut, there's a punch-in on long
   stretches, a card every 15 to 25 s, and a list or tags where the speaker lists things. Never two of these at
   once.
4. **Fact cards are pause-bait.** A real number with its source makes viewers pause the video. Only use facts the
   user has verified.
5. **One ask at the end.** A question for the comments in the last 4 s, over the speaker's face, with no end card.

## Picture
- Output 1080x1920, 30 fps. The source is upscaled 2x (lanczos plus light sharpening) so the tight framing is
  roughly 1:1 with the source pixels.
- **Un-mirror** front-camera footage. Backwards background text looks amateur, and readable book spines add
  personality.
- Framings, anchored on the tracked face: WIDE 1.00 (face where it is), MEDIUM 1.17 and TIGHT 1.33 (face at 35%
  height, which leaves the top tracker clear of the hair). Each shot pushes in 1.6%, so the camera feels alive. Snap zoom: +0.085 over 6 frames, on
  punchlines only. Overused, it feels frantic.
- Grade presets: `neutral` (a gentle contrast lift and highlight roll-off) or `warm-room` (also cools a
  yellow lamp cast). Never push skin tones.
- A vignette, a dark gradient under the captions (it also tames bright desks), and a light one under the tracker.

## Type and color
- Captions: Playfair Display 700, white, soft dark shadow, 70 px (86 px for `[big]`). The keyword is Playfair
  Display Italic 800 in the accent color, with a dark outline painted under the fill. Without the outline, a
  green keyword vanished over a green shirt.
- Labels, kickers and source lines: Avenir Next Condensed (a macOS system font), uppercase, tracked out.
- Palette defaults: green `#4FAE50` is the only accent. Cards and tags are linen `#E4DFD7` with
  charcoal `#272526` type, and the card highlighter is the accent at 40%. One accent color only.
- On screen, no em dashes, arrows or emojis, and none in the post copy either.

## Layout and Instagram's UI
- Caption block bottom at y=1400; text inside x 90 to 930. Instagram's buttons cover the right edge below
  y≈980, and its caption and username cover the bottom ~420 px. `reel stills --guides` shades these zones.
- Tracker at y≈246, inside a frosted dark box; the top ~230 px has Instagram's header.
- Cards are centred around y=880 and can cover the face, because the shot behind them is blurred and darkened.

## Motion (all of it is a function of the frame number, so renders are repeatable)
- Caption words rise 20 px and fade in over 4 frames on their spoken onset, and the keyword pops from 112%.
- Cards slide up 260 px with a slight overshoot and a −1.2° rest angle. The highlighter sweeps 13 frames after.
  They exit by dropping 110 px over 7 frames.
- Chapter card: the numeral settles from 122% over 9 frames, the title rises after it, and the whole card lifts
  away over the last 6 frames.
- The blur behind cards ramps over 6 frames at each end.

## Cover (thumbnail)
- The profile grid shows a 3:4 centre crop (y 240 to 1680 of the 1920 frame) at about 393 px wide on a phone, and
  the feed shows a 4:5 crop (y 285 to 1635). The face and title must both sit inside both crops.
- An optional small accent tag, a white line, then 1 to 3 huge words in the accent italic, over a dark gradient.
  Use the most expressive frame: a raised finger or a direct look. `reel cover` writes a grid-size check; if the
  big line doesn't read at tile size, cut words.

## Sound
- Voice: high-pass 70 Hz, −1.5 dB at 250 Hz, +2 dB at 3.8 kHz, a spike limiter, then +12 dB, a 4:1 compressor and
  a de-esser. The mix is −14 LUFS, which matches Instagram's playback level. It's limited at −1.5 dBTP; the AAC
  encode reads about 0.1 dB higher, and anything at or under −1.0 is fine.
- Every cut gets an 8 ms fade, so nothing clicks.
- SFX are synthesized and quiet: a whoosh into each card, a low thump under each chapter numeral, and a tick on
  list items, tags and the end prompt.
- Music, when used, sits about 16 LU under the voice (see `music.md`).
