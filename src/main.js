/**
 * AI客服 - 主进程
 * Electron入口，窗口管理
 */
const { app, BrowserWindow, ipcMain, Menu, Tray, nativeImage } = require('electron');
const path = require('path');
const axios = require('axios');

const API_BASE = 'http://localhost:8000';

// 创建主窗口
function createWindow() {
  const mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    backgroundColor: '#0a0e17',
    frame: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  // 加载前端页面
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  
  // 打开开发者工具
  if (process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools();
  }

  // 窗口关闭时隐藏到托盘
  mainWindow.on('close', (event) => {
    if (!app.isQuiting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });
}

// 创建系统托盘
function createTray() {
  // 创建透明图标用于托盘
  const icon = nativeImage.createEmpty();
  
  const tray = new Tray(icon);
  
  const contextMenu = Menu.buildFromTemplate([
    { label: '显示AI客服', click: () => mainWindow.show() },
    { type: 'separator' },
    { label: '抖音飞鸽', type: 'checkbox', checked: true },
    { label: '淘宝千牛', type: 'checkbox', checked: true },
    { type: 'separator' },
    { label: '退出', click: () => { app.isQuiting = true; app.quit(); } }
  ]);
  
  tray.setToolTip('AI客服 - 多平台智能客服系统');
  tray.setContextMenu(contextMenu);
  
  tray.on('click', () => {
    mainWindow.show();
  });
}

// 应用准备就绪
app.whenReady().then(() => {
  createWindow();
  createTray();
});

// 所有窗口关闭
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// IPC通信处理
ipcMain.handle('api-call', async (event, { method, url, data }) => {
  try {
    const fullUrl = url.startsWith('http') ? url : API_BASE + url;
    const response = await axios({
      method,
      url: fullUrl,
      data
    });
    return response.data;
  } catch (error) {
    return { code: 1, msg: error.message };
  }
});

ipcMain.handle('get-stats', async () => {
  try {
    const response = await axios.get(`${API_BASE}/api/stats`);
    return response.data;
  } catch (error) {
    return { code: 1, msg: '后端服务未启动' };
  }
});
