// VERITY desktop mascot — a configurable, frameless, transparent desktop pet that reacts to the harness.
const {app, BrowserWindow, Tray, Menu, ipcMain, screen, nativeImage} = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');

let win = null, setupWin = null, tray = null;
const SIZE = 200;
const CFG = path.join(os.homedir(), '.verity-harness', 'mascot.json');

// config: mascot = hawk | sun | logo | none ; animations = full | idle ;
// layer = front (above all windows) | desktop (only on the desktop) ; frequency = low | med | high
const DEFAULTS = {mascot: 'hawk', animations: 'full', layer: 'front', frequency: 'med', configured: false};
function loadCfg() { try { return {...DEFAULTS, ...JSON.parse(fs.readFileSync(CFG, 'utf8'))}; } catch { return {...DEFAULTS}; } }
function saveCfg(c) { try { fs.mkdirSync(path.dirname(CFG), {recursive: true}); fs.writeFileSync(CFG, JSON.stringify(c)); } catch {} }
// A mascot is OFFERED only if its assets are present. hawk/sun/logo ship with the repo; AVANI is a
// private easter egg — her assets are NOT in the public repo (gitignored), so she appears ONLY on a
// build that has them locally. Same code everywhere; availability is data-driven, no fork needed.
function hasAvani() { try { return fs.existsSync(path.join(__dirname, 'assets', 'mascot-avani.png')); } catch { return false; } }

function applyLayer(cfg) {
  if (!win) return;
  if (cfg.layer === 'front') { win.setAlwaysOnTop(true, 'screen-saver'); }
  else { win.setAlwaysOnTop(false); }              // 'desktop' = behind other windows, on the desktop
}

function createWindow(cfg) {
  if (cfg.mascot === 'none') return;               // user opted out of the visual
  const {width, height} = screen.getPrimaryDisplay().workAreaSize;
  win = new BrowserWindow({
    width: SIZE, height: SIZE, x: width - SIZE - 24, y: height - SIZE - 24,
    frame: false, transparent: true, resizable: false, skipTaskbar: true, hasShadow: false,
    // sandbox:false so the preload can require fs/path (read the ledger) — without it Electron 31's
    // default sandbox kills the preload and window.verity is never exposed (the "bridge not loaded" bug).
    webPreferences: {preload: path.join(__dirname, 'preload.js'), contextIsolation: true, sandbox: false},
  });
  win.setVisibleOnAllWorkspaces(true, {visibleOnFullScreen: true});
  win.loadFile('index.html');
  applyLayer(cfg);
}

function openSetup() {
  if (setupWin) { setupWin.focus(); return; }
  setupWin = new BrowserWindow({width: 470, height: 680, resizable: true, title: 'VERITY mascot',
    webPreferences: {preload: path.join(__dirname, 'preload.js'), contextIsolation: true, sandbox: false}});
  setupWin.loadFile('setup.html');
  setupWin.on('closed', () => { setupWin = null; });
}

function rebuild() {                                // re-apply config to the live window
  const cfg = loadCfg();
  if (cfg.mascot === 'none') { if (win) { win.close(); win = null; } return; }
  if (!win) createWindow(cfg); else { applyLayer(cfg); win.show(); win.webContents.send('cfg', cfg); }
}

function trayMenu() {
  const c = loadCfg();
  const pick = (k, v) => () => { const n = {...loadCfg(), [k]: v, configured: true}; saveCfg(n); rebuild(); tray.setContextMenu(trayMenu()); };
  // Voice picks also mirror to the state files the voice loop reads, so they take effect live.
  const pickV = (k, v) => () => {
    saveCfg({...loadCfg(), [k]: v, configured: true});
    try {
      const sd = path.join(os.homedir(), '.verity-harness'); fs.mkdirSync(sd, {recursive: true});
      if (k === 'readout') fs.writeFileSync(path.join(sd, 'tts-style'), v);
      if (k === 'interactive') fs.writeFileSync(path.join(sd, 'voice-mode'), v === 'ptt' ? 'interactive' : 'tldr');
    } catch {}
    rebuild(); tray.setContextMenu(trayMenu());
  };
  const chk = (k, v) => c[k] === v;
  return Menu.buildFromTemplate([
    {label: 'VERITY — installed & watching', enabled: false},
    {type: 'separator'},
    {label: 'Mascot', submenu: [
      {label: 'Truth Hawk', type: 'radio', checked: chk('mascot','hawk'), click: pick('mascot','hawk')},
      {label: 'VERI (Sun)', type: 'radio', checked: chk('mascot','sun'),  click: pick('mascot','sun')},
      ...(hasAvani() ? [{label: 'AVANI ✦ (easter egg)', type: 'radio', checked: chk('mascot','avani'), click: pick('mascot','avani')}] : []),
      {label: 'Logo only',  type: 'radio', checked: chk('mascot','logo'), click: pick('mascot','logo')},
      {label: 'None (off)', type: 'radio', checked: chk('mascot','none'), click: pick('mascot','none')},
    ]},
    {label: 'Animations', submenu: [
      {label: 'Full (reacts to the harness)', type: 'radio', checked: chk('animations','full'), click: pick('animations','full')},
      {label: 'Idle only', type: 'radio', checked: chk('animations','idle'), click: pick('animations','idle')},
    ]},
    {label: 'Reaction frequency', submenu: [
      {label: 'Low',    type: 'radio', checked: chk('frequency','low'),  click: pick('frequency','low')},
      {label: 'Medium', type: 'radio', checked: chk('frequency','med'),  click: pick('frequency','med')},
      {label: 'High',   type: 'radio', checked: chk('frequency','high'), click: pick('frequency','high')},
    ]},
    {label: 'Position', submenu: [
      {label: 'In front of all windows', type: 'radio', checked: chk('layer','front'),   click: pick('layer','front')},
      {label: 'On the desktop only',     type: 'radio', checked: chk('layer','desktop'), click: pick('layer','desktop')},
    ]},
    {label: 'Voice', submenu: [
      {label: 'Speak: Silent',  type: 'radio', checked: chk('voice','off') || !c.voice, click: pickV('voice','off')},
      {label: 'Speak: TL;DR',   type: 'radio', checked: chk('voice','tldr'), click: pickV('voice','tldr')},
      {label: 'Speak: Full',    type: 'radio', checked: chk('voice','full'), click: pickV('voice','full')},
      {type: 'separator'},
      {label: 'Style: Standard (warm)',          type: 'radio', checked: chk('readout','standard') || !c.readout, click: pickV('readout','standard')},
      {label: 'Style: LCARS / J.A.R.V.I.S.',     type: 'radio', checked: chk('readout','lcars'), click: pickV('readout','lcars')},
      {label: 'Style: AISHA (Gen-Z)',            type: 'radio', checked: chk('readout','aisha'), click: pickV('readout','aisha')},
      {type: 'separator'},
      {label: 'Engine: Free · Voicebox', type: 'radio', checked: chk('voiceengine','oss') || !c.voiceengine, click: pickV('voiceengine','oss')},
      {label: 'Engine: OpenAI',          type: 'radio', checked: chk('voiceengine','openai'), click: pickV('voiceengine','openai')},
      {label: 'Engine: ElevenLabs',      type: 'radio', checked: chk('voiceengine','elevenlabs'), click: pickV('voiceengine','elevenlabs')},
      {label: 'Engine: Hybrid',          type: 'radio', checked: chk('voiceengine','hybrid'), click: pickV('voiceengine','hybrid')},
      {type: 'separator'},
      {label: 'Talk back: Off',          type: 'radio', checked: chk('interactive','off') || !c.interactive, click: pickV('interactive','off')},
      {label: 'Talk back: Push-to-talk', type: 'radio', checked: chk('interactive','ptt'), click: pickV('interactive','ptt')},
    ]},
    {type: 'separator'},
    {label: 'How it works ▶', click: () => { if (!win) rebuild(); if (win) win.webContents.send('show-tour'); }},
    {label: 'Setup / pick again…', click: openSetup},
    {label: win && win.isVisible() ? 'Hide' : 'Show', click: () => { if (!win) rebuild(); else (win.isVisible() ? win.hide() : win.show()); tray.setContextMenu(trayMenu()); }},
    {label: 'Quit', click: () => app.quit()},
  ]);
}

function buildTray() {
  const img = nativeImage.createFromDataURL('data:image/svg+xml;base64,' + Buffer.from(
    `<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22"><path d="M3 4 L11 19 L19 4 L16 4 L11 13 L6 4 Z" fill="#2dd4bf"/></svg>`).toString('base64'));
  tray = new Tray(img);
  tray.setToolTip('VERITY — installed & watching');
  tray.setContextMenu(trayMenu());
}

ipcMain.handle('get-cfg', () => ({...loadCfg(), _avani: hasAvani()}));
ipcMain.on('save-cfg', (_e, c) => { saveCfg({...loadCfg(), ...c}); rebuild(); if (tray) tray.setContextMenu(trayMenu()); });
ipcMain.on('setup-done', (_e, c) => { saveCfg({...loadCfg(), ...c, configured: true}); if (setupWin) setupWin.close(); rebuild(); if (tray) tray.setContextMenu(trayMenu()); });
// Custom drag (so the mascot is both DRAGGABLE and CLICKABLE — app-region drag ate the clicks).
ipcMain.on('move-window', (_e, dx, dy) => { if (win) { const [x, y] = win.getPosition(); win.setPosition(Math.round(x + dx), Math.round(y + dy)); } });
// Right-click the MASCOT → pop the same menu the tray has, at the cursor.
ipcMain.on('show-menu', () => { if (tray) trayMenu().popup(); });
// The status dot doubles as a voice-mode toggle → persist the mode where the voice loop reads it.
const VOICE_MODE = path.join(os.homedir(), '.verity-harness', 'voice-mode');
ipcMain.handle('get-voice-mode', () => { try { return fs.readFileSync(VOICE_MODE, 'utf8').trim() || 'tldr'; } catch { return 'tldr'; } });
ipcMain.on('set-voice-mode', (_e, m) => { try { fs.mkdirSync(path.dirname(VOICE_MODE), {recursive: true}); fs.writeFileSync(VOICE_MODE, m === 'interactive' ? 'interactive' : 'tldr'); } catch {} });
// Live TTS amplitude for the audio-reactive dot. The voice path writes {start, win, rms[]} while speaking;
// we index the envelope by elapsed wall-clock and hand back the current level (or {speaking:false}).
const VOICE_SPEAKING = path.join(os.homedir(), '.verity-harness', 'voice-speaking');
ipcMain.handle('voice-level', () => {
  try {
    const j = JSON.parse(fs.readFileSync(VOICE_SPEAKING, 'utf8'));
    if (!Array.isArray(j.rms) || !j.rms.length) return {speaking: false};
    const idx = Math.floor((Date.now() - j.start) / (j.win || 80));
    if (idx < 0 || idx >= j.rms.length) return {speaking: false};
    return {speaking: true, level: Math.max(0.12, Math.min(1, j.rms[idx] || 0.3))};
  } catch { return {speaking: false}; }
});

// Single-instance lock: so VERITY's startup can always try to launch the mascot without stacking —
// a second launch just quits (and surfaces the existing one).
if (!app.requestSingleInstanceLock()) { app.quit(); }
else {
  app.on('second-instance', () => { if (win) { win.show(); win.focus(); } else if (setupWin) setupWin.focus(); });
  app.whenReady().then(() => {
    const cfg = loadCfg();
    buildTray();
    if (!cfg.configured) openSetup();              // first run → onboarding picker
    else createWindow(cfg);
    if (app.dock) app.dock.hide();
  });
}
app.on('window-all-closed', () => {});             // stay alive in the tray
