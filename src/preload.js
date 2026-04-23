/**
 * AI客服 - 预加载脚本
 * 在主进程和渲染进程之间建立安全的IPC通信
 */
const { contextBridge, ipcRenderer } = require('electron');

// 暴露安全的API给渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // 调用后端API
  apiCall: (method, url, data) => {
    return ipcRenderer.invoke('api-call', { method, url, data });
  },
  
  // 获取统计数据
  getStats: () => {
    return ipcRenderer.invoke('get-stats');
  },
  
  // 获取平台列表
  getPlatforms: () => {
    return ipcRenderer.invoke('get-platforms');
  },
  
  // 切换平台连接状态
  togglePlatform: (platformId, enabled) => {
    return ipcRenderer.invoke('toggle-platform', { platformId, enabled });
  },
  
  // 发送消息
  sendMessage: (message, platform) => {
    return ipcRenderer.invoke('send-message', { message, platform });
  },
  
  // 监听后端消息推送
  onMessage: (callback) => {
    ipcRenderer.on('new-message', (event, data) => callback(data));
  },
  
  // 监听平台状态变化
  onPlatformStatus: (callback) => {
    ipcRenderer.on('platform-status', (event, data) => callback(data));
  },
  
  // 移除监听器
  removeAllListeners: (channel) => {
    ipcRenderer.removeAllListeners(channel);
  },
  
  // 获取应用版本
  getVersion: () => {
    return ipcRenderer.invoke('get-version');
  },
  
  // 打开外部链接
  openExternal: (url) => {
    return ipcRenderer.invoke('open-external', url);
  }
});

// 通知主进程渲染进程已就绪
console.log('[Preload] AI客服预加载脚本已加载');
