import { getState, updateState } from './store.js';
import { mockApi } from './mock.js';

function getSettings() {
  return getState().settings;
}

async function request(path, options = {}) {
  const settings = getSettings();
  const baseUrl = settings.backendBaseUrl.replace(/\/$/, '');
  const url = `${baseUrl}${path}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), settings.requestTimeoutMs);

  try {
    const response = await fetch(url, {
      method: options.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {})
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal
    });

    const text = await response.text();
    const data = text ? JSON.parse(text) : {};

    if (!response.ok) {
      const message = data.detail || data.message || `HTTP ${response.status}`;
      throw new Error(message);
    }

    return data;
  } finally {
    clearTimeout(timeoutId);
  }
}

async function callWithFallback(mockFn, remoteFn) {
  const settings = getSettings();
  if (settings.mockMode) return mockFn();

  let lastError = null;
  const times = Math.max(1, Number(settings.retryTimes || 1) + 1);
  for (let index = 0; index < times; index += 1) {
    try {
      return await remoteFn();
    } catch (error) {
      lastError = error;
      await new Promise((resolve) => setTimeout(resolve, 500 + index * 900));
    }
  }
  throw lastError;
}

function upsertProject(project) {
  updateState((state) => {
    const exists = state.projects.some((item) => item.id === project.id);
    state.projects = exists
      ? state.projects.map((item) => (item.id === project.id ? project : item))
      : [project, ...state.projects];
    state.currentProjectId = project.id;
    return state;
  });
}

export const api = {
  async createProject(payload) {
    return callWithFallback(
      () => mockApi.createProject(payload),
      async () => {
        const data = await request('/api/projects', { method: 'POST', body: payload });
        if (data.project) {
          updateState((state) => {
            state.projects = [data.project, ...state.projects.filter((item) => item.id !== data.project.id)];
            state.currentProjectId = data.project.id;
            state.activeRoute = 'blueprint';
            state.pendingChapter = null;
            return state;
          });
        }
        return data;
      }
    );
  },

  async buildProject(projectId) {
    return callWithFallback(
      () => mockApi.buildProject(projectId),
      async () => {
        const data = await request(`/api/projects/${projectId}/build`, { method: 'POST' });
        if (data.project) upsertProject(data.project);
        return data;
      }
    );
  },

  async regenerateBlueprint(projectId) {
    return callWithFallback(
      () => mockApi.regenerateBlueprint(projectId),
      async () => {
        const data = await request(`/api/projects/${projectId}/blueprint/regenerate`, { method: 'POST' });
        if (data.project) upsertProject(data.project);
        return data;
      }
    );
  },

  async generateNextChapter(projectId, options = {}) {
    const settings = getSettings();
    const body = {
      mode: options.mode || settings.generationMode,
      qualityThreshold: settings.qualityThreshold,
      maxInputTokens: settings.maxInputTokens,
      maxOutputTokens: settings.maxOutputTokens,
      userInstruction: options.userInstruction || ''
    };
    return callWithFallback(
      () => mockApi.generateNextChapter(projectId, body),
      async () => {
        const data = await request(`/api/projects/${projectId}/chapters/generate-next`, { method: 'POST', body });
        if (data.chapter) {
          updateState((state) => {
            state.pendingChapter = data.chapter;
            state.lastJob = {
              type: 'generate_next_chapter',
              status: 'done',
              projectId,
              finishedAt: new Date().toISOString(),
              mode: body.mode
            };
            state.activeRoute = 'writing';
            return state;
          });
        }
        return data;
      }
    );
  },

  /**
   * 流式生成下一章（SSE）。
   * Mock 模式下直接调用 mock 并模拟事件回调。
   * 远程模式下使用 SSE 流式接收。
   */
  async generateNextChapterStream(projectId, options = {}, onEvent = () => {}) {
    const settings = getSettings();

    // Mock 模式：直接调用 mock 并模拟事件
    if (settings.mockMode) {
      onEvent({ type: 'agent_start', agent: 'MemoryAgent' });
      await new Promise((r) => setTimeout(r, 300));
      onEvent({ type: 'agent_done', agent: 'MemoryAgent' });

      onEvent({ type: 'agent_start', agent: 'ConstraintAgent' });
      await new Promise((r) => setTimeout(r, 200));
      onEvent({ type: 'agent_done', agent: 'ConstraintAgent' });

      onEvent({ type: 'agent_start', agent: 'DirectorAgent' });
      await new Promise((r) => setTimeout(r, 300));
      onEvent({ type: 'agent_done', agent: 'DirectorAgent' });

      onEvent({ type: 'agent_start', agent: 'WriterAgent' });
      const result = await mockApi.generateNextChapter(projectId, {});
      onEvent({ type: 'agent_done', agent: 'WriterAgent' });

      onEvent({ type: 'agent_start', agent: 'ReviewAgent' });
      await new Promise((r) => setTimeout(r, 200));
      onEvent({ type: 'agent_done', agent: 'ReviewAgent' });

      if (result && result.chapter) {
        onEvent({ type: 'chapter_done', chapter: result.chapter });
      }
      return result ? result.chapter : null;
    }

    // 远程模式：SSE 流式
    const baseUrl = settings.backendBaseUrl.replace(/\/$/, '');
    const url = `${baseUrl}/api/projects/${projectId}/chapters/generate-next`;
    const body = {
      mode: options.mode || settings.generationMode,
      qualityThreshold: settings.qualityThreshold,
      maxInputTokens: settings.maxInputTokens,
      maxOutputTokens: settings.maxOutputTokens,
      userInstruction: options.userInstruction || ''
    };

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
      },
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      const text = await response.text();
      const data = text ? JSON.parse(text) : {};
      throw new Error(data.detail || data.message || `HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalChapter = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith('data: ')) continue;
        const dataStr = trimmed.slice(6);
        if (!dataStr) continue;

        try {
          const event = JSON.parse(dataStr);
          onEvent(event);

          if (event.type === 'chapter_done') {
            finalChapter = event.chapter;
          }
        } catch (e) {
          // 忽略解析失败的行
        }
      }
    }

    return finalChapter;
  },

  /**
   * 提交章节生成任务（任务队列模式）
   */
  async submitGenerateTask(projectId, options = {}) {
    const settings = getSettings();
    const body = {
      mode: options.mode || settings.generationMode,
      qualityThreshold: settings.qualityThreshold,
      maxInputTokens: settings.maxInputTokens,
      maxOutputTokens: settings.maxOutputTokens,
      userInstruction: options.userInstruction || ''
    };
    return callWithFallback(
      () => mockApi.generateNextChapter(projectId, body),
      async () => {
        const data = await request(`/api/projects/${projectId}/chapters/generate-next`, { method: 'POST', body });
        if (data.taskId) {
          updateState((state) => {
            state.currentTaskId = data.taskId;
            state.lastJob = {
              type: 'generate_next_chapter',
              status: 'pending',
              projectId,
              taskId: data.taskId,
              startedAt: new Date().toISOString(),
              mode: body.mode
            };
            return state;
          });
        }
        if (data.chapter) {
          updateState((state) => {
            state.pendingChapter = data.chapter;
            state.lastJob = {
              type: 'generate_next_chapter',
              status: 'done',
              projectId,
              finishedAt: new Date().toISOString(),
              mode: body.mode
            };
            state.activeRoute = 'writing';
            return state;
          });
        }
        return data;
      }
    );
  },

  /**
   * 获取任务状态和进度
   */
  async getTaskStatus(taskId) {
    return request(`/api/projects/tasks/${taskId}`);
  },

  /**
   * 列出所有任务
   */
  async listTasks() {
    return request('/api/projects/tasks');
  },

  /**
   * 取消任务
   */
  async cancelTask(taskId) {
    return request(`/api/projects/tasks/${taskId}/cancel`, { method: 'POST' });
  },

  /**
   * 分析用户对章节正文的修改
   */
  async analyzeEdit(projectId, chapterId, originalText, modifiedText) {
    return request(`/api/projects/${projectId}/chapters/${chapterId}/analyze-edit`, {
      method: 'POST',
      body: { originalText, modifiedText }
    });
  },

  async confirmChapter(projectId, chapterId) {
    return callWithFallback(
      () => mockApi.confirmChapter(projectId, chapterId),
      async () => {
        const data = await request(`/api/projects/${projectId}/chapters/${chapterId}/confirm`, { method: 'POST' });
        if (data.project) {
          updateState((state) => {
            state.projects = state.projects.map((project) => (project.id === data.project.id ? data.project : project));
            state.currentProjectId = data.project.id;
            state.pendingChapter = null;
            return state;
          });
        }
        return data;
      }
    );
  },

  async analyzeState(projectId) {
    return callWithFallback(
      () => mockApi.analyzeState(projectId),
      async () => request(`/api/projects/${projectId}/state/analyze`, { method: 'POST' })
    );
  }
};

export function toUserError(error) {
  if (!error) return '未知错误';
  if (error.name === 'AbortError') return '请求超时。请调大超时时间，或降低输出上限。';
  return error.message || String(error);
}
