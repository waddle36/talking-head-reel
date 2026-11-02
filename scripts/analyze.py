"""`reel analyze <reel>`: everything the edit decisions need, written to <reel>/analysis/.

  source.json   duration, fps, size, colour transfer (HDR check), loudness, colour cast
  words.json    one entry per spoken word: text, start, end (whisper.cpp, word-level)
  transcript.txt the words as readable text
  speech.json   speech regions and pauses from the audio's energy (the timing authority, not whisper)
  face.json     face centre over time (OpenCV Haar cascade at 4 Hz), for framing the punch-ins
  sheet_NN.jpg  1 frame per second, 18 per sheet, to look at the clip
"""
import glob
import json
import os
import re
import shutil
import subprocess
import wave

import numpy as np

MODEL_CANDIDATES = [os.environ.get('WHISPER_MODEL', ''),
                    os.path.expanduser('~/.cache/talking-head-reel/ggml-small.en.bin'),
                    os.path.expanduser('~/models/whisper/ggml-small.en.bin')]


def sh(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=kw.pop('text', True), **kw)


def probe(src):
    j = json.loads(sh(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', src]).stdout)
    v = next(s for s in j['streams'] if s['codec_type'] == 'video')
    a = next((s for s in j['streams'] if s['codec_type'] == 'audio'), None)
    num, den = (v.get('avg_frame_rate') or '30/1').split('/')
    rot = 0
    for sd in v.get('side_data_list', []):
        if 'rotation' in sd:
            rot = int(sd['rotation'])
    rot = int(v.get('tags', {}).get('rotate', rot))
    w, h = int(v['width']), int(v['height'])
    if abs(rot) in (90, 270):
        w, h = h, w
    err = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', src, '-map', '0:a:0?', '-af', 'ebur128=peak=true',
                          '-f', 'null', '-'], capture_output=True, text=True).stderr
    lufs = re.findall(r'I:\s+(-?[\d.]+) LUFS', err)
    stats = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(float(j['format']['duration']) / 2), '-i', src,
                            '-frames:v', '1', '-vf', 'signalstats,metadata=print:file=-', '-f', 'null', '-'],
                           capture_output=True, text=True).stdout
    sv = {k: float(x) for k, x in re.findall(r'signalstats\.(YAVG|UAVG|VAVG)=([\d.]+)', stats)}
    return {'duration': float(j['format']['duration']), 'fps': int(num) / max(1, int(den)), 'width': w, 'height': h,
            'rotation': rot, 'codec': v.get('codec_name'), 'transfer': v.get('color_transfer', ''),
            'pix_fmt': v.get('pix_fmt', ''), 'audio': bool(a), 'lufs': float(lufs[-1]) if lufs else None, 'stats': sv}


def find_model():
    for p in MODEL_CANDIDATES:
        if p and os.path.exists(p):
            return p
    raise SystemExit('No whisper model found. Run scripts/setup.sh --install (downloads ggml-small.en.bin, ~466 MB), '
                     'or set WHISPER_MODEL to a ggml model path.')


def transcribe(wav16, out_base, prompt=None):
    exe = shutil.which('whisper-cli') or shutil.which('whisper-cpp')
    if not exe:
        raise SystemExit('whisper-cli not found. Run scripts/setup.sh --install (brew install whisper-cpp).')
    cmd = [exe, '-m', find_model(), '-f', wav16, '-t', str(max(2, (os.cpu_count() or 4))), '-ojf', '-ml', '1', '-sow',
           '-of', out_base, '-np']
    if prompt:
        cmd += ['--prompt', prompt]
    sh(cmd)
    d = json.load(open(out_base + '.json'))
    words = []
    for s in d['transcription']:
        t = s['text'].strip()
        if not t:
            continue
        toks = [k for k in s.get('tokens', []) if not k.get('text', '').startswith('[_')]
        pmin = min((k.get('p', 1.0) for k in toks), default=1.0)
        words.append({'w': t, 'a': s['offsets']['from'] / 1000, 'b': s['offsets']['to'] / 1000, 'p': round(pmin, 3)})
    return words


def speech_regions(wav16):
    """10 ms RMS envelope; speech = above floor + 35% of the floor-to-p95 range; gaps < 120 ms closed"""
    w = wave.open(wav16)
    sr = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    hop = int(sr * 0.01)
    n = len(x) // hop
    db = 20 * np.log10(np.sqrt(np.mean(x[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12))
    db = np.convolve(db, np.ones(3) / 3, mode='same')
    floor, p95 = np.percentile(db, 5), np.percentile(db, 95)
    sp = db > floor + 0.35 * (p95 - floor)
    runs, s = [], None
    for i, v in enumerate(sp):
        if v and s is None:
            s = i
        if not v and s is not None:
            runs.append([s, i])
            s = None
    if s is not None:
        runs.append([s, len(sp)])
    merged = []
    for a, b in runs:
        if merged and a - merged[-1][1] < 12:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    regions = [[a / 100, b / 100] for a, b in merged if b - a >= 6]
    pauses = [[regions[i][1], regions[i + 1][0]] for i in range(len(regions) - 1)]
    return {'regions': regions, 'pauses': pauses, 'floor_db': float(floor), 'p95_db': float(p95)}


def face_track(src, fps=4, W=360, H=640):
    import cv2
    if not hasattr(cv2, 'CascadeClassifier'):
        raise SystemExit('OpenCV 5 has no Haar face detector: run with opencv-python-headless<5 (the ./reel wrapper does).')
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-vf', f'fps={fps},scale={W}:{H}', '-f', 'rawvideo',
                          '-pix_fmt', 'gray', '-'], capture_output=True, check=True).stdout
    n = len(raw) // (W * H)
    frames = np.frombuffer(raw[:n * W * H], np.uint8).reshape(n, H, W)
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    pts = []
    for g in frames:
        f = casc.detectMultiScale(g, scaleFactor=1.08, minNeighbors=5, minSize=(40, 40))
        if len(f):
            x, y, w, h = max(f, key=lambda r: r[2] * r[3])
            pts.append(((x + w / 2) / W, (y + h / 2) / H, w / W))
        else:
            pts.append(None)
    found = sum(p is not None for p in pts)
    t = np.arange(n) / fps
    if found < max(3, n // 10):
        return {'fps': fps, 't': [], 'cx': [], 'cy': [], 'fw': [], 'found': found, 'samples': n}

    def fill(k):
        v = np.array([np.nan if p is None else p[k] for p in pts], float)
        ok = ~np.isnan(v)
        v = np.interp(t, t[ok], v[ok])
        pad = np.pad(v, 3, mode='edge')     # 1.75 s median: ignores the odd false detection
        return [round(float(np.median(pad[i:i + 7])), 4) for i in range(len(v))]
    return {'fps': fps, 't': t.round(3).tolist(), 'cx': fill(0), 'cy': fill(1), 'fw': fill(2), 'found': found,
            'samples': n}


def sheets(src, out_dir):
    for p in glob.glob(os.path.join(out_dir, 'sheet_*.jpg')):
        os.remove(p)
    sh(['ffmpeg', '-v', 'error', '-y', '-i', src, '-vf', 'fps=1,scale=240:-2,tile=6x3:padding=4:color=black',
        '-q:v', '4', os.path.join(out_dir, 'sheet_%02d.jpg')])
    return sorted(glob.glob(os.path.join(out_dir, 'sheet_*.jpg')))


def mirror_check(src, out, duration):
    """the upper part of one full-resolution frame: background text is readable here (contact sheets are too small)"""
    sh(['ffmpeg', '-v', 'error', '-y', '-ss', f'{duration / 2:.2f}', '-i', src, '-frames:v', '1', '-vf',
        'crop=iw:ih*0.45:0:0', '-q:v', '2', out])
    return out


def analyze(reel, source, prompt=None):
    A = os.path.join(reel, 'analysis')
    os.makedirs(A, exist_ok=True)
    src = os.path.abspath(source)
    meta = probe(src)
    json.dump(meta, open(os.path.join(A, 'source.json'), 'w'), indent=1)
    wav16 = os.path.join(A, 'audio16k.wav')
    sh(['ffmpeg', '-v', 'error', '-y', '-i', src, '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', wav16])
    print(f"source: {meta['width']}x{meta['height']} {meta['fps']:.2f} fps {meta['duration']:.1f} s, "
          f"audio {meta['lufs']} LUFS, transfer {meta['transfer'] or 'unknown'}")
    if meta['transfer'] in ('arib-std-b67', 'smpte2084'):
        print('  WARNING: HDR footage (HLG/PQ). The grade assumes SDR and will look washed out. Make an SDR copy first, '
              'e.g. `avconvert --source IN.mov --preset PresetHighestQuality --output IN-sdr.mov`, and edit that.')
    st = meta['stats']
    if st and st.get('VAVG', 128) - 128 > 4 and 128 - st.get('UAVG', 128) > 4:
        print(f"  warm colour cast (U {st['UAVG']:.0f}, V {st['VAVG']:.0f}): the 'warm-room' grade suits it")
    words = transcribe(wav16, os.path.join(A, 'whisper'), prompt)
    json.dump(words, open(os.path.join(A, 'words.json'), 'w'), indent=0)
    text = ' '.join(w['w'] for w in words)
    open(os.path.join(A, 'transcript.txt'), 'w').write(re.sub(r'([.?!]) ', r'\1\n', text) + '\n')
    sp = speech_regions(wav16)
    json.dump(sp, open(os.path.join(A, 'speech.json'), 'w'))
    long_p = [p for p in sp['pauses'] if p[1] - p[0] >= 0.22]
    print(f"{len(words)} words; {len(long_p)} pauses of 0.22 s or more, {sum(b - a for a, b in long_p):.1f} s in total")
    fc = face_track(src)
    json.dump(fc, open(os.path.join(A, 'face.json'), 'w'))
    if fc['t']:
        print(f"face found in {fc['found']}/{fc['samples']} samples; median centre "
              f"({np.median(fc['cx']):.2f}, {np.median(fc['cy']):.2f}) of the frame")
    else:
        print(f"face found in only {fc['found']}/{fc['samples']} samples: framing will centre on the frame instead")
    sh_list = sheets(src, A)
    mc = mirror_check(src, os.path.join(A, 'frame_top.jpg'), meta['duration'])
    print(f'mirror check (full resolution, read it: does any text run backwards?): {mc}')
    print('contact sheets (look at them: mirrored text? framing? lighting?):')
    for p in sh_list:
        print('  ' + p)
    print('\nwords (index:word), for captions.txt and the word numbers in edit.json:')
    line = []
    for i, w in enumerate(words):
        line.append(f'{i}:{w["w"]}')
        if len(line) == 12:
            print('  ' + ' '.join(line))
            line = []
    if line:
        print('  ' + ' '.join(line))
    low = [(i, w) for i, w in enumerate(words) if w.get('p', 1) < 0.6]
    if low:
        print('\npossible mishears (whisper was unsure; check each against the context, fix them in captions.txt):')
        for i, w in low:
            ctx = ' '.join(x['w'] for x in words[max(0, i - 3):i]) + f' [{w["w"]}] ' + ' '.join(x['w'] for x in words[i + 1:i + 4])
            print(f'  {i}: p={w["p"]:.2f}  ...{ctx}...')
    print(f'\ntranscript: {os.path.join(A, "transcript.txt")}')
