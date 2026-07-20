const {contextBridge, ipcRenderer} = require('electron');

contextBridge.exposeInMainWorld('merchantDesktop', {
  platform: process.platform,
  version: process.versions.electron,
  desktopAgent: {
    start: (options) => ipcRenderer.invoke('desktop-agent:start', options || {}),
    stop: () => ipcRenderer.invoke('desktop-agent:stop'),
    status: () => ipcRenderer.invoke('desktop-agent:status')
  }
});
