const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('novelStudio', {
  getVersion: () => ipcRenderer.invoke('app:getVersion'),
  openExternal: (url) => ipcRenderer.invoke('app:openExternal', url)
});
