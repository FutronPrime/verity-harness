const {contextBridge, ipcRenderer} = require('electron');
const fs = require('fs');
const path = require('path');
const os = require('os');

const LEDGER_DIR = path.join(os.homedir(), '.verity-harness', 'ledger');

contextBridge.exposeInMainWorld('verity', {
  getCfg: () => ipcRenderer.invoke('get-cfg'),
  saveCfg: (c) => ipcRenderer.send('save-cfg', c),
  setupDone: (c) => ipcRenderer.send('setup-done', c),
  onCfg: (cb) => ipcRenderer.on('cfg', (_e, c) => cb(c)),
  moveWindow: (dx, dy) => ipcRenderer.send('move-window', dx, dy),
  showMenu: () => ipcRenderer.send('show-menu'),
  // Tail the newest ledger file; return the latest event verdict so the mascot can react.
  latestLedgerEvent: () => {
    try {
      const files = fs.readdirSync(LEDGER_DIR).filter(f => f.endsWith('.jsonl'))
        .map(f => ({f, t: fs.statSync(path.join(LEDGER_DIR, f)).mtimeMs}))
        .sort((a, b) => b.t - a.t);
      if (!files.length) return null;
      const lines = fs.readFileSync(path.join(LEDGER_DIR, files[0].f), 'utf8').trim().split('\n');
      const last = lines[lines.length - 1];
      const ev = JSON.parse(last);
      return {verdict: ev.verdict || '', gate: ev.gate || '', ts: ev.ts || '', mtime: files[0].t};
    } catch { return null; }
  },
  // Is the VERITY proxy floor up? (a quick liveness signal the mascot shows as a dot)
  proxyUp: async () => {
    try {
      const r = await fetch('http://127.0.0.1:11500/health', {signal: AbortSignal.timeout(800)});
      return r.ok;
    } catch { return false; }
  },
  // The status dot doubles as a voice-mode TOGGLE: 'interactive' (real-time talk-back) vs
  // 'tldr' (one-way spoken read-outs). Persisted to ~/.verity-harness/voice-mode for the voice loop.
  setVoiceMode: (m) => ipcRenderer.send('set-voice-mode', m),
  getVoiceMode: () => ipcRenderer.invoke('get-voice-mode'),
});
