const STORAGE_KEY = 'novel_studio_pro_frontend_v3_state';

const defaultAgentSwitches = {
  memory: true,
  constraint: true,
  director: true,
  character: true,
  foreshadow: true,
  writer: true,
  review: true,
  state: true
};

const defaultModelRoutes = [
  { task: '大纲补全', model: 'deepseek-v4-pro', temperature: 0.6, maxOutputTokens: 12000, fallback: 'deepseek-v4-flash' },
  { task: '章节导演', model: 'deepseek-v4-flash', temperature: 0.5, maxOutputTokens: 6000, fallback: 'deepseek-v4-flash' },
  { task: '正文写作', model: 'deepseek-v4-flash', temperature: 0.9, maxOutputTokens: 16000, fallback: 'deepseek-v4-flash' },
  { task: '连续性检查', model: 'deepseek-v4-pro', temperature: 0.2, maxOutputTokens: 6000, fallback: 'deepseek-v4-flash' },
  { task: '状态提取 JSON', model: 'deepseek-v4-flash', temperature: 0.1, maxOutputTokens: 5000, fallback: 'deepseek-v4-flash' }
];

const defaultSettings = {
  mockMode: true,
  backendBaseUrl: 'https://novel.aixiaolv.icu',
  requestTimeoutMs: 120000,
  retryTimes: 1,
  generationMode: 'standard',
  qualityThreshold: 85,
  autoRewriteTimes: 2,
  chapterWordTargetMin: 5000,
  chapterWordTargetMax: 8000,
  maxInputTokens: 64000,
  maxOutputTokens: 12000,
  temperatureWriting: 0.9,
  temperatureReview: 0.2,
  writingModel: 'deepseek-v4-flash',
  reviewModel: 'deepseek-v4-pro',
  fallbackModel: 'deepseek-v4-flash',
  embeddingModel: 'BAAI/bge-m3',
  modelRoutes: defaultModelRoutes,
  agentSwitches: defaultAgentSwitches,
  deepseekBaseUrl: 'https://api.deepseek.com',
  deepseekMainModel: 'deepseek-v4-flash',
  deepseekFastModel: 'deepseek-v4-flash',
  deepseekApiKeySet: false,
  streaming: true
};

const defaultState = {
  activeRoute: 'create',
  currentProjectId: null,
  projects: [],
  pendingChapter: null,
  lastJob: null,
  settings: defaultSettings,
  viewingChapterIndex: -1
};

const subscribers = new Set();

function safeParse(raw) {
  try {
    return raw ? JSON.parse(raw) : null;
  } catch (_error) {
    return null;
  }
}

function normalizeState(state) {
  const oldV2 = safeParse(localStorage.getItem('novel_studio_pro_frontend_v2_state'));
  const source = state || oldV2 || null;
  const merged = {
    ...defaultState,
    ...(source || {}),
    settings: {
      ...defaultSettings,
      ...((source && source.settings) || {}),
      agentSwitches: {
        ...defaultAgentSwitches,
        ...((source && source.settings && source.settings.agentSwitches) || {})
      },
      modelRoutes: Array.isArray(source?.settings?.modelRoutes) ? source.settings.modelRoutes : defaultModelRoutes
    }
  };
  if (!Array.isArray(merged.projects)) merged.projects = [];
  return merged;
}

export function getState() {
  const saved = safeParse(localStorage.getItem(STORAGE_KEY));
  return normalizeState(saved);
}

export function setState(nextState) {
  const normalized = normalizeState(nextState);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
  subscribers.forEach((fn) => fn(normalized));
  return normalized;
}

export function updateState(mutator) {
  const current = getState();
  const next = typeof mutator === 'function' ? mutator(structuredClone(current)) : mutator;
  return setState(next);
}

export function subscribe(fn) {
  subscribers.add(fn);
  return () => subscribers.delete(fn);
}

export function getCurrentProject() {
  const state = getState();
  return state.projects.find((project) => project.id === state.currentProjectId) || null;
}

export function updateProject(projectId, updater) {
  return updateState((state) => {
    state.projects = state.projects.map((project) => {
      if (project.id !== projectId) return project;
      return typeof updater === 'function' ? updater(project) : updater;
    });
    return state;
  });
}

export function setActiveRoute(route) {
  return updateState((state) => {
    state.activeRoute = route;
    return state;
  });
}

export function setSettings(partial) {
  return updateState((state) => {
    state.settings = {
      ...state.settings,
      ...partial,
      agentSwitches: {
        ...state.settings.agentSwitches,
        ...(partial.agentSwitches || {})
      }
    };
    return state;
  });
}

export function resetDemoData() {
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem('novel_studio_pro_frontend_v2_state');
  return setState(defaultState);
}

export function setViewingChapterIndex(index) {
  return updateState((state) => {
    state.viewingChapterIndex = index;
    return state;
  });
}

export function setCurrentProject(projectId) {
  return updateState((state) => {
    state.currentProjectId = projectId;
    state.viewingChapterIndex = -1;
    return state;
  });
}

export function setPendingChapter(chapter) {
  return updateState((state) => {
    state.pendingChapter = chapter;
    state.viewingChapterIndex = -1;
    return state;
  });
}

export function deleteProject(projectId) {
  return updateState((state) => {
    state.projects = state.projects.filter((p) => p.id !== projectId);
    if (state.currentProjectId === projectId) {
      state.currentProjectId = state.projects.length > 0 ? state.projects[0].id : null;
      state.activeRoute = state.projects.length > 0 ? 'blueprint' : 'create';
      state.pendingChapter = null;
      state.viewingChapterIndex = -1;
    }
    return state;
  });
}

export { defaultSettings, defaultState };
