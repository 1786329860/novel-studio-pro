import { getState } from './store.js';
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

export const api = {
  createProject(payload) {
    return callWithFallback(
      () => mockApi.createProject(payload),
      () => request('/api/projects', { method: 'POST', body: payload })
    );
  },

  buildProject(projectId) {
    return callWithFallback(
      () => mockApi.buildProject(projectId),
      () => request(`/api/projects/${projectId}/build`, { method: 'POST' })
    );
  },

  regenerateBlueprint(projectId) {
    return callWithFallback(
      () => mockApi.regenerateBlueprint(projectId),
      () => request(`/api/projects/${projectId}/blueprint/regenerate`, { method: 'POST' })
    );
  },

  generateNextChapter(projectId, options = {}) {
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
      () => request(`/api/projects/${projectId}/chapters/generate-next`, { method: 'POST', body })
    );
  },

  confirmChapter(projectId, chapterId) {
    return callWithFallback(
      () => mockApi.confirmChapter(projectId, chapterId),
      () => request(`/api/projects/${projectId}/chapters/${chapterId}/confirm`, { method: 'POST' })
    );
  },

  analyzeState(projectId) {
    return callWithFallback(
      () => mockApi.analyzeState(projectId),
      () => request(`/api/projects/${projectId}/state/analyze`, { method: 'POST' })
    );
  }
};

export function toUserError(error) {
  if (!error) return '未知错误';
  if (error.name === 'AbortError') return '请求超时。请调大超时时间，或降低输出上限。';
  return error.message || String(error);
}
