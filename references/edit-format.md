# The edit: `edit.json` + `captions.txt`

Two files in the reel folder hold every decision. `reel build` turns them into `build/timeline.json`.
A complete worked example (a 70 s "3 mistakes" reel) is in `assets/templates/edit.example.json` and
`assets/templates/captions.example.txt`. Read those once before writing your first edit. Its fact cards are
placeholders.

Word numbers below are the indices printed by `reel analyze` (also `analysis/words.json`, 0-based). Times are
never written by hand: everything is anchored to words, and the builder pins each word to real speech.

## captions.txt

One line per caption group, in spoken order. The words map 1:1 onto the transcript words, so every transcript word
appears exactly once, in order. `reel build` stops and names the next words if the count is off.

```
[hook] {s}Why does everyone / {l}*scroll past* / {l}*your videos?*
Let's fix it.
There are *three mistakes*
I see in almost / *every video*
[chapter:1] Mistake number one, you start slow.
[big] If I don't know / where this is *going,*
[hide:cardB] A number gives the viewer a finish line and a reason to stay until the very end,
[list] the problem, the promise or the surprise.
[tags] okay, now what, was that it, should I follow, where's the link, what do I do,
```

- **Line prefix** (optional):
  - none: a normal caption. Words build in one at a time as they're spoken.
  - `[hook]`: the whole group is on screen at once. Use it for the opening line, which should be readable from
    frame 0. The first group starts at frame 0 automatically.
  - `[big]`: bigger type, for a punchline or a question to the viewer.
  - `[chapter:N]`: no caption. A chapter card covers these words (title from `chapters.N`).
  - `[hide:ID]`: no caption. Fact card `cards.ID` covers these words.
  - `[list]`: no caption. The `list` block shows these words as items.
  - `[tags]`: no caption. The `tags` block pops these words as paper tags.
- ` / ` breaks the line. Two lines is the norm; a hook can take three.
- `{s}`, `{l}`, `{xl}` at the start of a line make that line smaller or larger (mostly inside `[hook]`).
- `*word*` or `*two words*` marks the keyword, drawn italic in the accent color. Use one per group, on the word
  that carries the meaning; never mark a filler word.
- Fix only what the transcript misheard: name spellings, homophones ("than" for "that"). `reel build` prints
  every word you changed, so check that list. Keep the speaker's own words, and never add or drop a word.
- Group size: 2 to 6 words, broken at phrase boundaries (commas, "and", "but", "that").
- Lines starting with `#` are comments.

## edit.json

```jsonc
{
  "source": "raw/IMG_1234.mov",          // relative to the reel folder, or absolute
  "title": "Why people scroll past your videos",
  "mirror": true,                        // front camera mirrored the picture (background text reads backwards)
  "grade": "neutral",                    // "neutral" | "warm-room" (lamp-lit rooms; analyze suggests it) | "none"
  "pauses": {"cut_min": 0.22, "keep_after": 0.07, "keep_after_sentence": 0.10, "keep_before": 0.05},
  "tail_hold_frames": 12,                // hold the last frame 0.4 s after the clip ends

  "shots": [[0, "T"], [7, "M"], [14, "W"]],   // [word, framing]: W wide 1.0, M medium 1.17, T tight 1.33
  "snaps": [10, 63, 130],                      // words that get a quick zoom-in (punchlines only, 4 to 8 a reel)
  "push_overrides": [[186, 0.05]],             // [word, push]: a stronger slow push for the shot holding that word

  "chapter_kicker": "Mistake",           // small label above the chapter numeral ("" hides it)
  "chapters": {"1": {"title": "You start / slow", "short": "Starting slow"}},
  "tracker": {                           // the label at the top; every part is optional
    "intro": {"word": 16, "label": "<em>3</em> mistakes"},     // from this word to chapter 1
    "chapter_label": "Mistake",                                // becomes "Mistake 2/3" + the chapter's short title
    "outro": {"word": 232, "label": "The fix"}                 // from this word to the end prompt
  },

  "cards": {                             // fact cards, keyed by the [hide:ID] in captions.txt
    "cardB": {
      "kick": "Who ran it &middot; what they measured",
      "stat": "3 <i>of</i> 4",                                   // optional big number
      "body": "what the number counts, worded as the source words it. <mark>The phrase that matters.</mark>",
      "note": "optional second line under a rule",
      "src": "Author, et al. Journal. Year &middot; PMID"
    }
  },
  "list": {"label": "Open with", "items": [[89, "The problem"], [91, "The promise"]]},
  "tags": {"items": [[191, "Okay, now what?", 70, 262, -3.0]], "out_word": 207},   // [word, text, x, y, rotation]
  "end": {"word": 256, "q": "Which one are you fixing first?", "cta": "Comment 1, 2 or 3"},

  "cover": {"frame": 22, "kicker": "3 mistakes", "line1": "Why people scroll past", "line2": "your videos",
            "zoom": 1.3, "face_y": 0.31},
  "style": {"accent": "#4FAE50", "paper": "#E4DFD7", "ink": "#272526", "highlight": "rgba(79, 174, 80, .40)"},
  "music": {"file": "music/A_s11.wav", "lufs": -25, "duck_db": 5},   // or null for no music
  "sfx": true                            // soft synthesized whoosh, thump and tick on the graphics
}
```

Notes on each block:

- **shots.** A shot starts at every cut, plus at each requested word that has no cut within 0.45 s before it. A shot
  that would repeat the previous framing flips to its alternate, because a jump cut needs a framing change to hide
  it. A punch-in that lands on the edge of a blurred card is moved inside the blur. `reel build` lists every shot
  that stays on screen longer than 4.5 s; add a request inside each one. It also flags tight shots under the end
  prompt or tags.
- **chapters.** Each title is the speaker's point in a few words. ` / ` breaks the title line. `short` is the
  tracker text.
- **cards.** The text is HTML. `<mark>` gets the highlighter sweep; use one per card, on the phrase that matters.
  `&nbsp;` keeps a phrase together; `&#8209;` is a non-breaking hyphen. A card covers the hidden words plus a few
  frames, so 10 to 18 hidden words gives 3 to 5 s, which is enough to read it. Space cards 15 s or more apart.
- **list.** Each item appears on its word, at the left of the frame under a small label.
- **tags.** x and y are in pixels on the 1080x1920 frame, for the tag's top-left corner. Keep them off the face and
  inside x 60 to 940. The face moves with the framing, so check `reel stills --guides` (red face box) on the
  actual frames. A tag at (560, 392) once touched the hair on a tight shot. Above the head (y 240 to 330) and the
  chest (y 950 to 1250) are the safe bands. They clear on `out_word`, and the top tracker hides while they're up.
- **end.** One call to action, on screen for the last 3 to 5 s. A question for the comments works best. Leave out
  `cta` for just the question. The pills sit at y 236 to about 420, so keep the shot W or M while they're up.
- **cover.** `frame` is an output frame. Pick one with an open, expressive face, from `reel stills`. Two to six
  words in `line1` and `line2` read at grid size; `line2` is the big accent line.
- **style.** The defaults are a green accent, linen cards and charcoal type. Change `accent` for a different brand
  color; the keyword gets a dark outline, so it stays readable over clothing in a similar color.
