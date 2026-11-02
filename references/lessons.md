# Lessons (things that went wrong once)

- **Mirrored front camera.** Look at a contact sheet: if any text reads backwards, set `"mirror": true`. The
  builder flips the face track with it.
- **HDR iPhone footage** (`transfer` arib-std-b67 or smpte2084 in `analysis/source.json`) looks washed out
  through this SDR grade. Make an SDR copy with macOS's own tool and edit that:
  `avconvert --source IN.mov --preset PresetHighestQuality --output IN-sdr.mov`. Better still, ask the user to
  film with HDR Video off (Settings > Camera > Record Video).
- **Don't trust Whisper for timing.** Its word times drift into pauses. The builder pins every onset to the speech
  envelope, and `reel check` confirms it: expect 0 caption words in a pause.
- **Color clashes with clothing.** An accent close to the shirt's color disappears. The keyword's dark outline
  handles it; check a still where the keyword sits over the shirt.
- **Audio.**
  - ffmpeg's `deesser` blows up on samples above full scale, so the chain limits spikes first and de-esses last.
  - A mono voice copied to both channels measures 3 LU louder, so the chain aims the mono 3 LU low.
  - The pre-limiter mix goes to the limiter as float, never 16-bit, or it hard-clips.
- **Render time.** About 5.5 fps on a 2018 Intel Mac mini, so a 100 s reel takes 9 to 10 minutes; Apple Silicon is
  faster. Run `reel render` in the background, because it outlasts a 10-minute tool timeout. Render one reel at a
  time.
- **OpenCV 5 dropped the Haar face detector.** The `./reel` wrapper pins `opencv-python-headless<5`.
- **Card exits.** A punch-in in the last frames of a blurred card flashes the old framing. The builder moves it
  inside the blur, so don't fight that.
- **Top text over a tight shot** (the tracker, end prompt or a tag) lands on the hair. `reel build` warns, and
  `reel stills --guides` draws the face box. On one test this cost a full re-render because the small sheet hid it.
- **Words bunched at a cut.** Whisper can put two or three words inside a removed pause, so they pinned to the same
  frame and popped in together. The builder now spreads them 2 frames apart.
- **720p sources** go soft on the tight framing (about 2x upscale). Ask for 1080p or 4K, and never a re-export at
  720p.
- **Paid outputs live in the reel folder,** never in a temp folder. `/tmp` gets cleared and takes them with it.
- **Phone delivery caps at about 30 MB.** `reel preview` makes a 720p copy (about 25 MB for 100 s); post the
  full-res master.
