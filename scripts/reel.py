"""talking-head-reel CLI. Run through the ./reel wrapper at the skill root (it supplies numpy, playwright, opencv).

  ./reel analyze  <reel-dir> --source <clip> [--prompt "Names, Brands"]   transcript, pauses, face track, sheets,
                                                                           and a starter edit.json
  ./reel build    <reel-dir>                      edit.json + captions.txt -> build/timeline.json (prints the tables)
  ./reel stills   <reel-dir> 0,150,700 [--guides] full-res PNGs + a sheet (guides = Instagram's UI zones)
  ./reel render   <reel-dir>                      audio + the full picture (~9 min) -> exports/<reel>.mp4
  ./reel check    <reel-dir>                      caption sync, loudness, format
  ./reel sheet    <reel-dir> [--every 57]         frames from the master, tiled
  ./reel cover    <reel-dir>                      exports/<reel>-cover.jpg + a grid-size check
  ./reel preview  <reel-dir>                      720p copy under 30 MB for phones
  ./reel remix    <reel-dir>                      new audio (music change) under the same picture, no re-render
  ./reel music-plan <reel-dir> [--flavor A|B|C]   a music plan that follows the edit's sections
  ./reel music-gen  <reel-dir> [--flavor A] [--seed 11] [--yes]   ElevenLabs Music with the user's own key
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def opt(a, name, default=None):
    return a[a.index(name) + 1] if name in a else default


def starter_edit(reel, source, meta):
    path = os.path.join(reel, 'edit.json')
    if os.path.exists(path):
        return
    st = meta.get('stats') or {}
    warm = st.get('VAVG', 128) - 128 > 4 and 128 - st.get('UAVG', 128) > 4
    src = os.path.abspath(source)   # relative only when the clip lives inside the reel folder
    src = os.path.relpath(src, reel) if src.startswith(reel + os.sep) else src
    e = {'source': src, 'title': '', 'mirror': False,
         'grade': 'warm-room' if warm else 'neutral', 'shots': [[0, 'T']], 'snaps': [], 'chapters': {},
         'chapter_kicker': '', 'tracker': {}, 'cards': {}, 'end': None,
         'cover': {'frame': 15, 'kicker': '', 'line1': '', 'line2': ''}, 'music': None}
    json.dump(e, open(path, 'w'), indent=1)
    print(f'starter edit.json written: {path}')


def main():
    a = sys.argv[1:]
    if len(a) < 2:
        raise SystemExit(__doc__)
    cmd, reel = a[0], os.path.abspath(a[1])
    if cmd == 'analyze':
        import analyze
        src = opt(a, '--source')
        if not src:
            ej = os.path.join(reel, 'edit.json')
            if not os.path.exists(ej):
                raise SystemExit('analyze needs --source <clip> the first time')
            src = os.path.join(reel, json.load(open(ej))['source'])
        os.makedirs(reel, exist_ok=True)
        analyze.analyze(reel, src, opt(a, '--prompt'))
        starter_edit(reel, src, json.load(open(os.path.join(reel, 'analysis', 'source.json'))))
        return
    if cmd == 'build':
        import edl
        edl.build(reel)
        return
    import render
    R = render.Reel(reel)
    if cmd == 'stills':
        render.stills(R, [int(x) for x in a[2].split(',')], guides='--guides' in a)
    elif cmd == 'render':
        render.master(R)
    elif cmd == 'check':
        render.check(R)
    elif cmd == 'sheet':
        render.sheet(R, int(opt(a, '--every', 57)))
    elif cmd == 'cover':
        render.cover(R)
    elif cmd == 'preview':
        render.preview(R)
    elif cmd == 'remix':
        render.remix(R)
    elif cmd in ('music-plan', 'music-gen'):
        import music
        if cmd == 'music-plan':
            music.write_plan(R, opt(a, '--flavor', 'A'))
        else:
            music.generate(R, opt(a, '--flavor', 'A'), int(opt(a, '--seed', 11)), yes='--yes' in a)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
