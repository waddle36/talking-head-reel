'use strict';
// One frame of the reel as a pure function of the frame number and timeline.json (no clock, no randomness).
// render.py streams the graded source frame in as an image URL, calls renderFrame(n, url), then screenshots.

const E = {
  outCubic: x => 1 - Math.pow(1 - x, 3),
  inCubic: x => x * x * x,
  inOutCubic: x => (x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
  outBack: (x, s = 1.7) => 1 + (s + 1) * Math.pow(x - 1, 3) + s * Math.pow(x - 1, 2),
};
const cl = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const pr = (n, f0, d) => cl((n - f0) / d);
const $ = id => document.getElementById(id);
const Q = new URLSearchParams(location.search);

let T = null;
const el = {};

function fontAvailable(fam) {
  const c = document.createElement('canvas').getContext('2d');
  c.font = '700 40px monospace';
  const a = c.measureText('ABCDEF abcdef 123').width;
  c.font = `700 40px "${fam}", monospace`;
  return Math.abs(c.measureText('ABCDEF abcdef 123').width - a) > 1;
}

window.READY = (async () => {
  T = await (await fetch('timeline.json?v=' + Date.now())).json();
  await Promise.all(['700 70px PF', 'italic 800 70px PF', '900 70px PF', 'italic 600 70px PF'].map(f => document.fonts.load(f)));
  const fonts = {
    pf: document.fonts.check('700 70px PF'), pfi: document.fonts.check('italic 800 70px PF'),
    cond: fontAvailable('Avenir Next Condensed'),
  };
  build();
  return { frames: T.frames, fonts: { ok: fonts.pf && fonts.pfi && fonts.cond, ...fonts } };
})();

function build() {
  const st = T.style || {};   // colours from edit.json "style" (defaults live in reel.html :root)
  for (const [k, v] of [['accent', st.accent], ['paper', st.paper], ['ink', st.ink], ['hl', st.highlight]])
    if (v) document.documentElement.style.setProperty('--' + k, v);
  for (const id of ['stage', 'base', 'cap', 'tracker', 'chapter', 'cards', 'list', 'tags', 'endp'])
    el[id] = $(id);
  el.trLab = el.tracker.querySelector('.lab');
  el.trTit = el.tracker.querySelector('.tit');
  el.trRule = el.tracker.querySelector('.rule');
  el.chKick = el.chapter.querySelector('.kick');
  el.chNum = el.chapter.querySelector('.num');
  el.chTit = el.chapter.querySelector('.tit');
  el.chKick.textContent = T.chapter_kicker || '';
  el.chKick.style.display = T.chapter_kicker ? '' : 'none';

  // study cards, built once and measured so each sits centred on y=880
  el.card = {};
  for (const c of T.cards) {
    const d = document.createElement('div');
    d.className = 'card';
    d.innerHTML = `<div class="kick">${c.kick}</div>` + (c.stat ? `<div class="stat">${c.stat}</div>` : '')
      + `<div class="body">${c.body}</div>` + (c.note ? `<div class="note">${c.note}</div>` : '')
      + `<div class="src">${c.src}</div>`;
    el.cards.appendChild(d);
    d.style.top = Math.round(880 - d.offsetHeight / 2) + 'px';
    el.card[c.id] = { d, marks: [...d.querySelectorAll('mark')], count: d.querySelector('.count'),
      plus: d.querySelector('.plus') };
    d.classList.add('hide');
  }

  // lifestyle list
  if (T.list) {
    el.list.innerHTML = `<div class="lab">${T.list.label}</div>`
      + T.list.items.map(it => `<div class="it"><i></i>${it.text}</div>`).join('');
    el.listLab = el.list.querySelector('.lab');
    el.listIt = [...el.list.querySelectorAll('.it')];
  }

  // rabbit-hole tags
  el.tag = (T.tags ? T.tags.items : []).map(it => {
    const d = document.createElement('div');
    d.className = 'tag hide';
    d.textContent = it.text;
    d.style.left = it.x + 'px';
    d.style.top = it.y + 'px';
    el.tags.appendChild(d);
    return d;
  });

  if (T.end) {
    el.endp.querySelector('.q').textContent = T.end.q;
    el.endp.querySelector('.cta').textContent = T.end.cta;
    el.endp.querySelector('.cta').style.display = T.end.cta ? '' : 'none';
  }
  el.endQ = el.endp.querySelector('.q');
  el.endC = el.endp.querySelector('.cta');

  if (Q.get('guides')) {
    const g = document.createElement('div');
    g.className = 'layer';
    g.innerHTML = '<div style="position:absolute;left:0;right:0;top:0;height:230px;background:rgba(0,160,255,.18)"></div>'
      + '<div style="position:absolute;left:0;right:0;bottom:0;height:420px;background:rgba(0,160,255,.18)"></div>'
      + '<div style="position:absolute;right:0;width:150px;top:980px;bottom:420px;background:rgba(0,160,255,.18)"></div>';
    el.stage.appendChild(g);
    el.face = document.createElement('div');   // where the tracked face (plus hair) is in this frame
    el.face.style.cssText = 'position:absolute;border:4px dashed rgba(255,60,60,.9);pointer-events:none;';
    el.stage.appendChild(el.face);
  }
}

// ---------- base footage: framing, push, snaps, blur under cards
let si = 0;
function shotAt(n) {
  const S = T.shots;
  while (si < S.length - 1 && n >= S[si].f1) si++;
  while (si > 0 && n < S[si].f0) si--;
  return S[si];
}
function blurAt(n) {
  let b = 0;
  for (const w of T.blur) {
    if (n >= w.f0 && n < w.f1) b = Math.max(b, E.outCubic(Math.min(pr(n, w.f0, 6), 1 - pr(n, w.f1 - 6, 6))));
  }
  return b;
}
function renderBase(n) {
  const s = shotAt(n);
  const p = (n - s.f0) / Math.max(1, s.f1 - s.f0);
  let z = s.z * (1 + s.push * p);
  for (const sn of s.snaps) if (n >= sn.f) z += sn.dz * E.outCubic(pr(n, sn.f, 6));
  const bl = blurAt(n);
  z *= 1 + 0.045 * bl;
  const win = 1 / z;
  const left = cl(s.fx - 0.5 * win, 0, 1 - win), top = cl(s.fy - s.oy * win, 0, 1 - win);
  el.base.style.transform = `translate(${(-left * 1080 * z).toFixed(3)}px, ${(-top * 1920 * z).toFixed(3)}px) scale(${z.toFixed(5)})`;
  if (el.face) {
    const fw = (s.fw || 0.25) * 1080 * z, cx = (s.fx - left) * z * 1080, cy = (s.fy - top) * z * 1920;
    // approximate (the shot's median face position): hairline to chin, ear to ear
    el.face.style.left = (cx - fw * 0.6).toFixed(1) + 'px';
    el.face.style.width = (fw * 1.2).toFixed(1) + 'px';
    el.face.style.top = (cy - fw * 0.75).toFixed(1) + 'px';
    el.face.style.height = (fw * 1.3).toFixed(1) + 'px';
  }
  el.base.style.filter = bl > 0.002
    ? `blur(${(22 * bl).toFixed(2)}px) brightness(${(1 - 0.5 * bl).toFixed(3)}) saturate(${(1 - 0.2 * bl).toFixed(3)})` : 'none';
  return { shot: s.fr, z, bl };
}

// ---------- captions: words build on their spoken onset; the keyword pops
let capIdx = -2, capWords = [];
function buildCaption(gi) {
  const cap = el.cap;
  cap.innerHTML = '';
  capWords = [];
  if (gi < 0) return;
  const g = T.captions[gi];
  cap.className = g.kind === 'cap' ? '' : g.kind;
  const lines = g.lines.map(sz => {
    const d = document.createElement('div');
    d.className = 'line' + (sz === 'n' ? '' : ' ' + sz);
    cap.appendChild(d);
    return d;
  });
  for (const w of g.words) {
    const s = document.createElement('span');
    s.className = 'w' + (w.key ? ' k' : '');
    s.textContent = w.t;
    const line = lines[w.line];
    if (line.childNodes.length) line.appendChild(document.createTextNode(' '));
    line.appendChild(s);
    capWords.push(s);
  }
  for (const d of lines) {   // shrink any line wider than the 840 px column
    const w = d.scrollWidth;
    if (w > 840) d.style.fontSize = (parseFloat(getComputedStyle(d).fontSize) * 836 / w).toFixed(2) + 'px';
  }
}
function renderCaptions(n) {
  let gi = -1;
  for (let i = 0; i < T.captions.length; i++) {
    const g = T.captions[i];
    if (n >= g.f0 && n < g.f1) { gi = i; break; }
  }
  if (gi !== capIdx) { buildCaption(gi); capIdx = gi; }
  if (gi < 0) return null;
  const g = T.captions[gi];
  const full = g.kind === 'hook';
  g.words.forEach((w, k) => {
    const s = capWords[k];
    let op = 1, ty = 0, sc = 1;
    if (!full) {
      const q = E.outCubic(pr(n, w.f, 4));
      op = n < w.f ? 0 : q;
      ty = (1 - q) * 20;
    }
    if (w.key && n >= w.f) sc = 1 + (full ? 0.08 : 0.12) * (1 - E.outCubic(pr(n, w.f, 8)));
    s.style.opacity = op.toFixed(3);
    s.style.transform = `translateY(${ty.toFixed(2)}px) scale(${sc.toFixed(4)})`;
  });
  return gi;
}

// ---------- tracker (top): "3 MISTAKES", then "MISTAKE 2/3" + title, then the outro label
let trKey = '';
function renderTracker(n) {
  const st = T.tracker.find(s => n >= s.f0 && n < s.f1);
  if (!st) { el.tracker.classList.add('hide'); return; }
  const key = st.label + '|' + st.title;
  if (key !== trKey) {
    el.trLab.innerHTML = st.label;
    el.trTit.textContent = st.title;
    el.trTit.style.display = st.title ? '' : 'none';
    trKey = key;
  }
  el.tracker.classList.remove('hide');
  const a = E.outCubic(pr(n, st.f0, 7)), o = pr(n, st.f1 - 5, 5);
  el.tracker.style.opacity = (a * (1 - o)).toFixed(3);
  el.tracker.style.transform = `translateY(${((1 - a) * -18).toFixed(2)}px)`;
  el.trRule.style.transform = `scaleX(${E.outCubic(pr(n, st.f0 + 3, 8)).toFixed(3)})`;
}

// ---------- chapter card: kicker / big numeral / the chapter title
let chN = 0;
function renderChapter(n) {
  const c = T.chapters.find(c => n >= c.f0 && n < c.f1);
  if (!c) { el.chapter.classList.add('hide'); return; }
  if (chN !== c.n) {
    el.chNum.textContent = String(c.n);
    el.chTit.innerHTML = c.title.split(' / ').map(t => `<span>${t}</span>`).join('');
    chN = c.n;
  }
  el.chapter.classList.remove('hide');
  const o = E.inCubic(pr(n, c.f1 - 6, 6));
  const k = E.outCubic(pr(n, c.f0 + 1, 6));
  el.chKick.style.opacity = (k * (1 - o)).toFixed(3);
  el.chKick.style.transform = `translateY(${((1 - k) * -16).toFixed(2)}px)`;
  const m = E.outCubic(pr(n, c.f0, 9));
  el.chNum.style.opacity = (Math.min(1, pr(n, c.f0, 4)) * (1 - o)).toFixed(3);
  el.chNum.style.transform = `scale(${(1.22 - 0.22 * m).toFixed(4)})`;
  const t = E.outCubic(pr(n, c.f0 + 4, 8));
  el.chTit.style.opacity = (t * (1 - o)).toFixed(3);
  el.chTit.style.transform = `translateY(${((1 - t) * 34).toFixed(2)}px)`;
  el.chapter.style.transform = `translateY(${(-50 * o).toFixed(2)}px) scale(${(1 - 0.04 * o).toFixed(4)})`;
}

// ---------- study cards
function renderCards(n) {
  for (const c of T.cards) {
    const k = el.card[c.id];
    if (n < c.f0 || n >= c.f1) { k.d.classList.add('hide'); continue; }
    k.d.classList.remove('hide');
    const a = pr(n, c.f0, 11), o = E.inCubic(pr(n, c.f1 - 7, 7));
    const ab = E.outBack(a, 1.25);
    const y = (1 - ab) * 260 + o * 110;
    const rot = -1.2 - (1 - E.outCubic(a)) * 3.5;
    k.d.style.transform = `translateY(${y.toFixed(2)}px) rotate(${rot.toFixed(3)}deg)`;
    k.d.style.opacity = (Math.min(1, pr(n, c.f0, 5)) * (1 - o)).toFixed(3);
    const h = E.inOutCubic(pr(n, c.f0 + 13, 13));
    for (const m of k.marks) m.style.backgroundSize = `${(h * 100).toFixed(2)}% 100%`;
    if (k.count) {
      const v = Math.round(1000 * E.outCubic(pr(n, c.f0 + 5, 22)));
      k.count.textContent = v.toLocaleString('en-US');
      k.plus.style.opacity = v >= 1000 ? '1' : '0';
    }
  }
}

// ---------- lifestyle list
function renderList(n) {
  const L = T.list;
  if (!L || n < L.f0 || n >= L.f1) { el.list.classList.add('hide'); return; }
  el.list.classList.remove('hide');
  const o = pr(n, L.f1 - 5, 5);
  el.list.style.opacity = (1 - o).toFixed(3);
  const l = E.outCubic(pr(n, L.f0, 6));
  el.listLab.style.opacity = l.toFixed(3);
  L.items.forEach((it, i) => {
    const q = E.outCubic(pr(n, it.f, 6));
    const d = el.listIt[i];
    d.style.opacity = (n < it.f ? 0 : q).toFixed(3);
    d.style.transform = `translateX(${((1 - q) * -46).toFixed(2)}px)`;
  });
}

// ---------- rabbit-hole tags
function renderTags(n) {
  const G = T.tags;
  if (!G) return;
  G.items.forEach((it, i) => {
    const d = el.tag[i];
    if (n < it.f || n >= G.f1) { d.classList.add('hide'); return; }
    d.classList.remove('hide');
    const a = pr(n, it.f, 9), o = E.inCubic(pr(n, G.out, 6));
    const sc = (0.55 + 0.45 * E.outBack(a, 2.4)) * (1 - 0.25 * o);
    d.style.opacity = (Math.min(1, pr(n, it.f, 3)) * (1 - o)).toFixed(3);
    d.style.transform = `translateY(${(-60 * o).toFixed(2)}px) rotate(${it.r}deg) scale(${sc.toFixed(4)})`;
  });
}

// ---------- end prompt
function renderEnd(n) {
  if (!T.end) { el.endp.classList.add('hide'); return; }
  const f0 = T.end.f0;
  if (n < f0) { el.endp.classList.add('hide'); return; }
  el.endp.classList.remove('hide');
  const a = pr(n, f0, 10), b = pr(n, f0 + 6, 10);
  el.endQ.style.opacity = Math.min(1, pr(n, f0, 3)).toFixed(3);
  el.endQ.style.transform = `rotate(-1.5deg) scale(${(0.6 + 0.4 * E.outBack(a, 2.2)).toFixed(4)})`;
  el.endC.style.opacity = Math.min(1, pr(n, f0 + 6, 3)).toFixed(3);
  el.endC.style.transform = `rotate(1deg) scale(${(0.6 + 0.4 * E.outBack(b, 2.2)).toFixed(4)})`;
}

window.renderFrame = async (n, url) => {
  await window.READY;
  if (url) {
    el.base.src = url;
    await el.base.decode();
  }
  const b = renderBase(n);
  const gi = renderCaptions(n);
  renderTracker(n);
  renderChapter(n);
  renderCards(n);
  renderList(n);
  renderTags(n);
  renderEnd(n);
  return { n, shot: b.shot, z: +b.z.toFixed(3), blur: +b.bl.toFixed(2), cap: gi };
};
