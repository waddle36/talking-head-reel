"""Audio, stills, the master, the cover, the phone preview and the checks for one reel folder.

Frames: ffmpeg decodes the clip at 30 fps, un-mirrors it if edit.json says so, grades it and upscales it to
1440x2560 JPEGs; installed Chrome (driven by Playwright, sRGB forced) composites one frame of assets/web/reel.html
per output frame; the screenshots stream straight into x264. Nothing but the movie and the audio touches the disk.
"""
import base64
import http.server
import json
import math
import os
import re
import subprocess
import threading
import time
import wave

import numpy as np

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(SKILL, 'assets', 'web')
SR = 48000
SPF = SR // 30                      # audio samples per video frame

GRADES = {   # (yuv part, rgb part); pick one in edit.json "grade"
    'neutral': ('eq=contrast=1.05:saturation=1.04:gamma=0.99', 'curves=master=0/0.01 0.3/0.29 0.7/0.71 1/0.965'),
    'warm-room': ('eq=contrast=1.07:saturation=1.05:gamma=0.98',
                  'colorbalance=rs=-0.025:bs=0.035:rm=-0.03:bm=0.03:rh=-0.025:bh=0.018,'
                  'curves=master=0/0.012 0.3/0.285 0.7/0.715 1/0.955'),
    'none': ('', ''),
}
# spikes (plosives, mic bumps) are limited before the gain; the de-esser goes last because it goes unstable on
# samples above full scale
VOICE_CHAIN = ('aformat=sample_fmts=flt:channel_layouts=mono,highpass=f=70:poles=2,'
               'equalizer=f=250:t=q:w=1.2:g=-1.5,equalizer=f=3800:t=q:w=1.0:g=2,'
               'alimiter=limit=0.16:attack=0.8:release=30:level=false:latency=true,volume=12dB,'
               'acompressor=threshold=0.1:ratio=4:attack=2:release=80:knee=2.8:makeup=1,deesser=i=0.3')
MUSIC_CHAIN = ('aformat=sample_fmts=flt:channel_layouts=stereo,highpass=f=40,equalizer=f=2500:t=q:w=1.2:g=-3,'
               'acompressor=threshold=0.05:ratio=2.5:attack=200:release=1200:knee=6:makeup=1')
TARGET_LUFS, CEIL_DB = -14.0, -1.5


class Reel:
    def __init__(self, path):
        self.dir = os.path.abspath(path)
        self.build = os.path.join(self.dir, 'build')
        self.exports = os.path.join(self.dir, 'exports')
        self.slug = os.path.basename(self.dir)
        os.makedirs(self.build, exist_ok=True)
        os.makedirs(self.exports, exist_ok=True)

    @property
    def tl(self):
        return json.load(open(os.path.join(self.build, 'timeline.json')))

    def b(self, *p):
        return os.path.join(self.build, *p)


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def loudness(path):
    err = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    return float(re.findall(r'I:\s+(-?[\d.]+) LUFS', err)[-1]), float(re.findall(r'Peak:\s+(-?[\d.]+) dBFS', err)[-1])


def loudness_of(x):
    """integrated LUFS of a float array (n, 2)"""
    err = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', '-',
                          '-af', 'ebur128', '-f', 'null', '-'], input=x.astype('<f4').tobytes(), capture_output=True).stderr
    return float(re.findall(r'I:\s+(-?[\d.]+) LUFS', err.decode())[-1])


def read_f32(path, ch=1):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', str(ch), '-ar', str(SR), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, '<f4').astype(np.float64)
    return x.reshape(-1, ch) if ch > 1 else x


def write_wav16(path, x):
    x = x[:, None] if x.ndim == 1 else x
    pcm = (np.clip(x, -1, 1) * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(pcm.shape[1])
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def limit_to_wav(mix, out):
    """float mix (n, 2) -> 4x-oversampled true-peak limiter at CEIL_DB -> 16-bit wav (peaks reach it unclipped)"""
    lim = 10 ** (CEIL_DB / 20)
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', '-', '-af',
         f'aresample=192000:filter_size=64:cutoff=0.97,alimiter=limit={lim:.6f}:attack=1.5:release=60:'
         f'level=false:latency=true,aresample=48000:filter_size=64:cutoff=0.97', '-c:a', 'pcm_s16le', out],
        input=mix.astype('<f4').tobytes())


# ---------------------------------------------------------------- synthesized SFX (nothing downloaded)
def _svf_band(x, fc, q):
    low = band = 0.0
    out = np.empty_like(x)
    for i in range(len(x)):
        f = 2 * math.sin(math.pi * min(fc[i], SR / 6) / SR)
        high = x[i] - low - q * band
        band += f * high
        low += f * band
        out[i] = band
    return out


def _peak(x, db):
    return x / (np.max(np.abs(x)) + 1e-12) * 10 ** (db / 20)


def sfx_bank():
    n = int(0.5 * SR)
    t = np.arange(n) / n
    noise = np.random.default_rng(3).standard_normal(n)
    fc = 300 * (2800 / 300) ** np.clip(t / 0.7, 0, 1) * (1 - 0.35 * np.clip((t - 0.7) / 0.3, 0, 1))
    y = _svf_band(noise, fc, 0.8) * np.where(t < 0.62, np.sin(np.pi / 2 * t / 0.62) ** 2, np.exp(-(t - 0.62) * 9))
    pan = 0.3 + 0.4 * t
    whoosh = _peak(np.stack([y * np.cos(pan * np.pi / 2), y * np.sin(pan * np.pi / 2)], 1), -24)
    tt = np.arange(int(0.45 * SR)) / SR
    th = np.sin(2 * np.pi * np.cumsum(45 + 50 * np.exp(-tt / 0.06)) / SR) * np.exp(-tt / 0.11) * np.clip(tt / 0.002, 0, 1)
    thump = np.stack([_peak(th, -15)] * 2, 1)
    tt = np.arange(int(0.07 * SR)) / SR
    tk = np.sin(2 * np.pi * np.cumsum(900 + 900 * np.exp(-tt / 0.012)) / SR) * np.exp(-tt / 0.016) * np.clip(tt / 0.001, 0, 1)
    tick = np.stack([_peak(tk, -30)] * 2, 1)
    return {'whoosh': whoosh, 'thump': thump, 'tick': tick}


# ---------------------------------------------------------------- audio
def music_bed(path, voice, need, lufs, duck_db, body):
    """carved out of the voice band, slowly compressed, body section at `lufs`, ducked by duck_db under speech"""
    m = read_f32(path, 2)
    proc = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', '-', '-af', MUSIC_CHAIN,
                           '-f', 'f32le', '-'], input=m.astype('<f4').tobytes(), capture_output=True, check=True).stdout
    m = np.frombuffer(proc, '<f4').astype(np.float64).reshape(-1, 2)[:need]
    m = np.pad(m, ((0, need - len(m)), (0, 0)))
    a, b = int(body[0] * SR), min(need, int(body[1] * SR))
    m *= 10 ** ((lufs - loudness_of(m[a:b])) / 20)
    hop = SR // 50
    n = need // hop
    db = 20 * np.log10(np.sqrt(np.mean(voice[:n * hop].reshape(n, hop) ** 2, 1)) + 1e-9)
    floor, p95 = np.percentile(db, 5), np.percentile(db, 95)
    target = np.where(db > floor + 0.35 * (p95 - floor), -duck_db, 0.0)
    g, env = 0.0, np.empty(n)
    ka, kr = 1 - math.exp(-1 / (0.08 * 50)), 1 - math.exp(-1 / (0.4 * 50))   # 80 ms attack, 400 ms release
    for i, tg in enumerate(target):
        g += (tg - g) * (ka if tg < g else kr)
        env[i] = g
    m *= (10 ** (np.interp(np.arange(need), np.arange(n) * hop + hop / 2, env) / 20))[:, None]
    fi, fo = int(0.15 * SR), int(1.2 * SR)
    m[:fi] *= np.linspace(0, 1, fi)[:, None]
    m[-fo:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, fo)))[:, None]
    return m


def build_audio(R):
    T = R.tl
    src = read_f32(T['src'], 1)
    fade = int(0.008 * SR)
    ramp = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, fade))
    parts = []
    for k, (a, b) in enumerate(T['kept']):   # the picture's cut list, 8 ms raised-cosine fades at every join
        seg = src[a * SPF:min(b * SPF, len(src))].copy()
        if len(seg) > 2 * fade:
            if k > 0:
                seg[:fade] *= ramp
            if k < len(T['kept']) - 1:
                seg[-fade:] *= ramp[::-1]
        parts.append(seg)
    parts.append(np.zeros(T['tail_hold'] * SPF))
    need = T['frames'] * SPF
    voice = np.concatenate(parts)
    voice = np.pad(voice, (0, max(0, need - len(voice))))[:need]
    cut_wav, proc_wav = R.b('voice_cut.wav'), R.b('voice_proc.wav')
    write_wav16(cut_wav, voice * 0.98)
    run(['ffmpeg', '-v', 'error', '-y', '-i', cut_wav, '-af', VOICE_CHAIN, '-c:a', 'pcm_f32le', proc_wav])
    vi, _ = loudness(proc_wav)
    v = read_f32(proc_wav, 1)[:need]
    # measured as mono; the same signal on both channels reads 3.01 LU louder, so aim the mono 3.01 LU lower
    v = np.pad(v, (0, need - len(v))) * 10 ** ((TARGET_LUFS - 3.01 - vi) / 20)
    write_wav16(R.b('voice_only.wav'), v)
    mix = np.stack([v, v], 1)
    bank = sfx_bank() if T['sfx'] else {}
    for e in T['sfx']:
        s, o = bank[e['kind']], e['f'] * SPF
        n = min(len(s), need - o)
        if n > 0:
            mix[o:o + n] += s[:n]
    limit_to_wav(mix, R.b('audio_voice.wav'))           # what the picture render carries
    M = T.get('music')
    if M and os.path.exists(M['file']):
        bed = music_bed(M['file'], v, need, M['lufs'], M['duck_db'], M['body'])
        print(f"music bed {loudness_of(bed):.1f} LUFS under the voice at {TARGET_LUFS}")
        mix = mix + bed
        mix *= 10 ** ((TARGET_LUFS - loudness_of(mix)) / 20)
    elif M:
        print(f"music file missing: {M['file']} (mixing without music)")
    limit_to_wav(mix, R.b('audio_final.wav'))
    fi, ftp = loudness(R.b('audio_final.wav'))
    print(f'audio: {fi:.1f} LUFS, true peak {ftp:.1f} dBFS, {len(T["sfx"])} sfx, {need / SR:.2f} s')


# ---------------------------------------------------------------- frames
class Frames:
    """sequential decoder: the clip at 30 fps, un-mirrored and graded, as JPEG bytes"""

    def __init__(self, T, w, h, select=None):
        gy, gr = GRADES.get(T.get('grade', 'neutral'), GRADES['neutral'])
        vf = ['fps=30', f"select='{select}'" if select else None, 'hflip' if T.get('mirror') else None, gy or None,
              f'scale={w}:{h}:flags=lanczos', 'unsharp=5:5:0.5:5:5:0' if w >= 1080 else None,
              'scale=in_color_matrix=bt709:in_range=pc:out_color_matrix=bt709:out_range=pc', 'format=rgb24', gr or None,
              'scale=out_color_matrix=bt601:out_range=pc', 'format=yuvj420p']
        cmd = ['ffmpeg', '-v', 'error', '-i', T['src'], '-vf', ','.join(x for x in vf if x),
               *(['-fps_mode', 'passthrough'] if select else []), '-c:v', 'mjpeg', '-q:v', '2', '-f', 'image2pipe', '-']
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=1 << 22)
        self.buf, self.k, self.cur = b'', -1, None

    def next(self):
        while True:
            s = self.buf.find(b'\xff\xd8')
            e = self.buf.find(b'\xff\xd9', s + 2) if s >= 0 else -1
            if s >= 0 and e >= 0:
                img, self.buf = self.buf[s:e + 2], self.buf[e + 2:]
                return img
            chunk = self.p.stdout.read(1 << 20)
            if not chunk:
                return None
            self.buf += chunk

    def get(self, k):
        while self.k < k:
            img = self.next()
            if img is None:
                break
            self.cur, self.k = img, self.k + 1
        return self.cur

    def close(self):
        self.p.kill()


class Page:
    def __init__(self, R, html='reel.html', guides=False):
        from playwright.sync_api import sync_playwright
        self.frame_bytes = {}
        ref = self

        class H(http.server.SimpleHTTPRequestHandler):
            def __init__(s, *a, **k):
                super().__init__(*a, directory=WEB, **k)

            def log_message(s, *a):
                pass

            def do_GET(s):
                path = s.path.split('?')[0]
                if path.startswith('/frame/'):
                    body, ctype = ref.frame_bytes.get(path), 'image/jpeg'
                elif path == '/timeline.json':
                    body, ctype = open(R.b('timeline.json'), 'rb').read(), 'application/json'
                else:
                    return super().do_GET()
                if body is None:
                    s.send_error(404)
                    return
                s.send_response(200)
                s.send_header('Content-Type', ctype)
                s.send_header('Content-Length', str(len(body)))
                s.send_header('Cache-Control', 'no-store')
                s.end_headers()
                s.wfile.write(body)

        self.httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.pw = sync_playwright().start()
        try:
            self.browser = self.pw.chromium.launch(channel='chrome', args=[
                '--force-color-profile=srgb', '--font-render-hinting=none', '--disable-lcd-text',
                '--enable-gpu-rasterization', '--ignore-gpu-blocklist'])
        except Exception as ex:
            self.pw.stop()
            self.httpd.shutdown()
            raise SystemExit(f'Could not start Google Chrome through Playwright ({ex}). Is Chrome installed in /Applications?')
        self.page = self.browser.new_page(viewport={'width': 1080, 'height': 1920}, device_scale_factor=1)
        self.page.on('console', lambda m: m.type in ('error', 'warning') and print('[page]', m.type, m.text))
        self.page.on('pageerror', lambda e: print('[page error]', e))
        port = self.httpd.server_address[1]
        self.page.goto(f'http://127.0.0.1:{port}/{html}' + ('?guides=1' if guides else ''))
        self.info = self.page.evaluate('window.READY')
        if not self.info['fonts']['ok']:
            self.close()
            raise SystemExit(f"FONT CHECK FAILED: {self.info['fonts']}")
        self.cdp = self.page.context.new_cdp_session(self.page)

    def frame(self, n, jpeg, fmt='jpeg', quality=93):
        key = f'/frame/{n}.jpg'
        self.frame_bytes.clear()
        self.frame_bytes[key] = jpeg
        r = self.page.evaluate('([n, u]) => window.renderFrame(n, u)', [n, key + f'?n={n}'])
        p = {'format': fmt, 'captureBeyondViewport': False, 'optimizeForSpeed': True,
             'clip': {'x': 0, 'y': 0, 'width': 1080, 'height': 1920, 'scale': 1}}
        if fmt == 'jpeg':
            p['quality'] = quality
        return base64.b64decode(self.cdp.send('Page.captureScreenshot', p)['data']), r

    def close(self):
        try:
            self.browser.close()
            self.pw.stop()
        finally:
            self.httpd.shutdown()


def encode_picture(R, out, f0=0, f1=None, crf=18, preset='slow', base=(1440, 2560)):
    T = R.tl
    f1 = T['frames'] if f1 is None else min(f1, T['frames'])
    audio = R.b('audio_voice.wav')
    vf = ('scale=in_color_matrix=bt601:in_range=pc:out_color_matrix=bt709:out_range=tv,format=yuv420p,'
          'setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv,setsar=1')
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'image2pipe', '-c:v', 'mjpeg', '-framerate', '30', '-i', '-',
           '-ss', f'{f0 / 30:.6f}', '-t', f'{(f1 - f0) / 30:.6f}', '-i', audio, '-map', '0:v', '-map', '1:a',
           '-vf', vf, '-c:v', 'libx264', '-preset', preset, '-crf', str(crf), '-profile:v', 'high', '-tune', 'film',
           '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
           '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', '-shortest', out]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    dec = Frames(T, *base)
    pg = Page(R)
    t0 = time.time()
    try:
        for n in range(f0, f1):
            data, r = pg.frame(n, dec.get(T['src_frames'][n]))
            enc.stdin.write(data)
            if (n - f0) % 300 == 0:
                el = time.time() - t0
                left = (f1 - n) / max((n - f0 + 1) / max(el, 1e-6), 0.1)
                print(f'  frame {n}/{f1}  {(n - f0 + 1) / max(el, 1e-6):.1f} fps, about {left / 60:.0f} min left', flush=True)
    finally:
        pg.close()
        dec.close()
        enc.stdin.close()
    if enc.wait():
        raise SystemExit('the x264 encode failed')
    print(f'{out}: {f1 - f0} frames in {time.time() - t0:.0f} s')


def mux(R, video, audio, out, preview=False):
    """audio under an already-rendered picture (video stream copied); preview=True makes a 720p copy under 30 MB"""
    v = (['-vf', 'scale=720:1280:flags=lanczos,setsar=1', '-c:v', 'libx264', '-preset', 'slow', '-b:v', '1800k',
          '-maxrate', '2400k', '-bufsize', '4000k', '-pix_fmt', 'yuv420p', '-colorspace', 'bt709',
          '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv'] if preview else ['-c:v', 'copy'])
    run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-i', audio, '-map', '0:v', '-map', '1:a', *v,
         '-c:a', 'aac', '-b:a', '128k' if preview else '192k', '-ar', '48000', '-movflags', '+faststart', '-shortest',
         '-metadata', f"title={R.tl.get('title', R.slug)}", out])
    print(f'{out}: {os.path.getsize(out) / 1e6:.1f} MB')


def master(R):
    build_audio(R)
    pic = R.b('picture.mp4')
    encode_picture(R, pic)
    out = os.path.join(R.exports, f'{R.slug}.mp4')
    mux(R, pic, R.b('audio_final.wav'), out)
    return out


def remix(R):
    """after a music change in edit.json (and `reel build`): new audio under the same picture, no re-render"""
    build_audio(R)
    out = os.path.join(R.exports, f'{R.slug}.mp4')
    mux(R, R.b('picture.mp4'), R.b('audio_final.wav'), out)
    return out


def preview(R):
    out = os.path.join(R.exports, f'{R.slug}-preview.mp4')
    mux(R, os.path.join(R.exports, f'{R.slug}.mp4'), R.b('audio_final.wav'), out, preview=True)
    return out


def stills(R, frames, guides=False):
    T = R.tl
    d = R.b('stills')
    os.makedirs(d, exist_ok=True)
    for p in os.listdir(d):
        os.remove(os.path.join(d, p))
    need = sorted(set(f for f in frames if 0 <= f < T['frames']))
    ks = sorted({T['src_frames'][n] for n in need})
    dec = Frames(T, 1440, 2560, select='+'.join(f'eq(n\\,{k})' for k in ks))
    imgs = {k: dec.next() for k in ks}
    dec.close()
    pg = Page(R, guides=guides)
    try:
        for n in need:
            data, r = pg.frame(n, imgs[T['src_frames'][n]], fmt='png')
            open(os.path.join(d, f'f{n:05d}.png'), 'wb').write(data)
    finally:
        pg.close()
    sheet = R.b('stills_sheet.jpg')   # half-size tiles: big enough to see text touching hair or a hand
    cols = min(4, len(need))
    run(['ffmpeg', '-v', 'error', '-y', '-pattern_type', 'glob', '-i', os.path.join(d, 'f*.png'), '-vf',
         f'scale=540:960:flags=lanczos,tile={cols}x{math.ceil(len(need) / cols)}:padding=6:color=white',
         '-frames:v', '1', '-q:v', '3', sheet])
    print(f'{len(need)} stills in {d}; sheet: {sheet}')
    return sheet


def sheet(R, every=57):
    src = os.path.join(R.exports, f'{R.slug}.mp4')
    out = R.b('master_sheet_%02d.jpg')
    run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-vf', f"select='not(mod(n\\,{every}))',scale=220:391,"
         'tile=9x3:padding=4:color=white', '-fps_mode', 'passthrough', '-q:v', '3', out])
    print('sheets: ' + ', '.join(sorted(p for p in os.listdir(R.build) if p.startswith('master_sheet_'))))


def check(R):
    """caption sync against his voice (0 words should appear in a pause), loudness, format"""
    T = R.tl
    x = read_f32(R.b('voice_only.wav'), 1)
    n = len(x) // SPF
    db = 20 * np.log10(np.sqrt(np.mean(x[:n * SPF].reshape(n, SPF) ** 2, 1)) + 1e-12)
    floor, p95 = np.percentile(db, 5), np.percentile(db, 95)
    speech = db > floor + 0.35 * (p95 - floor)
    shown = [(w['f'], w['t']) for g in T['captions'] for i, w in enumerate(g['words']) if g['kind'] != 'hook' or i == 0]
    bad = [(f, t) for f, t in shown if not speech[max(0, f - 1):f + 4].any()]
    ok = lambda c: 'PASS' if c else 'FAIL'
    print(f'{ok(not bad)}  caption sync: {len(shown) - len(bad)}/{len(shown)} caption onsets land on speech '
          '(a [hook] group counts once)' + (f"; in a pause: {', '.join(f'{t}@{f}' for f, t in bad[:20])}" if bad else ''))
    movie = os.path.join(R.exports, f'{R.slug}.mp4')
    i, tp = loudness(movie)
    print(f'{ok(abs(i - TARGET_LUFS) <= 1.0)}  loudness {i:.1f} LUFS (target {TARGET_LUFS}, within 1 LU)')
    print(f'{ok(tp <= -1.0)}  true peak {tp:.1f} dBTP (limited to {CEIL_DB}; the AAC encode reads about 0.1 dB higher; '
          '-1.0 or lower passes)')
    print(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_name,width,height,r_frame_rate,'
                          'pix_fmt,duration,sample_rate,channels', '-of', 'compact', movie],
                         capture_output=True, text=True).stdout.strip())
    print(f'size {os.path.getsize(movie) / 1e6:.1f} MB')


def cover(R):
    """assets/web/cover.html over the cover frame -> exports/<slug>-cover.jpg, plus a check at grid-tile size"""
    T = R.tl
    if not T.get('cover'):
        raise SystemExit('edit.json has no "cover" section')
    k = T['src_frames'][T['cover']['frame']]
    dec = Frames(T, 1440, 2560, select=f'eq(n\\,{k})')
    img = dec.next()
    dec.close()
    pg = Page(R, html='cover.html')
    try:
        png, _ = pg.frame(T['cover']['frame'], img, fmt='png')
    finally:
        pg.close()
    src = R.b('cover.png')
    open(src, 'wb').write(png)
    out = os.path.join(R.exports, f'{R.slug}-cover.jpg')
    run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-q:v', '2', out])
    chk = R.b('cover_grid_check.jpg')   # the profile grid's 3:4 centre crop at an iPhone tile's real size
    run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-filter_complex',
         '[0]split[a][b];[a]scale=540:960:flags=lanczos[full];[b]crop=1080:1440:0:240,scale=393:524:flags=lanczos,'
         'pad=393:960:0:218:color=white[tile];[full][tile]hstack', '-q:v', '3', chk])
    print(f'cover: {out}\ngrid check (right side = real tile size): {chk}')
