// Renderer: render the chosen mascot, idle, and (in full mode) REACT to VERITY's gates firing.
// Now that we have REAL per-state animations (transparent WebP, generated via Ludo — see
// feedback_transparent_animation_professional_motion), every VERITY action swaps the mascot to a
// genuine animation, not a CSS shake. Event→state taxonomy mirrors clawd-on-desk's state-mapping.
const stage = document.getElementById('stage');
const img = document.getElementById('mascot');
const emote = document.getElementById('emote');
const dot = document.getElementById('dot');

// Static fallbacks (used only if a state's animated WebP is missing for that mascot).
const SPRITES = {hawk: 'assets/mascot-hawk.png', sun: 'assets/mascot-sun.png',
                 avani: 'assets/mascot-avani.png', logo: 'assets/logo.png'};
let cfg = {mascot: 'hawk', animations: 'full', frequency: 'med'};
const FREQ = {low: {flourish: 18000, chance: 0.10}, med: {flourish: 9000, chance: 0.25}, high: {flourish: 4500, chance: 0.55}};

// STATE MACHINE. Each state can have a real animated WebP (transparent) at
// assets/anim/<mascot>-<state>.webp (generated via Ludo). If a state's WebP is missing for a mascot
// we gracefully fall back to that mascot's static sprite + a CSS micro-reaction — so partially-animated
// mascots still work. (clawd-on-desk model.) Robust state set:
//   idle · thinking · building · juggling · success · error · notification · sleeping
const STATES = ['idle', 'thinking', 'building', 'juggling', 'success', 'error', 'notification', 'sleeping'];
function gifFor(state) { return `assets/anim/${cfg.mascot}-${state}.webp`; }

let currentState = 'idle';
function setState(state) {
  currentState = state;
  const want = gifFor(state);
  const probe = new Image();
  probe.onload = () => { if (currentState === state) img.src = want; };
  probe.onerror = () => {                                        // no WebP for this mascot+state
    const fallbackAnim = gifFor('idle');                          // try the mascot's idle anim first
    const p2 = new Image();
    p2.onload = () => { if (currentState === state) img.src = fallbackAnim; };
    p2.onerror = () => { if (currentState === state) img.src = SPRITES[cfg.mascot] || SPRITES.hawk; };
    p2.src = fallbackAnim + '?v=' + cfg.mascot;
  };
  probe.src = want + '?v=' + cfg.mascot;                          // cache-stable per mascot
}

function render(c) {
  cfg = {...cfg, ...c};
  img.style.width = cfg.mascot === 'logo' ? '180px' : '150px';
  if (cfg.mascot === 'logo') { img.src = SPRITES.logo; return; }
  setState(asleep ? 'sleeping' : 'idle');
}

// VERITY event → animation state. Grounded in the real ledger gates the harness emits:
//   gate: swarm-plan|swarm-critic|swarm-synth (multi-agent) · search-before-concluding · assumption-caught
//   verdict: FOUND|VERIFIED|PASS · CORRECTED|NEGATIVE|DEFER|FAIL · NONE
function reactionFor(verdict, gate) {
  const v = (verdict || '').toUpperCase();
  const g = (gate || '').toLowerCase();
  if (g.startsWith('swarm') || g.includes('agent')) return {state: 'juggling', cls: 'react-think', glyph: '🤹'};
  if (g.includes('assumption'))                      return {state: 'notification', cls: 'react-alert', glyph: '!'};
  if (g.includes('search') || v === 'NONE')          return {state: 'thinking', cls: 'react-think', glyph: '🔍'};
  if (g.includes('verify') || g.includes('preflight') || g.includes('plan') || g.includes('build'))
                                                     return {state: 'building', cls: 'react-think', glyph: '⚙'};
  if (v === 'VERIFIED' || v === 'FOUND' || v === 'PASS') return {state: 'success', cls: 'react-success', glyph: '✓'};
  if (v === 'CORRECTED' || v === 'NEGATIVE' || v === 'DEFER' || v === 'FAIL') return {state: 'error', cls: 'react-alert', glyph: '!'};
  return null;
}

let reacting = false;
function playReaction(r) {
  if (!r || reacting || asleep) return;
  reacting = true;
  if (r.state) setState(r.state);            // swap to the state's real animation
  stage.classList.add(r.cls);                // + CSS micro-reaction (harmless when a real anim is present)
  emote.textContent = r.glyph; emote.classList.add('show');
  // juggling/building states run a touch longer (they're "ongoing work" feel); reactions are 1.8s.
  const hold = (r.state === 'juggling' || r.state === 'building') ? 2600 : 1800;
  setTimeout(() => {
    stage.classList.remove(r.cls); emote.classList.remove('show'); reacting = false;
    setState(asleep ? 'sleeping' : 'idle');
  }, hold);
}

// Sleep: proxy down OR 60s with no harness activity → drift to the sleeping animation; any event wakes it.
let asleep = false, lastActivity = Date.now();
function sleep()  { if (!asleep) { asleep = true;  setState('sleeping'); } }
function wake()   { if (asleep)  { asleep = false; setState('idle'); } lastActivity = Date.now(); }

let lastMtime = 0;
function pollLedger() {
  if (cfg.animations !== 'full') return;            // idle-only mode: no harness reactions
  const ev = window.verity.latestLedgerEvent();
  if (ev && ev.mtime > lastMtime) {
    if (lastMtime !== 0) { wake(); playReaction(reactionFor(ev.verdict, ev.gate)); }
    lastMtime = ev.mtime;
  }
  if (!asleep && !reacting && Date.now() - lastActivity > 60000) sleep();
}

async function pollProxy() {
  const up = await window.verity.proxyUp();
  dot.classList.toggle('up', up);
  if (cfg.animations === 'full') { if (!up) sleep(); else if (asleep && Date.now() - lastActivity < 60000) wake(); }
}

function idleFlourish() {
  if (cfg.animations !== 'full' || asleep) return;
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
  if (down && !moved) {                       // click → happy (sun sometimes throws on shades 😎)
    wake();
    const flex = (cfg.mascot === 'sun' && Math.random() < 0.4);
    playReaction(flex ? {state: 'shades', cls: 'react-success', glyph: '😎'}
                      : {state: 'success', cls: 'react-success', glyph: '✓'});
  }
  down = false;
});
// Right-click the mascot → the options menu (switch / hide / position / frequency / setup).
stage.addEventListener('contextmenu', (e) => { e.preventDefault(); if (window.verity && window.verity.showMenu) window.verity.showMenu(); });

// The status dot doubles as a VOICE-MODE TOGGLE: click it to flip TL;DR read-outs ↔ interactive
// talk-back. Intercept on the dot (stopPropagation) so it doesn't trigger the drag/click-react logic.
let voiceMode = 'tldr';
function applyVoiceMode(m) {
  voiceMode = (m === 'interactive') ? 'interactive' : 'tldr';
  dot.classList.toggle('interactive', voiceMode === 'interactive');
  dot.title = voiceMode === 'interactive'
    ? 'Voice: INTERACTIVE — real-time talk-back (costly). Click for read-out mode.'
    : 'Voice: read-out TL;DR (free). Click for interactive talk-back.';
}
dot.addEventListener('mousedown', (e) => {
  e.stopPropagation();
  applyVoiceMode(voiceMode === 'interactive' ? 'tldr' : 'interactive');
  if (window.verity && window.verity.setVoiceMode) window.verity.setVoiceMode(voiceMode);
});

// Audio-reactive dot: while the voice path is talking back (TTS), pulse the dot to the speech pace by
// reading the live RMS envelope. Drives scale + glow from amplitude — a voice indicator, like on the show.
let speaking = false;
async function pollVoice() {
  if (!window.verity || !window.verity.voiceLevel) return;
  let v; try { v = await window.verity.voiceLevel(); } catch { return; }
  if (v && v.speaking) {
    speaking = true;
    dot.classList.add('speaking');
    const s = (1 + v.level * 1.5).toFixed(2);
    dot.style.transform = `scale(${s})`;
    dot.style.boxShadow = `0 0 ${Math.round(6 + v.level * 20)}px rgba(45,212,191,${(0.45 + v.level * 0.55).toFixed(2)})`;
  } else if (speaking) {
    speaking = false;
    dot.classList.remove('speaking');
    dot.style.transform = '';
    dot.style.boxShadow = '';
  }
}

let flourishTimer = null;
function startLoops() {
  clearInterval(flourishTimer);
  flourishTimer = setInterval(idleFlourish, (FREQ[cfg.frequency] || FREQ.med).flourish);
}

(async () => {
  if (!window.verity) { render({mascot: 'hawk'}); stage.addEventListener('click',
    () => render({mascot: cfg.mascot === 'hawk' ? 'sun' : (cfg.mascot === 'sun' ? 'avani' : 'hawk')})); return; }   // browser-preview fallback cycles all 3
  render(await window.verity.getCfg());
  window.verity.onCfg((c) => { render(c); startLoops(); });   // live updates from the tray/setup
  if (window.verity.getVoiceMode) applyVoiceMode(await window.verity.getVoiceMode());
  pollProxy(); setInterval(pollProxy, 5000);
  setInterval(pollVoice, 80);   // audio-reactive dot (pulses to the TTS pace while talking back)
  setInterval(pollLedger, 1200);
  startLoops();
})();
