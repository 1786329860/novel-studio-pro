/**
 * 后端进程管理模块。
 *
 * 在 Electron 主进程中启动后端 Python 进程，
 * 自动检测 Python 路径，管理后端生命周期。
 *
 * 功能:
 * - 使用 child_process.spawn 启动 start_backend.py
 * - 自动检测 Python 路径（Windows: python, python3, py）
 * - 后端进程随 Electron 退出自动终止
 * - 启动失败时显示错误对话框
 * - 启动成功后等待健康检查通过再加载前端
 */

const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const { app, dialog } = require('electron');

// 后端进程引用
let backendProcess = null;

// 后端状态
let backendStatus = 'stopped'; // 'starting' | 'ready' | 'error' | 'stopped'
let backendLogs = [];
let backendPort = 8765;

// 日志回调（用于向渲染进程推送状态）
let onStatusChange = null;
let onLog = null;

/**
 * 设置状态变化回调。
 * @param {Function} callback - 状态变化时的回调函数
 */
function onBackendStatusChange(callback) {
  onStatusChange = callback;
}

/**
 * 设置日志回调。
 * @param {Function} callback - 新日志时的回调函数
 */
function onBackendLog(callback) {
  onLog = callback;
}

/**
 * 获取后端当前状态。
 * @returns {string} 后端状态
 */
function getBackendStatus() {
  return backendStatus;
}

/**
 * 获取后端日志。
 * @returns {string[]} 日志列表
 */
function getBackendLogs() {
  return [...backendLogs];
}

/**
 * 添加日志。
 * @param {string} message - 日志消息
 */
function addLog(message) {
  const timestamp = new Date().toLocaleTimeString('zh-CN');
  const logEntry = `[${timestamp}] ${message}`;
  backendLogs.push(logEntry);
  // 限制日志数量，避免内存泄漏
  if (backendLogs.length > 200) {
    backendLogs = backendLogs.slice(-100);
  }
  if (onLog) {
    onLog(logEntry);
  }
}

/**
 * 设置后端状态。
 * @param {string} status - 新状态
 */
function setStatus(status) {
  backendStatus = status;
  if (onStatusChange) {
    onStatusChange(status);
  }
}

/**
 * 查找 Python 可执行文件路径。
 * 按优先级尝试多个可能的 Python 命令。
 * @returns {Promise<string|null>} Python 路径，找不到返回 null
 */
async function findPython() {
  const candidates = process.platform === 'win32'
    ? ['python', 'python3', 'py', 'python.exe', 'python3.exe', 'py.exe']
    : ['python3', 'python'];

  for (const cmd of candidates) {
    try {
      const result = await new Promise((resolve, reject) => {
        const proc = spawn(cmd, ['--version'], {
          shell: true,
          windowsHide: true,
        });
        let output = '';
        proc.stdout.on('data', (data) => { output += data.toString(); });
        proc.stderr.on('data', (data) => { output += data.toString(); });
        proc.on('close', (code) => {
          resolve({ code, output });
        });
        proc.on('error', reject);
      });

      if (result.code === 0 && output.includes('Python')) {
        addLog(`找到 Python: ${cmd} (${output.trim()})`);
        return cmd;
      }
    } catch {
      // 继续尝试下一个
    }
  }

  return null;
}

/**
 * 健康检查：检测后端是否已启动。
 * @param {number} port - 后端端口
 * @param {number} timeout - 超时时间（毫秒）
 * @returns {Promise<boolean>} 是否健康
 */
async function healthCheck(port, timeout = 5000) {
  const url = `http://127.0.0.1:${port}/api/health`;
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      req.destroy();
      resolve(false);
    }, timeout);

    const req = http.get(url, (res) => {
      clearTimeout(timer);
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        resolve(res.statusCode === 200);
      });
    });

    req.on('error', () => {
      clearTimeout(timer);
      resolve(false);
    });
  });
}

/**
 * 启动后端进程。
 * @param {Object} options - 启动选项
 * @param {string} [options.backendDir] - 后端目录路径
 * @param {number} [options.port=8765] - 后端端口
 * @param {number} [options.maxWait=30000] - 最大等待时间（毫秒）
 * @returns {Promise<boolean>} 是否启动成功
 */
async function startBackend(options = {}) {
  const backendDir = options.backendDir || path.join(__dirname, '..', 'backend');
  backendPort = options.port || 8765;
  const maxWait = options.maxWait || 30000;

  // 如果后端已在运行，先检查健康状态
  if (backendProcess) {
    addLog('后端进程已存在，检查健康状态...');
    const healthy = await healthCheck(backendPort, 3000);
    if (healthy) {
      setStatus('ready');
      addLog('后端已在运行且健康');
      return true;
    }
    // 不健康，终止旧进程
    stopBackend();
  }

  setStatus('starting');
  addLog('正在启动后端...');

  // 查找 Python
  const pythonCmd = await findPython();
  if (!pythonCmd) {
    setStatus('error');
    addLog('错误: 未找到 Python 环境。请安装 Python 3.8+ 并确保在 PATH 中。');
    dialog.showErrorBox(
      '启动失败',
      '未找到 Python 环境。\n\n请安装 Python 3.8+ 并确保已添加到系统 PATH 环境变量中。'
    );
    return false;
  }

  // 确定启动脚本路径
  const startScript = path.join(backendDir, 'start_backend.py');
  const startBat = path.join(__dirname, '..', 'resources', 'start_backend.bat');

  let spawnArgs;
  let spawnCmd;

  if (process.platform === 'win32') {
    // Windows: 优先使用 bat 脚本
    if (require('fs').existsSync(startBat)) {
      spawnCmd = startBat;
      spawnArgs = [];
    } else {
      spawnCmd = pythonCmd;
      spawnArgs = [startScript];
    }
  } else {
    spawnCmd = pythonCmd;
    spawnArgs = [startScript];
  }

  addLog(`启动命令: ${spawnCmd} ${spawnArgs.join(' ')}`);
  addLog(`工作目录: ${backendDir}`);

  try {
    backendProcess = spawn(spawnCmd, spawnArgs, {
      cwd: backendDir,
      shell: true,
      windowsHide: true,
      env: {
        ...process.env,
        APP_HOST: '127.0.0.1',
        APP_PORT: String(backendPort),
        DEBUG: 'false',
      },
    });

    // 监听后端输出
    backendProcess.stdout.on('data', (data) => {
      const message = data.toString().trim();
      addLog(message);
    });

    backendProcess.stderr.on('data', (data) => {
      const message = data.toString().trim();
      addLog(`[STDERR] ${message}`);
    });

    backendProcess.on('error', (err) => {
      setStatus('error');
      addLog(`后端进程错误: ${err.message}`);
    });

    backendProcess.on('close', (code) => {
      addLog(`后端进程退出，退出码: ${code}`);
      if (backendStatus === 'starting') {
        setStatus('error');
        dialog.showErrorBox(
          '启动失败',
          `后端进程异常退出（退出码: ${code}）。\n\n请检查 Python 环境和依赖是否正确安装。`
        );
      } else if (backendStatus === 'ready') {
        setStatus('stopped');
      }
      backendProcess = null;
    });

    // 等待健康检查通过
    addLog(`等待后端启动（最多 ${maxWait / 1000} 秒）...`);
    const startTime = Date.now();
    const checkInterval = 1000; // 每秒检查一次

    while (Date.now() - startTime < maxWait) {
      await new Promise((resolve) => setTimeout(resolve, checkInterval));
      const healthy = await healthCheck(backendPort, 2000);
      if (healthy) {
        setStatus('ready');
        addLog(`后端启动成功！地址: http://127.0.0.1:${backendPort}`);
        return true;
      }
    }

    // 超时
    setStatus('error');
    addLog(`后端启动超时（${maxWait / 1000} 秒）`);
    dialog.showErrorBox(
      '启动超时',
      `后端在 ${maxWait / 1000} 秒内未完成启动。\n\n可能原因:\n- Python 依赖未安装（请运行 pip install -r requirements.txt）\n- 端口 ${backendPort} 被占用\n- Python 版本不兼容`
    );
    return false;

  } catch (err) {
    setStatus('error');
    addLog(`启动异常: ${err.message}`);
    dialog.showErrorBox('启动失败', `后端启动异常: ${err.message}`);
    return false;
  }
}

/**
 * 停止后端进程。
 */
function stopBackend() {
  if (backendProcess) {
    addLog('正在停止后端进程...');
    try {
      if (process.platform === 'win32') {
        // Windows: 使用 taskkill 终止进程树
        spawn('taskkill', ['/pid', String(backendProcess.pid), '/f', '/t'], {
          shell: true,
          windowsHide: true,
        });
      } else {
        backendProcess.kill('SIGTERM');
      }
    } catch {
      // 忽略终止错误
    }
    backendProcess = null;
    setStatus('stopped');
    addLog('后端进程已停止');
  }
}

module.exports = {
  startBackend,
  stopBackend,
  getBackendStatus,
  getBackendLogs,
  onBackendStatusChange,
  onBackendLog,
};
