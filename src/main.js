/**
 * AI客服 - 主进程
 * Electron入口，窗口管理，IPC通信中枢
 */
const { app, BrowserWindow, ipcMain, Menu, Tray, nativeImage, dialog } = require('electron');
const path = require('path');
const axios = require('axios');

const API_BASE = process.env.API_BASE || 'http://localhost:8000';

// 平台连接状态
const platformStatus = {
  dy_feige: { enabled: true, connected: false },
  tb_qianiu: { enabled: true, connected: false },
  douyin_web: { enabled: true, connected: false }
};

let mainWindow = null;
let tray = null;

// 创建主窗口
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    backgroundColor: '#0a0e17',
    frame: true,
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  // 加载前端页面
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  
  // 窗口准备好后显示
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });
  
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
  
  // 窗口关闭时清空引用
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// 创建系统托盘
function createTray() {
  // 创建一个简单的图标（16x16蓝色方块）
  const iconSize = 16;
  const iconBuffer = Buffer.alloc(iconSize * iconSize * 4);
  for (let i = 0; i < iconSize * iconSize; i++) {
    iconBuffer[i * 4] = 0;       // R
    iconBuffer[i * 4 + 1] = 240; // G  
    iconBuffer[i * 4 + 2] = 255; // B
    iconBuffer[i * 4 + 3] = 255; // A
  }
  const icon = nativeImage.createFromBuffer(iconBuffer, { width: iconSize, height: iconSize });
  
  tray = new Tray(icon);
  updateTrayMenu();
  
  tray.setToolTip('AI客服 - 多平台智能客服系统');
  
  tray.on('click', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.hide();
      } else {
        mainWindow.show();
      }
    }
  });
}

// 更新托盘菜单
function updateTrayMenu() {
  const template = [
    { 
      label: '显示AI客服', 
      click: () => mainWindow && mainWindow.show() 
    },
    { type: 'separator' },
    { 
      label: '🐦 抖音飞鸽', 
      type: 'checkbox', 
      checked: platformStatus.dy_feige.enabled,
      click: (menuItem) => {
        platformStatus.dy_feige.enabled = menuItem.checked;
        broadcastPlatformStatus();
      }
    },
    { 
      label: '🐱 淘宝千牛', 
      type: 'checkbox', 
      checked: platformStatus.tb_qianiu.enabled,
      click: (menuItem) => {
        platformStatus.tb_qianiu.enabled = menuItem.checked;
        broadcastPlatformStatus();
      }
    },
    { 
      label: '🏪 抖店网页', 
      type: 'checkbox', 
      checked: platformStatus.douyin_web.enabled,
      click: (menuItem) => {
        platformStatus.douyin_web.enabled = menuItem.checked;
        broadcastPlatformStatus();
      }
    },
    { type: 'separator' },
    { 
      label: '🔄 检查更新', 
      click: () => {
        dialog.showMessageBox({
          type: 'info',
          title: 'AI客服',
          message: '当前版本: 1.0.0\n已是最新版本'
        });
      }
    },
    { type: 'separator' },
    { 
      label: '退出', 
      click: () => { 
        app.isQuiting = true; 
        app.quit(); 
      } 
    }
  ];
  
  tray.setContextMenu(Menu.buildFromTemplate(template));
}

// 向渲染进程广播平台状态
function broadcastPlatformStatus() {
  if (mainWindow && mainWindow.webContents) {
    mainWindow.webContents.send('platform-status', platformStatus);
  }
}

// 应用准备就绪
app.whenReady().then(() => {
  createWindow();
  createTray();
  checkBackendConnection();
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

app.on('before-quit', () => {
  app.isQuiting = true;
});

// 检查后端连接状态
async function checkBackendConnection() {
  try {
    const response = await axios.get(`${API_BASE}/health`, { timeout: 5000 });
    if (response.status === 200) {
      platformStatus.dy_feige.connected = true;
      platformStatus.tb_qianiu.connected = true;
      platformStatus.douyin_web.connected = true;
      broadcastPlatformStatus();
    }
  } catch (error) {
    console.log('[主进程] 后端服务未连接:', error.message);
  }
}

// 每30秒检查一次后端连接
setInterval(checkBackendConnection, 30000);

// ============== IPC通信处理 ==============

// 通用API调用
ipcMain.handle('api-call', async (event, { method, url, data }) => {
  try {
    const fullUrl = url.startsWith('http') ? url : API_BASE + url;
    const response = await axios({
      method: method || 'GET',
      url: fullUrl,
      data,
      timeout: 30000
    });
    return response.data;
  } catch (error) {
    console.error('[API调用失败]', error.message);
    return { code: 1, msg: error.message };
  }
});

// 获取统计数据
ipcMain.handle('get-stats', async () => {
  try {
    const response = await axios.get(`${API_BASE}/api/stats`, { timeout: 5000 });
    return response.data;
  } catch (error) {
    return { code: 1, msg: '后端服务未启动' };
  }
});

// 获取平台列表
ipcMain.handle('get-platforms', async () => {
  try {
    const response = await axios.get(`${API_BASE}/api/platforms`, { timeout: 5000 });
    return response.data;
  } catch (error) {
    // 后端未启动时返回本地状态
    return {
      code: 0,
      data: {
        platforms: [
          { id: 'dy_feige', name: '抖音飞鸽', status: platformStatus.dy_feige.connected ? 'active' : 'inactive' },
          { id: 'tb_qianiu', name: '淘宝千牛', status: platformStatus.tb_qianiu.connected ? 'active' : 'inactive' },
          { id: 'douyin_web', name: '抖店网页', status: platformStatus.douyin_web.connected ? 'active' : 'inactive' }
        ]
      }
    };
  }
});

// 切换平台开关
ipcMain.handle('toggle-platform', (event, { platformId, enabled }) => {
  if (platformStatus[platformId]) {
    platformStatus[platformId].enabled = enabled;
    updateTrayMenu();
    return { code: 0, msg: 'success' };
  }
  return { code: 1, msg: '平台不存在' };
});

// 发送消息
ipcMain.handle('send-message', async (event, { message, platform }) => {
  try {
    const response = await axios.post(`${API_BASE}/api/chat`, {
      message,
      user_id: 'manual',
      platform
    }, { timeout: 30000 });
    return response.data;
  } catch (error) {
    return { code: 1, msg: error.message };
  }
});

// 获取版本
ipcMain.handle('get-version', () => {
  return {
    version: '1.0.0',
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    node: process.versions.node
  };
});

// 打开外部链接
ipcMain.handle('open-external', (event, url) => {
  require('electron').shell.openExternal(url);
});

// 获取平台状态
ipcMain.handle('get-platform-status', () => {
  return platformStatus;
});
