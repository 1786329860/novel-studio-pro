/**
 * electron-builder afterPack 钩子。
 *
 * 在打包完成后，自动将后端文件复制到 resources 目录。
 * 确保打包后的 EXE 可以找到后端文件。
 */

const path = require('path');
const fs = require('fs');

/**
 * afterPack 钩子函数。
 * @param {Object} context - electron-builder 打包上下文
 */
exports.default = async function afterPack(context) {
  const { appOutDir, electronPlatformName, packager } = context;

  // 只在 Windows 平台执行
  if (electronPlatformName !== 'win32') {
    return;
  }

  console.log('[afterPack] 正在检查后端文件...');

  // 检查后端文件是否已打包到 resources/backend
  const backendDir = path.join(appOutDir, 'resources', 'backend');
  const startScript = path.join(backendDir, 'start_backend.py');

  if (!fs.existsSync(startScript)) {
    console.warn('[afterPack] 警告: 后端启动脚本未找到:', startScript);
    console.warn('[afterPack] 请确保后端目录结构正确');
  } else {
    console.log('[afterPack] 后端文件检查通过');
  }

  // 检查 start_backend.bat 是否在 resources 目录
  const batFile = path.join(appOutDir, 'resources', 'start_backend.bat');
  if (!fs.existsSync(batFile)) {
    console.warn('[afterPack] 警告: start_backend.bat 未找到');
  }

  console.log('[afterPack] 打包后处理完成');
};
