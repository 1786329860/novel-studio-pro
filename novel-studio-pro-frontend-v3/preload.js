const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('novelStudio', {
  getVersion: () => ipcRenderer.invoke('app:getVersion'),
  openExternal: (url) => ipcRenderer.invoke('app:openExternal'),

  // 后端状态相关 API
  backendStatus: {
    /** 获取后端当前状态: 'starting' | 'ready' | 'error' | 'stopped' */
    getStatus: () => ipcRenderer.invoke('backend:getStatus'),
    /** 获取后端日志列表 */
    getLogs: () => ipcRenderer.invoke('backend:getLogs'),
    /** 重启后端 */
    restart: () => ipcRenderer.invoke('backend:restart'),
    /** 监听后端状态变化 */
    onStatusChange: (callback) => {
      ipcRenderer.on('backend-status', (_event, status) => callback(status));
    },
    /** 监听后端日志 */
    onLog: (callback) => {
      ipcRenderer.on('backend-log', (_event, logEntry) => callback(logEntry));
    },
    /** 移除状态变化监听 */
    offStatusChange: () => {
      ipcRenderer.removeAllListeners('backend-status');
    },
    /** 移除日志监听 */
    offLog: () => {
      ipcRenderer.removeAllListeners('backend-log');
    },
  },
});
