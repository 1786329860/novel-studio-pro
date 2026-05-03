/**
 * renderer.js 补丁 - 任务 1 & 任务 2 前端改造
 *
 * 本文件包含需要在 renderer.js 中集成的代码片段。
 * 由于 renderer.js 不在当前项目中，这里提供完整的补丁代码，
 * 需要手动集成到前端的 renderer.js 中。
 *
 * 集成方式:
 * 1. 将 generateNextChapterWithTask 函数替换原有的 generateNextChapter action
 * 2. 将 analyzeEditAction 和 confirmWithEditCheck 添加到 actions 中
 * 3. 在写作页面模板中添加进度条和修改分析 UI
 */

// ======================================================================
// 任务 2: 任务队列 - generateNextChapter 改造
// ======================================================================

/**
 * 使用任务队列模式生成下一章
 * 提交任务后显示进度条，每 2 秒轮询任务状态
 */
async function generateNextChapterWithTask(projectId, options = {}) {
  const { api } = await import('./api.js');
  const { getState, updateState } = await import('./store.js');

  try {
    // 提交任务
    const result = await api.submitGenerateTask(projectId, options);

    if (!result.taskId) {
      // 向后兼容: 如果直接返回了 chapter（非任务模式）
      if (result.chapter) {
        updateState((state) => {
          state.pendingChapter = result.chapter;
          state.activeRoute = 'writing';
          return state;
        });
        return result;
      }
      throw new Error('未能提交生成任务');
    }

    const taskId = result.taskId;

    // 更新状态: 显示进度条
    updateState((state) => {
      state.generating = true;
      state.taskProgress = {
        taskId,
        status: 'pending',
        progress: 0,
        currentStep: '任务已提交，等待执行...',
      };
      return state;
    });

    // 轮询任务状态
    const pollInterval = 2000; // 2 秒
    let pollCount = 0;
    const maxPolls = 300; // 最多轮询 10 分钟

    const pollResult = await new Promise((resolve, reject) => {
      const timer = setInterval(async () => {
        pollCount++;

        try {
          const status = await api.getTaskStatus(taskId);

          // 更新进度
          updateState((state) => {
            state.taskProgress = {
              taskId,
              status: status.status,
              progress: status.progress || 0,
              currentStep: status.current_step || '',
              error: status.error || '',
            };
            return state;
          });

          if (status.status === 'done') {
            clearInterval(timer);
            // 任务完成，获取章节数据
            if (status.result && status.result.chapter) {
              updateState((state) => {
                state.pendingChapter = status.result.chapter;
                state.generating = false;
                state.taskProgress = null;
                state.activeRoute = 'writing';
                return state;
              });
              resolve(status.result);
            } else {
              // 章节数据可能已通过 store 更新，重新获取项目
              updateState((state) => {
                state.generating = false;
                state.taskProgress = null;
                return state;
              });
              resolve(status);
            }
          } else if (status.status === 'failed') {
            clearInterval(timer);
            updateState((state) => {
              state.generating = false;
              state.taskProgress = null;
              return state;
            });
            reject(new Error(status.error || '章节生成失败'));
          } else if (status.status === 'cancelled') {
            clearInterval(timer);
            updateState((state) => {
              state.generating = false;
              state.taskProgress = null;
              return state;
            });
            reject(new Error('任务已取消'));
          }
        } catch (pollError) {
          // 轮询出错，继续尝试
          console.warn('轮询任务状态出错:', pollError);
        }

        if (pollCount >= maxPolls) {
          clearInterval(timer);
          updateState((state) => {
            state.generating = false;
            state.taskProgress = null;
            return state;
          });
          reject(new Error('任务超时'));
        }
      }, pollInterval);
    });

    return pollResult;
  } catch (error) {
    updateState((state) => {
      state.generating = false;
      state.taskProgress = null;
      return state;
    });
    throw error;
  }
}

/**
 * 取消正在进行的生成任务
 */
async function cancelGenerateTask(taskId) {
  const { api } = await import('./api.js');
  const { updateState } = await import('./store.js');

  try {
    await api.cancelTask(taskId);
    updateState((state) => {
      state.generating = false;
      state.taskProgress = null;
      return state;
    });
  } catch (error) {
    console.error('取消任务失败:', error);
    throw error;
  }
}


// ======================================================================
// 任务 1: 用户修改回灌 - 分析修改 & 确认入库
// ======================================================================

/**
 * 分析用户对章节正文的修改
 * 当检测到正文被修改时调用
 */
async function analyzeEditAction(projectId, chapterId, originalText, modifiedText) {
  const { api } = await import('./api.js');

  const result = await api.analyzeEdit(projectId, chapterId, originalText, modifiedText);

  return result.analysis || result;
}

/**
 * 带修改检查的确认入库
 * 如果检测到正文被修改，先分析修改，显示结果让用户确认
 * 如果用户确认，再执行确认入库
 */
async function confirmWithEditCheck(projectId, chapterId) {
  const { getState, updateState } = await import('./store.js');
  const { api } = await import('./api.js');

  const state = getState();
  const pendingChapter = state.pendingChapter;

  if (!pendingChapter) {
    throw new Error('没有待确认的章节');
  }

  // 检查正文是否被修改
  const originalText = pendingChapter._originalText || '';
  const currentText = pendingChapter.text || '';

  if (originalText && currentText && originalText !== currentText) {
    // 检测到修改，先分析
    updateState((state) => {
      state.editAnalysis = {
        analyzing: true,
        result: null,
        error: null,
      };
      return state;
    });

    try {
      const analysis = await analyzeEditAction(
        projectId,
        chapterId,
        originalText,
        currentText
      );

      updateState((state) => {
        state.editAnalysis = {
          analyzing: false,
          result: analysis,
          error: null,
        };
        return state;
      });

      // 返回分析结果，让 UI 展示给用户确认
      // 用户确认后再调用 confirmChapter
      return {
        hasEdits: true,
        analysis,
        message: analysis.summary || '检测到正文修改，请查看分析结果后确认入库。',
      };
    } catch (error) {
      updateState((state) => {
        state.editAnalysis = {
          analyzing: false,
          result: null,
          error: error.message,
        };
        return state;
      });

      // 分析失败，仍然允许直接确认
      return {
        hasEdits: true,
        analysis: null,
        error: error.message,
        message: '修改分析失败，但仍可直接确认入库。',
      };
    }
  }

  // 没有修改，直接确认
  return api.confirmChapter(projectId, chapterId);
}


// ======================================================================
// 写作页面 UI 模板补丁
// ======================================================================

/**
 * 进度条组件 HTML
 * 在写作页面中，当 state.generating 为 true 时显示
 */
const taskProgressBarHTML = `
<div class="task-progress-bar" id="taskProgressBar">
  <div class="task-progress-header">
    <span class="task-progress-step" id="taskProgressStep">正在生成章节...</span>
    <span class="task-progress-percent" id="taskProgressPercent">0%</span>
  </div>
  <div class="task-progress-track">
    <div class="task-progress-fill" id="taskProgressFill" style="width: 0%"></div>
  </div>
  <button class="task-cancel-btn" id="taskCancelBtn" onclick="handleCancelTask()">取消</button>
</div>
`;

/**
 * 修改分析结果组件 HTML
 * 当检测到正文被修改并完成分析后显示
 */
const editAnalysisHTML = `
<div class="edit-analysis-panel" id="editAnalysisPanel">
  <h4>正文修改分析</h4>
  <p class="edit-analysis-summary" id="editAnalysisSummary"></p>
  <div class="edit-analysis-details" id="editAnalysisDetails">
    <h5>状态变化预览</h5>
    <div id="editDeltaPreview"></div>
  </div>
  <div class="edit-analysis-actions">
    <button class="btn-confirm-edit" onclick="handleConfirmWithEdit()">确认入库（应用修改）</button>
    <button class="btn-confirm-original" onclick="handleConfirmOriginal()">忽略修改，直接入库</button>
  </div>
</div>
`;

/**
 * "分析修改"按钮 HTML
 * 当检测到 pendingChapter 的 text 与 _originalText 不同时显示
 */
const analyzeEditButtonHTML = `
<button class="btn-analyze-edit" id="btnAnalyzeEdit" onclick="handleAnalyzeEdit()">
  检测到正文修改 - 点击分析修改内容
</button>
`;


// ======================================================================
// 导出
// ======================================================================

export {
  generateNextChapterWithTask,
  cancelGenerateTask,
  analyzeEditAction,
  confirmWithEditCheck,
  taskProgressBarHTML,
  editAnalysisHTML,
  analyzeEditButtonHTML,
};
