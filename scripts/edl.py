"""Build <reel>/build/timeline.json from the reel's edit decisions.

Inputs, all inside the reel folder:
  edit.json      the decisions: source, mirror, framing requests, chapters, cards, list, tags, end prompt, cover
  captions.txt   one caption group per line, mapped 1:1 onto the transcript words (markup in references/edit-format.md)
  analysis/      words.json, speech.json, face.json (written by `reel analyze`)

Every caption word is pinned to real speech: a word whose transcript start lands in a pause moves to the end of
that pause. Every output frame is described: which source frame, which framing, which captions and graphics.
"""
import json
import math
import os
import re

FPS = 30
ALT = {'W': 'M', 'M': 'W', 'T': 'M'}
DEFAULTS = {
    'mirror': False,
    'grade': 'neutral',
    'pauses': {'cut_min': 0.22, 'keep_after': 0.07, 'keep_after_sentence': 0.10, 'keep_before': 0.05},
    'tail_hold_frames': 12,
    'framing': {'W': 1.0, 'M': 1.17, 'T': 1.33},
    'face_y': {'W': 0.36, 'M': 0.35, 'T': 0.35},      # T at 0.35 leaves the tracker clear of the hair
    'push': 0.016,
    'snap_dz': 0.085,
    'shots': [[0, 'T']],
    'snaps': [],
    'push_overrides': [],
    'chapters': {},
    'chapter_kicker': '',
    'tracker': {},
    'cards': {},
    'style': {'accent': '#4FAE50', 'paper': '#E4DFD7', 'ink': '#272526', 'highlight': 'rgba(79, 174, 80, .40)'},
    'sfx': True,
}


def norm(w):
    return re.sub(r"[^a-z0-9']", '', w.lower())


def load_edit(reel):
    e = json.load(open(os.path.join(reel, 'edit.json')))
    for k, v in DEFAULTS.items():
        if k not in e:
            e[k] = v
        elif isinstance(v, dict) and isinstance(e[k], dict) and k in ('pauses', 'framing', 'face_y', 'style'):
            e[k] = {**v, **e[k]}
    return e


def parse_captions(text, words):
    """caption markup -> groups of {kind, lines, words[{t, key, line, wi}]}; checks the 1:1 word mapping"""
    groups, i = [], 0
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw or raw.startswith('#'):
            continue
        kind = 'cap'
        m = re.match(r'\[([^\]]+)\]\s*(.*)', raw)
        if m:
            kind, raw = m.group(1), m.group(2)
        lines, toks, key = [], [], False
        for li, line in enumerate(raw.split(' / ')):
            size = 'n'
            m = re.match(r'\{(s|l|xl)\}(.*)', line)
            if m:
                size, line = m.group(1), m.group(2)
            lines.append(size)
            for tok in line.split():
                starts, ends = tok.startswith('*'), tok.endswith('*')
                if starts:
                    key = True
                if i >= len(words):
                    raise SystemExit(f'captions.txt has more words than the transcript ({len(words)}); stopped at "{tok}"')
                text_tok = tok.strip('*')
                toks.append({'t': text_tok, 'key': key, 'line': li, 'wi': i})
                if norm(text_tok) != norm(words[i]['w']):
                    print(f'  word {i}: shows "{text_tok}" for transcript "{words[i]["w"]}"')
                if ends:
                    key = False
                i += 1
        groups.append({'kind': kind, 'lines': lines, 'words': toks})
    if i != len(words):
        nxt = ' '.join(w['w'] for w in words[i:i + 8])
        raise SystemExit(f'captions.txt covers {i} words, the transcript has {len(words)}. Next words: "{nxt}"')
    return groups


def build(reel, build_dir=None):
    E = load_edit(reel)
    A = os.path.join(reel, 'analysis')
    words = json.load(open(os.path.join(A, 'words.json')))
    sp = json.load(open(os.path.join(A, 'speech.json')))
    face = json.load(open(os.path.join(A, 'face.json')))
    meta = json.load(open(os.path.join(A, 'source.json')))
    SRC_FRAMES = int(round(meta['duration'] * FPS))
    pauses = sp['pauses']
    P = E['pauses']

    def pin_start(t):
        for p0, p1 in pauses:
            if p0 <= t < p1:
                return p1
        return t

    def pin_end(t):
        for p0, p1 in pauses:
            if p0 < t <= p1:
                return p0
        return t

    starts = [pin_start(w['a']) for w in words]
    ends = [max(pin_end(w['b']), s + 0.05) for w, s in zip(words, starts)]

    # cuts: tighten every pause >= cut_min, quantized to frames; the audio uses the same frame boundaries
    removed = []
    for p0, p1 in pauses:
        if p1 - p0 < P['cut_min']:
            continue
        before = [k for k, s in enumerate(starts) if s < p0]
        sent = bool(before) and words[before[-1]]['w'].rstrip()[-1:] in '.?!'
        r0 = math.ceil((p0 + (P['keep_after_sentence'] if sent else P['keep_after'])) * FPS)
        r1 = math.floor((p1 - P['keep_before']) * FPS)
        if r1 - r0 >= 2:
            removed.append((r0, min(r1, SRC_FRAMES)))
    kept, prev = [], 0
    for r0, r1 in removed:
        kept.append((prev, r0))
        prev = r1
    kept.append((prev, SRC_FRAMES))
    tail = int(E['tail_hold_frames'])
    src_frames = [f for a, b in kept for f in range(a, b)] + [SRC_FRAMES - 1] * tail
    N = len(src_frames)

    def out_frame(t):
        f, off = t * FPS, 0
        for a, b in kept:
            if f < a:
                return off
            if f < b:
                return off + (f - a)
            off += b - a
        return off

    joins, off = [], 0
    for a, b in kept[:-1]:
        off += b - a
        joins.append(off)

    wf = [max(0, min(round(out_frame(s)) - 1, N - 1)) for s in starts]   # appear one frame ahead of the onset
    for i in range(1, len(wf)):   # words pinned to the same join after a cut would pop in together: spread them
        if wf[i] < wf[i - 1] + 2 and wf[i - 1] + 2 - wf[i] <= 6:
            wf[i] = min(wf[i - 1] + 2, N - 1)
    we = [max(f + 2, round(out_frame(e))) for f, e in zip(wf, ends)]
    groups = parse_captions(open(os.path.join(reel, 'captions.txt')).read(), words)

    captions, chapters, cards, sfx = [], [], [], []
    list_block = tags_block = None
    for gi, g in enumerate(groups):
        w0, w1 = g['words'][0]['wi'], g['words'][-1]['wi']
        kind = g['kind']
        nxt = wf[w1 + 1] if w1 + 1 < len(words) else N
        if kind.startswith('chapter:'):
            n = int(kind.split(':')[1])
            ch = E['chapters'].get(str(n), {})
            f0, f1 = wf[w0] - 2, min(we[w1] + 8, nxt - 1)
            chapters.append({'n': n, 'f0': max(0, f0), 'f1': f1, 'title': ch.get('title', ''),
                             'short': ch.get('short', ch.get('title', '').replace(' / ', ' '))})
            sfx += [{'f': max(0, f0), 'kind': 'whoosh'}, {'f': max(0, f0) + 3, 'kind': 'thump'}]
        elif kind.startswith('hide:'):
            cid = kind.split(':')[1]
            if cid not in E['cards']:
                raise SystemExit(f'captions.txt hides words for card "{cid}" but edit.json has no cards.{cid}')
            f0, f1 = wf[w0] - 3, min(we[w1] + 4, nxt - 1)
            cards.append({'id': cid, 'f0': max(0, f0), 'f1': f1, **E['cards'][cid]})
            sfx.append({'f': max(0, f0), 'kind': 'whoosh'})
        elif kind == 'list':
            L = E['list']
            items = [{'f': wf[wi], 'text': text} for wi, text in L['items']]
            list_block = {'f0': items[0]['f'], 'f1': nxt - 1, 'label': L.get('label', ''), 'items': items}
            sfx += [{'f': it['f'], 'kind': 'tick'} for it in items]
        elif kind == 'tags':
            G = E['tags']
            items = [{'f': wf[wi], 'text': text, 'x': x, 'y': y, 'r': r} for wi, text, x, y, r in G['items']]
            out = wf[G['out_word']]
            tags_block = {'f0': items[0]['f'], 'f1': out + 6, 'out': out, 'items': items}
            sfx += [{'f': it['f'], 'kind': 'tick'} for it in items] + [{'f': out, 'kind': 'whoosh'}]
        else:
            ws = [{'t': w['t'], 'key': w['key'], 'line': w['line'], 'f': wf[w['wi']]} for w in g['words']]
            captions.append({'kind': kind, 'lines': g['lines'], 'words': ws, 'f0': ws[0]['f'], 'last_end': we[w1]})
    if captions and groups[0]['kind'] in ('cap', 'hook', 'big'):
        captions[0]['f0'] = 0                      # the hook is on screen from the very first frame
    blocks = ([c['f0'] for c in chapters] + [c['f0'] for c in cards]
              + ([list_block['f0']] if list_block else []) + ([tags_block['f0']] if tags_block else []))
    starts_all = sorted([c['f0'] for c in captions] + blocks)
    for c in captions:   # a group holds until the next group or block, at most 0.6 s past its last word
        later = [s for s in starts_all if s > c['f0']]
        c['f1'] = min(later[0] if later else N, c['last_end'] + 18)
    if captions and not [b for b in blocks if b > captions[-1]['f0']]:
        captions[-1]['f1'] = N                     # the last line stays up to the end

    # end prompt and tracker
    end_prompt = None
    if E.get('end'):
        end_prompt = {'f0': wf[E['end']['word']], 'q': E['end'].get('q', ''), 'cta': E['end'].get('cta', '')}
        sfx.append({'f': end_prompt['f0'], 'kind': 'tick'})
    stop = end_prompt['f0'] if end_prompt else N
    TR = E['tracker'] or {}
    states = []
    chs = sorted(chapters, key=lambda c: c['f0'])
    outro_f = wf[TR['outro']['word']] if TR.get('outro') else None
    if TR.get('intro'):
        f0 = wf[TR['intro']['word']]
        f1 = chs[0]['f0'] if chs else (outro_f or stop)
        states.append({'f0': f0, 'f1': f1, 'label': TR['intro']['label'], 'title': ''})
    if chs and TR.get('chapter_label') is not None:
        for k, c in enumerate(chs):
            f1 = chs[k + 1]['f0'] if k + 1 < len(chs) else (outro_f or stop)
            states.append({'f0': c['f1'] - 4, 'f1': f1, 'label': f"{TR['chapter_label']} <em>{c['n']}/{len(chs)}</em>",
                           'title': c['short']})
    if TR.get('outro'):
        states.append({'f0': outro_f, 'f1': stop, 'label': TR['outro']['label'], 'title': ''})
    if tags_block:   # the tags take over the top of the frame: hide the tracker under them
        cut = []
        for s in states:
            if s['f1'] <= tags_block['f0'] or s['f0'] >= tags_block['f1']:
                cut.append(s)
                continue
            if s['f0'] < tags_block['f0']:
                cut.append({**s, 'f1': tags_block['f0']})
            if s['f1'] > tags_block['f1']:
                cut.append({**s, 'f0': tags_block['f1']})
        states = cut
    states = [s for s in states if s['f1'] - s['f0'] > 6]

    # shots: a new shot at every cut; framing requests at words; never the same framing across a cut
    shot_starts = {j: None for j in joins}
    for wi, fr in E['shots']:
        f = wf[wi]
        near = [j for j in joins if f - round(0.45 * FPS) <= j <= f + 3]
        shot_starts[near[-1] if near else f] = fr
    joinset = set(joins)
    for b in chapters + cards:   # keep punch-ins off the edges of blurred cards, so nothing flashes on exit
        for f in sorted(shot_starts):
            if f in joinset:
                continue
            fr = shot_starts[f]
            if b['f0'] < f <= b['f0'] + 8:
                del shot_starts[f]
                shot_starts[b['f0']] = fr
            elif b['f1'] - 8 <= f <= b['f1'] + 8:
                del shot_starts[f]
                shot_starts[b['f1'] - 9] = fr
    shot_starts[0] = next((fr for wi, fr in E['shots'] if wi == 0), 'T')
    fs = sorted(shot_starts)
    shots, cur = [], None
    for k, f in enumerate(fs):
        fr = shot_starts[f] or (ALT[cur] if cur else 'W')
        if fr == cur:
            fr = ALT[cur]
        f1 = fs[k + 1] if k + 1 < len(fs) else N
        if f1 - f < 1:
            continue
        cur = fr
        shots.append({'f0': f, 'f1': f1, 'fr': fr})

    def face_at(f0, f1):
        """median face centre over the shot's source frames (un-mirrored when the clip is flipped)"""
        if not face.get('t'):
            return 0.5, 0.36
        idx = sorted({min(len(face['t']) - 1, round(s / FPS * face['fps'])) for s in src_frames[f0:f1]})
        cx = sorted((1 - face['cx'][i]) if E['mirror'] else face['cx'][i] for i in idx)
        cy = sorted(face['cy'][i] for i in idx)
        return cx[len(cx) // 2], cy[len(cy) // 2]

    def face_w(f0, f1):
        if not face.get('fw'):
            return 0.25
        idx = sorted({min(len(face['t']) - 1, round(s / FPS * face['fps'])) for s in src_frames[f0:f1]})
        return sorted(face['fw'][i] for i in idx)[len(idx) // 2]

    snap_frames = [wf[wi] for wi in E['snaps']]
    overrides = [(wf[wi], p) for wi, p in E['push_overrides']]
    for s in shots:
        s['z'] = E['framing'][s['fr']]
        s['oy'] = E['face_y'][s['fr']]
        s['fx'], s['fy'] = face_at(s['f0'], s['f1'])
        s['fw'] = face_w(s['f0'], s['f1'])
        s['snaps'] = [{'f': f, 'dz': E['snap_dz']} for f in snap_frames if s['f0'] <= f < s['f1']]
        s['push'] = next((p for f, p in overrides if s['f0'] <= f < s['f1']), E['push'])

    cover = None
    if E.get('cover'):
        C = E['cover']
        cf = int(C.get('frame', 0))
        cx, cy = face_at(cf, cf + 1)
        cover = {'frame': cf, 'kicker': C.get('kicker', ''), 'line1': C.get('line1', ''), 'line2': C.get('line2', ''),
                 'zoom': C.get('zoom', 1.3), 'face_y': C.get('face_y', 0.31), 'fx': cx, 'fy': cy}

    music = None
    if E.get('music') and E['music'].get('file'):
        M = E['music']
        body0 = chs[0]['f0'] if chs else 0
        body1 = outro_f or (tags_block['f0'] if tags_block else N)
        music = {'file': os.path.join(reel, M['file']), 'lufs': M.get('lufs', -25.0), 'duck_db': M.get('duck_db', 5.0),
                 'body': [body0 / FPS, max(body1, body0 + FPS * 5) / FPS]}

    tl = {'fps': FPS, 'W': 1080, 'H': 1920, 'frames': N, 'src': os.path.abspath(os.path.join(reel, E['source'])),
          'title': E.get('title', os.path.basename(os.path.abspath(reel))), 'mirror': bool(E['mirror']),
          'grade': E['grade'], 'style': E['style'], 'chapter_kicker': E['chapter_kicker'],
          'src_frames': src_frames, 'kept': kept, 'tail_hold': tail, 'shots': shots, 'captions': captions,
          'chapters': chapters, 'cards': cards, 'list': list_block, 'tags': tags_block, 'tracker': states,
          'end': end_prompt, 'outro': outro_f, 'blur': [{'f0': c['f0'], 'f1': c['f1']} for c in chapters + cards],
          'sfx': sorted(sfx, key=lambda e: e['f']) if E['sfx'] else [], 'cover': cover, 'music': music,
          'words': [{'f': f, 'e': e, 'w': w['w']} for f, e, w in zip(wf, we, words)]}
    build_dir = build_dir or os.path.join(reel, 'build')
    os.makedirs(build_dir, exist_ok=True)
    json.dump(tl, open(os.path.join(build_dir, 'timeline.json'), 'w'))

    cut_s = sum(b - a for a, b in removed) / FPS
    print(f'{len(removed)} cuts, {cut_s:.2f} s of pauses removed; output {N} frames = {N / FPS:.2f} s')
    print(f'{len(shots)} shots, avg {N / max(1, len(shots)) / FPS:.2f} s; under 0.5 s: '
          + (', '.join(f"{s['f0']}-{s['f1']}" for s in shots if s['f1'] - s['f0'] < 15) or 'none'))
    for c in chs:
        print(f"  chapter {c['n']}: frames {c['f0']}-{c['f1']} ({(c['f1'] - c['f0']) / FPS:.2f} s) {c['title']!r}")
    for c in cards:
        print(f"  card {c['id']}: frames {c['f0']}-{c['f1']} ({(c['f1'] - c['f0']) / FPS:.2f} s)")
    if list_block:
        print(f"  list: frames {list_block['f0']}-{list_block['f1']}")
    if tags_block:
        print(f"  tags: frames {tags_block['f0']}-{tags_block['f1']}")
    if end_prompt:
        print(f"  end prompt from frame {end_prompt['f0']} ({(N - end_prompt['f0']) / FPS:.1f} s on screen)")
    for s in states:
        print(f"  tracker {s['f0']}-{s['f1']}: {re.sub('<[^>]+>', '', s['label'])} {s['title']}")
    # what to look at next: long unbroken shots, and top text over a tight shot (it lands on the head)
    blurred = [(b['f0'], b['f1']) for b in chapters + cards]
    wstart = {}
    for i, f in enumerate(wf):
        wstart.setdefault(f, i)
    for s in shots:
        visible = (s['f1'] - s['f0']) - sum(max(0, min(s['f1'], b1) - max(s['f0'], b0)) for b0, b1 in blurred)
        if visible > 4.5 * FPS:
            ws = [i for i, f in enumerate(wf) if s['f0'] <= f < s['f1']]
            span = f"words {ws[0]}-{ws[-1]}" if ws else 'no words'
            print(f"  long shot: frames {s['f0']}-{s['f1']} ({visible / FPS:.1f} s on screen, {s['fr']}), {span}: "
                  f"add a framing request at a phrase boundary inside it")
    for name, w0 in ((('end prompt', end_prompt['f0']),) if end_prompt else ()) + \
            ((('tags', tags_block['f0']),) if tags_block else ()):
        w1 = N if name == 'end prompt' else tags_block['f1']
        tight = [s for s in shots if s['fr'] == 'T' and s['f0'] < w1 and s['f1'] > w0]
        if tight:
            print(f"  note: the {name} is up over TIGHT shot(s) at frames "
                  + ', '.join(f"{s['f0']}-{s['f1']}" for s in tight)
                  + ': top text will sit on the head. Request W or M there, or check `reel stills --guides`.')
    groups_long = [g for g in groups if g['kind'] in ('cap', 'big') and len(g['words']) > 7]
    if groups_long:
        print(f"  {len(groups_long)} caption group(s) over 7 words; split them: "
              + '; '.join(' '.join(w['t'] for w in g['words'][:5]) + '...' for g in groups_long[:4]))
    return tl
