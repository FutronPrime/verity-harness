// VERITY desktop mascot — a frameless, transparent, always-on-top desktop pet that idles in the
// corner and reacts to the harness. Toggle it, switch Truth Hawk <-> VERI the Sun, drag it anywhere.
const {app, BrowserWindow, Tray, Menu, ipcMain, screen, nativeImage} = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');

let win = null;
let tray = null;
let visible = true;
const SIZE = 200;
const CFG = path.join(os.homedir(), '.verity-harness', 'mascot.json');

function loadCfg() {
  try { return JSON.parse(fs.readFileSync(CFG, 'utf8')); } catch { return {mascot: 'hawk'}; }
}
function saveCfg(c) {
  try { fs.mkdirSync(path.dirname(CFG), {recursive: true}); fs.writeFileSync(CFG, JSON.stringify(c)); } catch {}
}

function createWindow() {
  const {width, height} = screen.getPrimaryDisplay().workAreaSize;
  win = new BrowserWindow({
    width: SIZE, height: SIZE,
    x: width - SIZE - 24, y: height - SIZE - 24,   // bottom-right corner
    frame: false, transparent: true, resizable: false,
    alwaysOnTop: true, skipTaskbar: true, hasShadow: false,
    focusable: false,                               // doesn't steal focus
    webPreferences: {preload: path.join(__dirname, 'preload.js'), contextIsolation: true},
  });
  win.setAlwaysOnTop(true, 'screen-saver');         // float above full-screen apps too
  win.setVisibleOnAllWorkspaces(true, {visibleOnFullScreen: true});
  win.loadFile('index.html');
  win.setIgnoreMouseEvents(false);
}

function buildTray() {
  // tiny teal "V" tray icon (generated, no asset needed)
  const img = nativeImage.createFromDataURL(
    'data:image/svg+xml;base64,' + Buffer.from(
      `<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22"><path d="M3 4 L11 19 L19 4 L16 4 L11 13 L6 4 Z" fill="#2dd4bf"/></svg>`
    ).toString('base64'));
  tray = new Tray(img);
  const menu = () => Menu.buildFromTemplate([
    {label: 'VERITY mascot', enabled: false},
    {type: 'separator'},
    {label: visible ? 'Hide' : 'Show', click: () => { visible = !visible; visible ? win.show() : win.hide(); tray.setContextMenu(menu()); }},
    {label: 'Switch: Truth Hawk', click: () => win.webContents.send('set-mascot', 'hawk')},
    {label: 'Switch: VERI (Sun)', click: () => win.webContents.send('set-mascot', 'sun')},
    {type: 'separator'},
    {label: 'Quit', click: () => app.quit()},
  ]);
  tray.setToolTip('VERITY — installed & watching');
  tray.setContextMenu(menu());
}

// Renderer asks for the saved mascot choice + persists changes.
ipcMain.handle('get-cfg', () => loadCfg());
ipcMain.on('save-cfg', (_e, c) => saveCfg(c));

app.whenReady().then(() => { createWindow(); buildTray(); if (app.dock) app.dock.hide(); });
app.on('window-all-closed', () => {});  // stay alive in the tray
