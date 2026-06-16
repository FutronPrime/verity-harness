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
    webPreferences: {preload: path.join(__dirname, 'preload.js'), contextIsolation: true},
  });
  win.setVisibleOnAllWorkspaces(true, {visibleOnFullScreen: true});
  win.loadFile('index.html');
  applyLayer(cfg);
}

function openSetup() {
  if (setupWin) { setupWin.focus(); return; }
  setupWin = new BrowserWindow({width: 470, height: 680, resizable: true, title: 'VERITY mascot',
    webPreferences: {preload: path.join(__dirname, 'preload.js'), contextIsolation: true}});
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
  const chk = (k, v) => c[k] === v;
  return Menu.buildFromTemplate([
    {label: 'VERITY — installed & watching', enabled: false},
    {type: 'separator'},
    {label: 'Mascot', submenu: [
      {label: 'Truth Hawk', type: 'radio', checked: chk('mascot','hawk'), click: pick('mascot','hawk')},
      {label: 'VERI (Sun)', type: 'radio', checked: chk('mascot','sun'),  click: pick('mascot','sun')},
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
    {type: 'separator'},
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

ipcMain.handle('get-cfg', () => loadCfg());
ipcMain.on('save-cfg', (_e, c) => { saveCfg({...loadCfg(), ...c}); rebuild(); if (tray) tray.setContextMenu(trayMenu()); });
ipcMain.on('setup-done', (_e, c) => { saveCfg({...loadCfg(), ...c, configured: true}); if (setupWin) setupWin.close(); rebuild(); if (tray) tray.setContextMenu(trayMenu()); });
// Custom drag (so the mascot is both DRAGGABLE and CLICKABLE — app-region drag ate the clicks).
ipcMain.on('move-window', (_e, dx, dy) => { if (win) { const [x, y] = win.getPosition(); win.setPosition(Math.round(x + dx), Math.round(y + dy)); } });
// Right-click the MASCOT → pop the same menu the tray has, at the cursor.
ipcMain.on('show-menu', () => { if (tray) trayMenu().popup(); });

app.whenReady().then(() => {
  const cfg = loadCfg();
  buildTray();
  if (!cfg.configured) openSetup();                // first run → onboarding picker
  else createWindow(cfg);
  if (app.dock) app.dock.hide();
});
app.on('window-all-closed', () => {});             // stay alive in the tray
