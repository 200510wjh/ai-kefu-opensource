const {app, BrowserWindow, Menu, ipcMain, shell} = require('electron');
const {spawn} = require('child_process');
const path = require('path');

const DEFAULT_APP_URL = 'https://wjhai.cn/merchant-admin/';
const LOCAL_APP_URL = 'http://127.0.0.1:5173/';
let agentProcess = null;
const agentLogs = [];

function targetUrl() {
  return process.env.MERCHANT_APP_URL || DEFAULT_APP_URL;
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 1100,
    minHeight: 760,
    title: '商家AI增长工作台',
    backgroundColor: '#08111f',
    webPreferences: {
      preload: require('path').join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  win.loadURL(targetUrl());

  win.webContents.setWindowOpenHandler(({url}) => {
    shell.openExternal(url);
    return {action: 'deny'};
  });

  win.webContents.on('did-fail-load', () => {
    const escapedUrl = targetUrl().replace(/[&<>"']/g, (char) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    })[char]);
    win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(`<!doctype html>
      <html lang="zh-CN">
      <head>
        <meta charset="utf-8" />
        <title>商家AI增长工作台</title>
        <style>
          body{margin:0;min-height:100vh;display:grid;place-items:center;background:#08111f;color:#eef6ff;font-family:-apple-system,BlinkMacSystemFont,"Microsoft YaHei",sans-serif}
          main{width:min(720px,calc(100% - 48px));border:1px solid rgba(125,211,252,.28);border-radius:10px;padding:28px;background:rgba(15,23,42,.78)}
          h1{margin:0 0 12px;font-size:28px} p{line-height:1.7;color:#cbd5e1} code{color:#93c5fd}
        </style>
      </head>
      <body>
        <main>
          <h1>暂时连接不到工作台</h1>
          <p>桌面客户端已启动，但当前无法打开：<code>${escapedUrl}</code></p>
          <p>如果是本地测试，请先启动后端和前端，然后用环境变量启动：<code>MERCHANT_APP_URL=http://127.0.0.1:5173/ open 商家AI增长工作台.app</code></p>
          <p>如果是交付给客户，请确认服务器和域名已经恢复可访问。</p>
        </main>
      </body>
      </html>`)}`);
  });

  return win;
}

function repoRoot() {
  return path.resolve(__dirname, '..', '..');
}

function pushAgentLog(type, text) {
  const line = String(text || '').trim();
  if (!line) return;
  agentLogs.push({time: new Date().toISOString(), type, text: line});
  while (agentLogs.length > 200) agentLogs.shift();
}

function agentStatus() {
  return {
    running: Boolean(agentProcess && !agentProcess.killed),
    pid: agentProcess ? agentProcess.pid : null,
    logs: agentLogs.slice(-80)
  };
}

function startAgent(options = {}) {
  if (agentProcess && !agentProcess.killed) return agentStatus();
  const root = repoRoot();
  const python = process.env.MERCHANT_DESKTOP_PYTHON || process.env.PYTHON || 'python';
  const runner = path.join(root, 'scripts', 'desktop_agent_runner.py');
  const configPath = options.configPath || path.join(root, 'scripts', 'desktop_listener.config.example.json');
  const args = [runner, '--config', configPath];
  if (options.mode) args.push('--mode', options.mode);
  if (options.paste) args.push('--paste');
  if (options.send) args.push('--send');
  if (options.confirmSend) args.push('--confirm-send', options.confirmSend);
  const env = {...process.env};
  if (options.authToken) env.MERCHANT_DESKTOP_AUTH_TOKEN = options.authToken;
  if (options.apiBase) env.MERCHANT_DESKTOP_API_BASE = options.apiBase;
  agentProcess = spawn(python, args, {
    cwd: root,
    env,
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe']
  });
  pushAgentLog('system', `started desktop agent pid=${agentProcess.pid}`);
  agentProcess.stdout.on('data', (chunk) => pushAgentLog('stdout', chunk.toString('utf8')));
  agentProcess.stderr.on('data', (chunk) => pushAgentLog('stderr', chunk.toString('utf8')));
  agentProcess.on('exit', (code, signal) => {
    pushAgentLog('system', `desktop agent exited code=${code} signal=${signal || ''}`);
    agentProcess = null;
  });
  return agentStatus();
}

function stopAgent() {
  if (agentProcess && !agentProcess.killed) {
    pushAgentLog('system', 'stopping desktop agent');
    agentProcess.kill();
  }
  agentProcess = null;
  return agentStatus();
}

function buildMenu() {
  return Menu.buildFromTemplate([
    {
      label: '商家AI增长工作台',
      submenu: [
        {role: 'about'},
        {type: 'separator'},
        {role: 'quit', label: '退出'}
      ]
    },
    {
      label: '视图',
      submenu: [
        {role: 'reload', label: '刷新'},
        {role: 'toggleDevTools', label: '开发者工具'},
        {type: 'separator'},
        {role: 'resetZoom', label: '实际大小'},
        {role: 'zoomIn', label: '放大'},
        {role: 'zoomOut', label: '缩小'},
        {type: 'separator'},
        {role: 'togglefullscreen', label: '全屏'}
      ]
    }
  ]);
}

app.whenReady().then(() => {
  ipcMain.handle('desktop-agent:start', (_event, options) => startAgent(options || {}));
  ipcMain.handle('desktop-agent:stop', () => stopAgent());
  ipcMain.handle('desktop-agent:status', () => agentStatus());
  Menu.setApplicationMenu(buildMenu());
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
