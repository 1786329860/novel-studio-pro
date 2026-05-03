const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');

// 后端进程管理
const backendManager = require('./tools/start_backend');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1540,
    height: 960,
    minWidth: 1280,
    minHeight: 780,
    title: 'Novel Studio Pro',
    backgroundColor: '#0f172a',
    show: false,
    autoHideMenuBar: true,
    titleBarStyle: 'hiddenInset',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });

  // 先显示加载页面
  mainWindow.loadFile('loading.html');
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });
}

/**
 * 切换到主页面。
 * 后端启动成功后调用。
 */
function switchToMainPage() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.loadFile('index.html');
  }
}

/**
 * 显示后端启动失败页面。
 * @param {string} errorMessage - 错误信息
 */
function showStartupError(errorMessage) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.loadFile('loading.html').then(() => {
      // 加载完成后发送错误状态
      mainWindow.webContents.send('backend-status', 'error');
      mainWindow.webContents.send('backend-log', `启动失败: ${errorMessage}`);
    });
  }
}

// 设置后端状态变化回调
backendManager.onBackendStatusChange((status) => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('backend-status', status);
  }
});

// 设置后端日志回调
backendManager.onBackendLog((logEntry) => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('backend-log', logEntry);
  }
});

app.whenReady().then(async () => {
  createWindow();

  // 启动后端进程
  const backendStarted = await backendManager.startBackend({
    maxWait: 30000, // 最多等待 30 秒
  });

  if (backendStarted) {
    // 后端启动成功，切换到主页面
    switchToMainPage();
  }
  // 如果启动失败，loading.html 已经通过回调显示了错误状态

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  // 终止后端进程
  backendManager.stopBackend();
  if (process.platform !== 'darwin') app.quit();
});

// 在应用退出前确保后端进程被终止
app.on('before-quit', () => {
  backendManager.stopBackend();
});

// IPC 处理程序
ipcMain.handle('app:getVersion', () => app.getVersion());

ipcMain.handle('app:openExternal', async (_event, url) => {
  if (typeof url === 'string' && /^https?:\/\//.test(url)) {
    await shell.openExternal(url);
  }
});

// 后端状态查询 IPC
ipcMain.handle('backend:getStatus', () => {
  return backendManager.getBackendStatus();
});

ipcMain.handle('backend:getLogs', () => {
  return backendManager.getBackendLogs();
});

ipcMain.handle('backend:restart', async () => {
  backendManager.stopBackend();
  // 显示加载页面
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.loadFile('loading.html');
  }
  const started = await backendManager.startBackend({ maxWait: 30000 });
  if (started) {
    switchToMainPage();
  }
  return started;
});
