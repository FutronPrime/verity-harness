// Renderer: render the chosen mascot, idle, and (in full mode) REACT to VERITY's gates firing.
const stage = document.getElementById('stage');
const img = document.getElementById('mascot');
const emote = document.getElementById('emote');
const dot = document.getElementById('dot');

const SPRITES = {hawk: 'assets/mascot-hawk.png', sun: 'assets/mascot-sun.png', logo: 'assets/logo.png'};
let cfg = {mascot: 'hawk', animations: 'full', frequency: 'med'};
const FREQ = {low: {flourish: 18000, chance: 0.10}, med: {flourish: 9000, chance: 0.25}, high: {flourish: 4500, chance: 0.55}};

// STATE MACHINE: each state can have a real animated GIF at assets/anim/<mascot>-<state>.gif (generated
// via Ludo/Higgsfield). If a state's GIF is missing for a mascot, we gracefully fall back to the static
// sprite + a CSS micro-reaction — so partially-animated mascots still work. (clawd-on-desk model.)
const STATES = ['idle', 'success', 'error', 'thinking', 'building'];
function gifFor(state) { return `assets/anim/${cfg.mascot}-${state}.gif`; }

function setState(state) {
  const want = gifFor(state);
  // probe the gif; on error fall back to the static sprite (mascots without that anim yet)
  const probe = new Image();
  probe.onload = () => { img.src = want; };
  probe.onerror = () => { img.src = SPRITES[cfg.mascot] || SPRITES.hawk; };
  probe.src = want + '?v=' + (cfg.mascot);   // cache-stable per mascot
}

function render(c) {
  cfg = {...cfg, ...c};
  img.style.width = cfg.mascot === 'logo' ? '180px' : '150px';
  if (cfg.mascot === 'logo') { img.src = SPRITES.logo; return; }
  setState('idle');                          // resting animation (or static fallback)
}

function reactionFor(verdict, gate) {
  const v = (verdict || '').toUpperCase();
  if (v === 'VERIFIED' || v === 'FOUND' || v === 'PASS') return {state: 'success', cls: 'react-success', glyph: '✓'};
  if (v === 'CORRECTED' || v === 'NEGATIVE' || v === 'DEFER' || v === 'FAIL') return {state: 'error', cls: 'react-alert', glyph: '!'};
  if (v === 'NONE' || (gate || '').toLowerCase().includes('search')) return {state: 'thinking', cls: 'react-think', glyph: '🔍'};
  return null;
}

let reacting = false;
function playReaction(r) {
  if (!r || reacting) return;
  reacting = true;
  if (r.state) setState(r.state);            // swap to the state's real animation (GIF) if it exists
  stage.classList.add(r.cls);                // + CSS micro-reaction (the fallback when no GIF, harmless with one)
  emote.textContent = r.glyph; emote.classList.add('show');
  setTimeout(() => {
    stage.classList.remove(r.cls); emote.classList.remove('show'); reacting = false;
    setState('idle');                        // back to the resting animation
  }, 1800);
}

let lastMtime = 0;
function pollLedger() {
  if (cfg.animations !== 'full') return;            // idle-only mode: no harness reactions
  const ev = window.verity.latestLedgerEvent();
  if (ev && ev.mtime > lastMtime) {
    if (lastMtime !== 0) playReaction(reactionFor(ev.verdict, ev.gate));
    lastMtime = ev.mtime;
  }
}

async function pollProxy() { dot.classList.toggle('up', await window.verity.proxyUp()); }

function idleFlourish() {
  if (cfg.animations !== 'full') return;
  if (!reacting && Math.random() < (FREQ[cfg.frequency] || FREQ.med).chance)
    playReaction({cls: 'react-think', glyph: '·'});
}

// Custom drag + click + right-click. (app-region drag ate the clicks, so we do it ourselves: track
// movement on press; if barely moved → it's a CLICK → react; otherwise move the window via IPC.)
let down = false, moved = false, lastX = 0, lastY = 0;
stage.addEventListener('mousedown', (e) => {
  if (e.button !== 0) return;          // left only; right-click handled below
  down = true; moved = false; lastX = e.screenX; lastY = e.screenY;
});
window.addEventListener('mousemove', (e) => {
  if (!down) return;
  const dx = e.screenX - lastX, dy = e.screenY - lastY;
  if (Math.abs(dx) + Math.abs(dy) > 2) { moved = true; if (window.verity && window.verity.moveWindow) window.verity.moveWindow(dx, dy); lastX = e.screenX; lastY = e.screenY; }
});
window.addEventListener('mouseup', () => {
  if (down && !moved) playReaction({state: 'success', cls: 'react-success', glyph: '✓'});   // click → success animation
  down = false;
});
// Right-click the mascot → the options menu (switch / hide / position / frequency / setup).
stage.addEventListener('contextmenu', (e) => { e.preventDefault(); if (window.verity && window.verity.showMenu) window.verity.showMenu(); });

let flourishTimer = null;
function startLoops() {
  clearInterval(flourishTimer);
  flourishTimer = setInterval(idleFlourish, (FREQ[cfg.frequency] || FREQ.med).flourish);
}

(async () => {
  if (!window.verity) { render({mascot: 'hawk'}); stage.addEventListener('click',
    () => render({mascot: cfg.mascot === 'hawk' ? 'sun' : 'hawk'})); return; }   // browser-preview fallback
  render(await window.verity.getCfg());
  window.verity.onCfg((c) => { render(c); startLoops(); });   // live updates from the tray/setup
  pollProxy(); setInterval(pollProxy, 5000);
  setInterval(pollLedger, 1200);
  startLoops();
})();
