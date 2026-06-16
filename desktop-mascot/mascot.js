// Renderer: pick the mascot, idle, and REACT to VERITY's gates firing (read from the decision ledger).
const stage = document.getElementById('stage');
const img = document.getElementById('mascot');
const emote = document.getElementById('emote');
const dot = document.getElementById('dot');

const SPRITES = {hawk: 'assets/mascot-hawk.png', sun: 'assets/mascot-sun.png'};
let current = 'hawk';

function setMascot(m) {
  if (!SPRITES[m]) return;
  current = m; img.src = SPRITES[m];
  window.verity.saveCfg({mascot: m});
}

// Map a ledger verdict to a reaction (silent — emote glyph + motion, never words).
function reactionFor(verdict, gate) {
  const v = (verdict || '').toUpperCase();
  if (v === 'VERIFIED' || v === 'FOUND' || v === 'PASS') return {cls: 'react-success', glyph: '✓'};
  if (v === 'CORRECTED' || v === 'NEGATIVE' || v === 'DEFER' || v === 'FAIL') return {cls: 'react-alert', glyph: '!'};
  if (v === 'NONE' || (gate || '').toLowerCase().includes('search')) return {cls: 'react-think', glyph: '🔍'};
  return null;
}

let reacting = false;
function playReaction(r) {
  if (!r || reacting) return;
  reacting = true;
  stage.classList.add(r.cls);
  emote.textContent = r.glyph; emote.classList.add('show');
  setTimeout(() => { stage.classList.remove(r.cls); emote.classList.remove('show'); reacting = false; }, 1400);
}

// Watch the ledger: when a NEW event lands (mtime advanced), react to its verdict.
let lastMtime = 0;
function pollLedger() {
  const ev = window.verity.latestLedgerEvent();
  if (ev && ev.mtime > lastMtime) {
    if (lastMtime !== 0) playReaction(reactionFor(ev.verdict, ev.gate));  // skip the first (startup) read
    lastMtime = ev.mtime;
  }
}

// Liveness: is the proxy floor up? Show the teal "installed & working" dot.
async function pollProxy() {
  const up = await window.verity.proxyUp();
  dot.classList.toggle('up', up);
}

// Occasional spontaneous idle flourish so it feels alive even when nothing's happening.
function idleFlourish() {
  if (!reacting && Math.random() < 0.25) playReaction({cls: 'react-think', glyph: '·'});
}

(async () => {
  // Degrade gracefully in a plain browser (no Electron preload): still idle + click-to-toggle for demos.
  if (!window.verity) {
    setMascot('hawk');
    stage.addEventListener('click', () => setMascot(current === 'hawk' ? 'sun' : 'hawk'));
    setInterval(idleFlourish, 9000);
    return;
  }
  const cfg = await window.verity.getCfg();
  setMascot(cfg.mascot || 'hawk');
  window.verity.onSetMascot(setMascot);
  pollProxy(); setInterval(pollProxy, 5000);
  setInterval(pollLedger, 1200);
  setInterval(idleFlourish, 9000);
})();
