"""Optional music: a plan whose sections follow the reel, and an ElevenLabs Music call with the user's own key.

`reel music-plan <reel> --flavor A`   writes <reel>/music/plan_A.json from the timeline (chapter starts, outro,
                                       tags), so the music changes where the edit changes
`reel music-gen <reel> --flavor A --seed 11 [--yes]`
                                       prints the cost first; spends only with --yes. Needs ELEVENLABS_API_KEY in the
                                       environment (the user's own account). Logs every call to <reel>/music/ledger.csv.
The same plan and seed have regenerated an identical track, so keep both.
"""
import csv
import datetime
import json
import os
import urllib.error
import urllib.request

FPS = 30
PRICE_PER_MIN = 0.15        # ElevenLabs API list price for music; on a subscription it spends plan credits instead
NEG = ["vocals", "choir", "spoken word", "humming", "EDM", "drop", "dubstep", "trap hi-hats", "epic trailer drums",
       "trailer braams", "horror", "jump scare", "rock guitar", "saxophone", "lo-fi", "vinyl crackle", "ukulele",
       "whistling", "generic corporate stock music", "loud lead melody", "big drum fill", "sudden loud hits"]
FLAVORS = {
    'A': {'name': 'documentary pulse',
          'base': ["modern documentary score", "investigative, serious, restrained", "minimal organic-electronic",
                   "pristine modern production, controlled, not busy"],
          'intro': "{a soft muted synth pulse on 8th notes, very quiet sub bass, a delicate high tick, airy pad}\n{tense, poised, quiet}",
          'acts': ["{the pulse settles into a steady low groove: muted synth bass 8ths, soft brushed percussion, a few sparse high felt-piano notes, wide warm pad}\n{focused, investigative, constant level}",
                   "{the same groove continues; a low cello-like pad joins and a soft rimshot lands on beats 2 and 4}\n{a touch more tension, constant level}",
                   "{the same groove with a little more drive: a soft muted kick on every beat and a light 16th-note shaker}\n{still restrained, background}"],
          'tension': "{tension rises: the ticking gets busier, a low uneasy drone grows, a slow gentle riser builds}\n{uncertain, searching, building}",
          'resolve': "{the tension releases into warm major chords on soft felt piano and pads, calm and hopeful; the pulse stops; it ends on one sustained warm chord with a long natural decay}"},
    'B': {'name': 'ticking clock',
          'base': ["modern organic-electronic score", "clockwork tension, precise, restrained", "premium brand film underscore",
                   "pristine modern production, wide stereo, tight and controlled"],
          'intro': "{a clock-like high tick on 8th notes and a soft sub kick on beat one of each bar, airy texture}\n{tense, poised, quiet}",
          'acts': ["{a steady pulse: soft sub kick on beats 1 and 3, the tick continues, muted plucked synth 8ths, a low warm pad}\n{focused, constant level}",
                   "{the same pulse; a soft shaker and a low bass note on each bar join}\n{a touch more urgency, constant level}",
                   "{the same pulse with a little more drive: kick on every beat, plucks in 16ths, still quiet and controlled}"],
          'tension': "{the ticks speed up and stack, a low drone grows, a slow gentle riser builds}\n{uncertain, building}",
          'resolve': "{everything rhythmic stops; warm sustained pads and a soft low piano chord, calm and resolved; it ends on one sustained warm chord with a long natural decay}"},
    'C': {'name': 'minimal piano',
          'base': ["minimal cinematic documentary score", "serious, thoughtful, warm undertone", "felt piano and soft strings",
                   "intimate, restrained, pristine production"],
          'intro': "{a quiet repeating low felt-piano ostinato in 8th notes, a soft sustained cello note underneath}\n{thoughtful, tense, quiet}",
          'acts': ["{the same piano ostinato continues steadily, a soft pulsing low string pad joins, very light percussion}\n{focused, serious, constant level}",
                   "{the ostinato continues; a second soft string layer and a muted heartbeat-like low pulse join}\n{a touch more tension, constant level}",
                   "{the ostinato with a little more motion: pizzicato strings in 8ths and a soft low pulse on every beat}\n{still restrained}"],
          'tension': "{tension rises: the strings slowly swell, a low dissonant cluster grows, the ostinato gets more insistent}\n{uncertain, building}",
          'resolve': "{the tension releases into warm major piano chords and soft strings, calm and hopeful; it ends on one sustained warm chord with a long natural decay}"},
}


def sections(T):
    """[(role, start_s, end_s)]: intro, one act per chapter, a tension section under the tags, then the resolve"""
    N = T['frames']
    chs = sorted(T['chapters'], key=lambda c: c['f0'])
    tr_out = T.get('outro')
    tags = T.get('tags')
    marks = [(0, 'intro')] + [(c['f0'], f'act{k}') for k, c in enumerate(chs)]
    if tags:
        marks += [(tr_out if tr_out and tr_out < tags['f0'] else tags['f0'], 'tension'), (tags['out'], 'resolve')]
    elif tr_out:
        marks.append((tr_out, 'resolve'))
    else:
        marks.append((max(marks[-1][0] + 5 * FPS, N - 8 * FPS), 'resolve'))
    marks = sorted(dict(marks).items())
    out = []
    for k, (f, role) in enumerate(marks):
        f1 = marks[k + 1][0] if k + 1 < len(marks) else N
        if f1 - f >= FPS:
            out.append((role, f / FPS, f1 / FPS))
    return out


def plan(T, flavor='A', bpm=94):
    F = FLAVORS[flavor]
    chunks = []
    secs = sections(T)
    for i, (role, a, b) in enumerate(secs):
        ms = int(round((b - a) * 1000)) + (1000 if i == len(secs) - 1 else 0)   # a 1 s tail after the end
        if role.startswith('act'):
            k = int(role[3:])
            text, label = F['acts'][min(k, len(F['acts']) - 1)], f'Act {k + 1}'
            extra = ['constant level, no fade'] + (['same groove as before', 'subtle new layer'] if k else ['steady groove'])
        else:
            text, label = F[role], {'intro': 'Intro', 'tension': 'Rising tension', 'resolve': 'Resolve'}[role]
            extra = {'intro': ['sparse', 'minimal'], 'tension': ['building tension', 'slow riser'],
                     'resolve': ['warm, resolved', 'one sustained chord', 'long natural decay']}[role]
        chunks.append({'text': f'[{label}]\n{text}', 'duration_ms': ms,
                       'positive_styles': ['instrumental', 'background underscore for a person talking to camera, '
                                           'leaves the mid-range clear for a voice', f'{bpm} BPM, 4/4', 'constant tempo']
                       + F['base'] + extra,
                       'negative_styles': NEG + (['drums'] if role in ('intro', 'resolve') else []),
                       'context_adherence': 'high' if i == 0 else 'low'})
    return {'chunks': chunks}


def write_plan(R, flavor='A'):
    d = os.path.join(R.dir, 'music')
    os.makedirs(d, exist_ok=True)
    p = plan(R.tl, flavor)
    path = os.path.join(d, f'plan_{flavor}.json')
    json.dump(p, open(path, 'w'), indent=1)
    total = sum(c['duration_ms'] for c in p['chunks']) / 1000
    print(f"{path}: {FLAVORS[flavor]['name']}, {len(p['chunks'])} sections, {total:.1f} s, "
          f"about ${total / 60 * PRICE_PER_MIN:.2f} at the API list price")
    for c in p['chunks']:
        print(f"  {c['duration_ms'] / 1000:6.2f} s  {c['text'].splitlines()[0]}")
    return path


def generate(R, flavor='A', seed=11, yes=False):
    path = os.path.join(R.dir, 'music', f'plan_{flavor}.json')
    if not os.path.exists(path):
        path = write_plan(R, flavor)
    p = json.load(open(path))
    secs = sum(c['duration_ms'] for c in p['chunks']) / 1000
    cost = secs / 60 * PRICE_PER_MIN
    out = os.path.join(R.dir, 'music', f'{flavor}_s{seed}.wav')
    print(f'ElevenLabs Music, {secs:.1f} s: about ${cost:.2f} at the API list price (plan credits on a subscription)')
    if not yes:
        print('Not spent. Re-run with --yes once the user has OK\'d the cost.')
        return None
    key = os.environ.get('ELEVENLABS_API_KEY')
    if not key:
        raise SystemExit('ELEVENLABS_API_KEY is not set. It must be the user\'s own key; never print it.')
    body = json.dumps({'model_id': 'music_v2_5', 'composition_plan': p, 'seed': seed}).encode()
    req = urllib.request.Request('https://api.elevenlabs.io/v1/music?output_format=pcm_48000', data=body, method='POST',
                                 headers={'xi-api-key': key, 'Content-Type': 'application/json'})
    t0 = datetime.datetime.now()
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            data, song = r.read(), r.headers.get('song-id', '')
    except urllib.error.HTTPError as ex:
        raise SystemExit(f'ElevenLabs refused the request: HTTP {ex.code} {ex.read()[:300]!r}')
    import wave
    ch = max(1, round(len(data) / (48000 * 2 * secs)))
    with wave.open(out, 'wb') as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(data[: len(data) - len(data) % (2 * ch)])
    led = os.path.join(R.dir, 'music', 'ledger.csv')
    new = not os.path.exists(led)
    with open(led, 'a', newline='') as f:
        wr = csv.writer(f)
        if new:
            wr.writerow(['time', 'flavor', 'seed', 'seconds', 'est_usd_list_price', 'song_id', 'file'])
        wr.writerow([t0.isoformat(timespec='seconds'), flavor, seed, round(secs, 2), round(cost, 4), song, out])
    print(f'{out} ({ch} ch). Logged in {led}. Set edit.json "music": {{"file": "music/{os.path.basename(out)}"}}, '
          f'then `reel build` and `reel remix`.')
    return out
