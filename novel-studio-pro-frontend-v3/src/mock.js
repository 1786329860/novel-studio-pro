import { getState, setState, updateState, getCurrentProject } from './store.js';

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const nowIso = () => new Date().toISOString();
const id = (prefix) => `${prefix}_${Math.random().toString(36).slice(2, 10)}_${Date.now().toString(36)}`;

function createVolumePlan(title, genre, lengthType) {
  const totalChapters = lengthType === 'short' ? 40 : lengthType === 'medium' ? 80 : lengthType === 'superlong' ? 220 : 120;
  const per = Math.ceil(totalChapters / 4);
  return [
    {
      id: 'vol_1',
      name: '卷一 · 命运初燃',
      range: `第1章 - 第${per}章`,
      status: '进行中',
      objective: '建立世界、主角困境、核心矛盾与第一组伏笔。',
      turningPoint: '主角被迫离开安全区，卷入更大的势力斗争。',
      tone: `${genre || '幻想'} / 铺垫 / 觉醒`,
      coverGradient: 'linear-gradient(135deg,#ffe2f0,#dff4ff,#fff2cb)'
    },
    {
      id: 'vol_2',
      name: '卷二 · 暗潮追影',
      range: `第${per + 1}章 - 第${per * 2}章`,
      status: '未开始',
      objective: '主线进入权力中心，女主线和反派线开始交织。',
      turningPoint: '关键人物身份反转，旧案真相露出裂缝。',
      tone: '权谋 / 追查 / 反转',
      coverGradient: 'linear-gradient(135deg,#d8eeff,#f3e7ff,#ffd8df)'
    },
    {
      id: 'vol_3',
      name: '卷三 · 真相低语',
      range: `第${per * 2 + 1}章 - 第${per * 3}章`,
      status: '未开始',
      objective: '揭开世界观深层规则，回收中期伏笔，制造情感抉择。',
      turningPoint: '读者以为的真相被推翻，真正敌人浮出水面。',
      tone: '揭秘 / 群像 / 冲突升级',
      coverGradient: 'linear-gradient(135deg,#e5fff5,#e7edff,#ffe2c9)'
    },
    {
      id: 'vol_4',
      name: '卷四 · 长明终局',
      range: `第${per * 3 + 1}章 - 第${totalChapters}章`,
      status: '未开始',
      objective: '完成主角成长、情感选择、反派终局与主题升华。',
      turningPoint: '主角以自己的方式打破旧秩序。',
      tone: '史诗 / 决战 / 升华',
      coverGradient: 'linear-gradient(135deg,#ffe1cc,#ffd6ef,#d6ecff)'
    }
  ];
}

function makeChapterTitle(n) {
  const titles = ['黑夜中的火光', '禁忌的代价', '离别与启程', '初入迷雾之城', '命运的第一次选择', '来自深渊的低语', '旧账与夜火', '风暴前的信笺', '沉默的钟楼', '假面舞会'];
  return titles[(n - 1) % titles.length];
}

function buildInitialProject(payload) {
  const projectId = id('project');
  const title = payload.title?.trim() || '未命名小说';
  const genre = payload.genre || '奇幻';
  const lengthType = payload.lengthType || 'long';
  const volumePlan = createVolumePlan(title, genre, lengthType);

  const chaptersPreview = Array.from({ length: 12 }).map((_, index) => ({
    number: index + 1,
    title: makeChapterTitle(index + 1),
    status: 'planned'
  }));

  return {
    id: projectId,
    title,
    outline: payload.outline || '',
    genre,
    lengthType,
    mode: payload.mode || 'balanced',
    createdAt: nowIso(),
    updatedAt: nowIso(),
    totalTargetChapters: lengthType === 'short' ? 40 : lengthType === 'medium' ? 80 : lengthType === 'superlong' ? 220 : 120,
    wordCount: 0,
    currentChapterNumber: 0,
    storyBible: {
      style: '青春明亮、节奏清爽、情绪直接，兼顾群像与主线推进。',
      corePremise: payload.outline ? payload.outline.slice(0, 120) : '主角在命运与真相的夹缝中成长，逐步揭开隐藏在世界背后的巨大阴谋。',
      mainConflict: '个人命运、家族旧案、世界规则与隐藏势力之间的冲突。',
      endingDirection: '主角完成自我选择，打破旧秩序，让故事主题得到情感落点。',
      forbiddenRules: [
        '不能让主角过早知道最终真相。',
        '女主必须拥有独立行动线，不能只作为主角陪衬。',
        '反派不能无动机作恶，必须维持自己的行动逻辑。'
      ],
      volumePlan,
      chapterTitlePreview: chaptersPreview
    },
    characters: [
      { id: 'char_mc', name: '江离', role: '主角', currentGoal: '追查旧案真相', lastAppeared: 0, dropoutRisk: 0.08, agencyScore: 0.88, trust: 50 },
      { id: 'char_fl', name: '沈烁', role: '女主', currentGoal: '寻找自己家族与旧案的关系', lastAppeared: 0, dropoutRisk: 0.18, agencyScore: 0.82, trust: 35 },
      { id: 'char_support', name: '苏照', role: '重要配角', currentGoal: '暗中保护女主，同时隐藏旧身份', lastAppeared: 0, dropoutRisk: 0.28, agencyScore: 0.61, trust: 40 },
      { id: 'char_villain', name: '夜烬', role: '反派', currentGoal: '利用旧案逼迫主角入局', lastAppeared: 0, dropoutRisk: 0.46, agencyScore: 0.78, trust: 0 }
    ],
    foreshadows: [
      { id: 'fb_001', name: '夜火计划', status: '已埋下', firstChapter: 0, lastMentioned: 0, risk: 0.25, plannedPayoff: 28 },
      { id: 'fb_002', name: '旧家徽的裂纹', status: '待回收', firstChapter: 0, lastMentioned: 0, risk: 0.35, plannedPayoff: 18 },
      { id: 'fb_003', name: '女主家族的沉默', status: '已埋下', firstChapter: 0, lastMentioned: 0, risk: 0.28, plannedPayoff: 32 }
    ],
    truthSource: {
      authorTruth: 100,
      readerKnown: 8,
      protagonistKnown: 5,
      femaleLeadKnown: 12,
      misdirection: 18
    },
    events: [],
    chapters: [],
    status: {
      mainProgress: 0,
      foreshadowCount: 3,
      activeCharacters: 4,
      deviationRisk: 0.08,
      qualityScore: 90,
      tests: []
    }
  };
}

export const mockApi = {
  async createProject(payload) {
    await wait(350);
    const project = buildInitialProject(payload);
    updateState((state) => {
      state.projects.unshift(project);
      state.currentProjectId = project.id;
      state.activeRoute = 'blueprint';
      state.pendingChapter = null;
      return state;
    });
    return { project };
  },

  async buildProject(projectId) {
    await wait(650);
    updateState((state) => {
      const project = state.projects.find((item) => item.id === projectId);
      if (project) project.updatedAt = nowIso();
      return state;
    });
    const project = getCurrentProject();
    return { project, message: 'AI 已完成故事蓝图、分卷规划、角色系统、伏笔与真相源初始化。' };
  },

  async regenerateBlueprint(projectId) {
    await wait(600);
    updateState((state) => {
      const project = state.projects.find((item) => item.id === projectId);
      if (project) {
        project.storyBible.style = '青春活力、轻盈明亮、冲突清晰，保留史诗感但减少压抑感。';
        project.storyBible.mainConflict = '个人成长、真相追寻、情感选择与势力博弈共同推进。';
        project.storyBible.volumePlan = createVolumePlan(project.title, project.genre, project.lengthType).map((volume, index) => ({
          ...volume,
          name: ['卷一 · 星火初见', '卷二 · 云上追光', '卷三 · 深海回声', '卷四 · 长明之约'][index]
        }));
        project.updatedAt = nowIso();
      }
      return state;
    });
    return { project: getCurrentProject(), message: '已重新扩写蓝图。' };
  },

  async generateNextChapter(projectId, options = {}) {
    await wait(900);
    const state = getState();
    const project = state.projects.find((item) => item.id === projectId);
    if (!project) throw new Error('项目不存在');

    const nextNumber = project.currentChapterNumber + 1;
    const title = nextNumber === 1 ? '命运开始的清晨' : makeChapterTitle(nextNumber);
    const qualityScore = 88 + (nextNumber % 8);
    const wordCount = 2800 + nextNumber * 37;
    const focusFemale = nextNumber % 3 === 0 ? 44 : 34;

    const chapter = {
      id: id('chapter'),
      number: nextNumber,
      title,
      status: 'pending',
      wordCount,
      createdAt: nowIso(),
      directorPlan: {
        goal: '推动主线调查，同时让女主拥有独立行动段落，并轻微回响旧案伏笔。',
        pov: nextNumber % 2 === 0 ? '江离 60% / 沈烁 40%' : '江离 55% / 沈烁 35% / 苏照 10%',
        roleFocus: { 江离: 42, 沈烁: focusFemale, 苏照: 12, 夜烬: 8 },
        forbidden: ['不能揭露最终真相', '不能让反派直接解释阴谋', '不能让女主只被动跟随']
      },
      text: `清晨的光从窗棂斜斜落进来，像一层被揉开的糖纸，轻轻铺在桌上的旧信封上。\n\n江离没有立刻拆开它。他记得昨夜风声里那句未说完的话，也记得沈烁转身时藏在袖口里的那枚银扣。所有线索都像被雨水冲散的墨迹，看似模糊，却总在某个边缘露出原本的形状。\n\n门外传来很轻的脚步声。沈烁没有敲门，只把一页账册推到门缝里。纸页上压着一朵刚摘下的白色小花，花瓣还带着露。\n\n“你要找的人昨夜离开了。”她的声音隔着门板传来，清亮，却不急。“但他不是逃走，是被人带走。”\n\n江离抬起眼。\n\n那一刻，他忽然意识到，沈烁查到的东西，或许比他更多。`,
      review: {
        totalScore: qualityScore,
        continuity: 95,
        characterAgency: 88,
        foreshadow: 90,
        style: 92,
        aiFlavorRisk: 0.12,
        tests: [
          { name: '连续性检查', passed: true, score: 96, note: '情节衔接良好' },
          { name: '视角稳定性', passed: true, score: 94, note: '视角切换自然' },
          { name: '女主主动性', passed: true, score: focusFemale >= 40 ? 92 : 86, note: '女主拥有独立行动' },
          { name: '禁止揭露检查', passed: true, score: 100, note: '无超前泄露' },
          { name: 'AI 味检测', passed: true, score: 91, note: '模板句较少' }
        ]
      },
      stateDelta: {
        newForeshadows: ['白色小花的来源', '账册缺页'],
        relationshipChanges: ['江离 ↔ 沈烁：信任 +8', '江离 ↔ 夜烬：敌意 +5'],
        eventUpdates: ['沈烁主动提交线索', '失踪者并非逃走，而是被带走'],
        timeline: ['清晨：江离收到沈烁线索']
      }
    };

    updateState((draftState) => {
      draftState.pendingChapter = chapter;
      draftState.lastJob = {
        type: 'generate_next_chapter',
        status: 'done',
        projectId,
        finishedAt: nowIso(),
        mode: options.mode || draftState.settings.generationMode
      };
      draftState.activeRoute = 'writing';
      return draftState;
    });

    return { chapter };
  },

  async confirmChapter(projectId, chapterId) {
    await wait(350);
    let confirmed = null;
    const nextState = updateState((state) => {
      const project = state.projects.find((item) => item.id === projectId);
      const pending = state.pendingChapter;
      if (!project || !pending || pending.id !== chapterId) return state;

      confirmed = { ...pending, status: 'confirmed' };
      project.chapters.push(confirmed);
      project.currentChapterNumber = confirmed.number;
      project.wordCount += confirmed.wordCount;
      project.updatedAt = nowIso();
      project.status.mainProgress = Math.min(100, project.status.mainProgress + 4);
      project.status.qualityScore = confirmed.review.totalScore;
      project.status.foreshadowCount += confirmed.stateDelta.newForeshadows.length;
      project.status.deviationRisk = Math.max(0.05, project.status.deviationRisk - 0.01);
      project.status.tests = confirmed.review.tests;

      project.events.push(
        ...confirmed.stateDelta.eventUpdates.map((eventText, index) => ({
          id: id('evt'),
          chapter: confirmed.number,
          time: `第${confirmed.number}章 0${index}:12`,
          scene: index % 2 ? '街口' : '书房',
          characters: index % 2 ? '沈烁' : '江离',
          event: eventText,
          impact: index % 2 ? '角色行动' : '推进主线',
          visibility: '主角/读者'
        }))
      );

      project.foreshadows.push(
        ...confirmed.stateDelta.newForeshadows.map((name, index) => ({
          id: id('fb'),
          name,
          status: '已埋下',
          firstChapter: confirmed.number,
          lastMentioned: confirmed.number,
          risk: 0.18 + index * 0.08,
          plannedPayoff: confirmed.number + 10 + index * 4
        }))
      );

      project.characters = project.characters.map((char) => {
        if (['江离', '沈烁', '苏照'].includes(char.name)) {
          return {
            ...char,
            lastAppeared: confirmed.number,
            dropoutRisk: Math.max(0.05, char.dropoutRisk - 0.06),
            agencyScore: Math.min(1, char.agencyScore + 0.02)
          };
        }
        return {
          ...char,
          dropoutRisk: Math.min(0.9, char.dropoutRisk + 0.03)
        };
      });

      state.pendingChapter = null;
      return state;
    });

    return { project: nextState.projects.find((item) => item.id === projectId), chapter: confirmed };
  },

  async analyzeState(projectId) {
    await wait(450);
    const project = getState().projects.find((item) => item.id === projectId);
    if (!project) throw new Error('项目不存在');
    return {
      report: {
        generatedAt: nowIso(),
        summary: '状态良好。主线推进稳定，伏笔风险可控，建议下一章继续提高女主主动行动比例。',
        score: project.status.qualityScore || 90
      }
    };
  }
};
