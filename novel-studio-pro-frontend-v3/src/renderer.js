import { api, toUserError } from './api.js';
import { getState, setActiveRoute, setSettings, resetDemoData, subscribe, setViewingChapterIndex, setCurrentProject, updateProject, updateState, setPendingChapter, deleteProject } from './store.js';

const app = document.querySelector('#app');
let busyText = '';
let streamProgress = null;  // 流式进度状态: { agent, text, rewriteAttempt, rewriteReason }
let toast = null;

const navItems = [
  { id: 'project', icon: '▦', label: '项目总览' },
  { id: 'create', icon: '＋', label: '新建项目' },
  { id: 'blueprint', icon: '◇', label: '故事蓝图' },
  { id: 'characters', icon: '♡', label: '角色系统' },
  { id: 'truth', icon: '!', label: '伏笔与真相' },
  { id: 'writing', icon: '✎', label: '章节写作' },
  { id: 'status', icon: '⚙', label: '状态面板' },
  { id: 'ledger', icon: '▤', label: '事件账本' },
  { id: 'memory', icon: '◎', label: '全局记忆' },
  { id: 'generation', icon: '✦', label: '生成设置' },
  { id: 'models', icon: '▣', label: '模型配置' },
  { id: 'deepseek', icon: '◆', label: 'DeepSeek API' }
];

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function clamp(value, min = 0, max = 100) {
  return Math.min(max, Math.max(min, Number(value) || 0));
}

function pct(value) {
  const n = Number(value) <= 1 ? Number(value) * 100 : Number(value);
  return Math.round(clamp(n));
}

function formatPct(value) {
  return `${pct(value)}%`;
}

function progress(value, color = 'blue') {
  return `<div class="progress"><span class="progress-fill ${color}" style="width:${pct(value)}%"></span></div>`;
}

function pill(text, tone = 'blue') {
  return `<span class="pill ${tone}">${escapeHtml(text)}</span>`;
}

function number(value) {
  return Number(value || 0).toLocaleString('zh-CN');
}

function getProject(state) {
  return state.projects.find((item) => item.id === state.currentProjectId) || null;
}

function showToast(message, tone = 'ok') {
  toast = { message, tone };
  render();
  setTimeout(() => {
    toast = null;
    render();
  }, 2600);
}

async function runTask(text, task) {
  try {
    busyText = text;
    render();
    const result = await task();
    busyText = '';
    render();
    return result;
  } catch (error) {
    busyText = '';
    render();
    showToast(toUserError(error), 'error');
    throw error;
  }
}

function renderSidebar(state, project) {
  return `
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">✦</div>
        <div class="brand-title">Novel Studio Pro</div>
      </div>
      <nav class="nav">
        ${navItems.map((item) => `
          <button class="nav-item ${state.activeRoute === item.id ? 'active' : ''}" data-route="${item.id}">
            <span class="nav-icon">${item.icon}</span>
            <span>${item.label}</span>
          </button>
        `).join('')}
      </nav>
      <div class="project-card mini-card">
        <div class="cover-sky"><div class="sun"></div><div class="castle">♜</div></div>
        <div class="project-name">${escapeHtml(project?.title || '未创建项目')}</div>
        <div class="project-meta">${escapeHtml(project?.genre || '题材未定')} / 自动化 / 本地</div>
        <div class="project-stats"><span>总字数</span><b>${number(project?.wordCount)}</b></div>
        <div class="project-stats"><span>已写章节</span><b>${project?.currentChapterNumber || 0} / ${project?.totalTargetChapters || 120}</b></div>
        ${progress(project ? (project.currentChapterNumber / project.totalTargetChapters) * 100 : 0, 'pink')}
      </div>
      <div class="sidebar-footer"><span>版本 0.3.0</span><span class="ok-dot">✓</span></div>
    </aside>
  `;
}

function renderTopbar(state, project) {
  const projectListHtml = state.projects.length > 1 ? `<div class="project-dropdown" id="project-dropdown">${state.projects.map((p) => `<div class="project-dropdown-item ${p.id === state.currentProjectId ? 'active' : ''}" data-action="switchProject" data-project-id="${escapeHtml(p.id)}">${p.id === state.currentProjectId ? '<span class="check-mark">✓</span>' : '<span class="check-mark"></span>'}<div class="dropdown-item-info"><b>${escapeHtml(p.title || '未命名项目')}</b><small>${p.chapters ? p.chapters.length : 0} 章</small></div><button class="dropdown-delete-btn" data-action="deleteProject" data-project-id="${escapeHtml(p.id)}" title="删除项目">×</button></div>`).join('')}</div>` : '';
  return `
    <header class="topbar">
      <div class="project-select-wrapper"><div class="project-select" data-action="showProjectList">当前项目：<b>${escapeHtml(project?.title || '未命名项目')}</b><span>⌄</span></div>${projectListHtml}</div>
      <div class="autosave"><span class="green-dot"></span>自动保存：${new Date().toLocaleTimeString('zh-CN', { hour12: false })}</div>
      <div class="top-actions">
        <button class="soft-btn" data-action="analyzeState">⌁ 智能检查</button>
        <button class="soft-btn" data-route="memory">▣ 全局记忆</button>
        <button class="soft-btn" data-route="generation">⚙ 生成设置</button>
      </div>
    </header>
  `;
}

function emptyProjectPanel() {
  return `
    <main class="page">
      <section class="empty-state card">
        <div class="empty-icon">✦</div>
        <h2>还没有小说项目</h2>
        <p>先输入小说名和总大纲，AI 会自动生成写作风格、故事蓝图、分卷走向、章节标题、角色系统、伏笔与真相源。</p>
        <button class="primary-btn" data-route="create">去创建项目</button>
      </section>
    </main>
  `;
}

function renderCreatePage() {
  return `
    <main class="page create-grid">
      <section class="hero-card card">
        <div>
          <h1>创建新小说项目</h1>
          <p class="hero-sub">强大自动化引擎 · 一键开启创作 · 状态驱动系统</p>
          <p class="muted">你只需要填写小说名和总大纲，其余设定由 AI 自动生成并持续优化。</p>
        </div>
        <div class="hero-orbit"><span></span></div>
      </section>

      <form id="create-form" class="card create-form">
        <label class="field-label">小说名</label>
        <input name="title" class="input" placeholder="输入小说名，例如：夜火长明" required maxlength="30" />
        <div class="hint">必填。后续章节标题、卷名、角色称呼都会围绕它统一风格。</div>

        <label class="field-label">总大纲输入区</label>
        <textarea name="outline" class="textarea" placeholder="请输入你的小说总大纲或故事梗概。简陋也可以，AI 会自动补全世界观、主线、支线、人物、伏笔、结局方向。" required></textarea>
        <div class="hint">建议包含：故事背景、主线冲突、主要角色、开篇起点、结局方向。</div>

        <div class="form-row">
          <div class="card inner">
            <label class="field-label">题材类型</label>
            <select name="genre" class="select">
              ${['奇幻', '玄幻', '都市', '悬疑', '仙侠', '科幻', '言情', '权谋'].map((x) => `<option>${x}</option>`).join('')}
            </select>
            <div class="chip-row">${['青春感', '群像', '爽点', '慢热', '轻权谋'].map((item) => pill(item, 'soft')).join('')}</div>
          </div>
          <div class="card inner">
            <label class="field-label">目标篇幅</label>
            <select name="lengthType" class="select">
              <option value="short">短篇：10万以内</option>
              <option value="medium">中篇：10-50万</option>
              <option value="long" selected>长篇：50-150万</option>
              <option value="superlong">超长篇：150万以上</option>
            </select>
          </div>
          <div class="card inner">
            <label class="field-label">生成模式</label>
            <select name="mode" class="select">
              <option value="balanced">平衡模式：剧情平衡，节奏适中</option>
              <option value="high_density">高浓度模式：高冲突，快节奏</option>
              <option value="slow_burn">慢热模式：细腻铺垫，重关系</option>
            </select>
          </div>
        </div>

        <section class="auto-grid">
          <h3>AI 将自动完成</h3>
          ${[
            ['写作风格', '匹配题材与氛围'], ['分卷规划', '自动规划章节结构'], ['每卷走向', '生成卷纲与关键事件'], ['角色系统', '角色设定与关系网'],
            ['伏笔与真相', '埋设伏笔与揭示路径'], ['章节标题', '生成吸引力章节名'], ['世界观扩展', '补全世界观与设定'], ['节奏控制', '优化情绪曲线']
          ].map(([a, b]) => `<div class="auto-item"><span>✧</span><b>${a}</b><small>${b}</small></div>`).join('')}
        </section>

        <button class="big-cta" type="submit">✦ 开始自动构建小说</button>
        <p class="center-hint">无需登录 · 本地运行 · 数据安全 · 完全自动化</p>
      </form>

      <aside class="card preview-panel">
        <h2>自动补全预览</h2>
        <p class="muted">AI 生成内容仅为预览，最终以实际生成结果为准。</p>
        ${[
          ['核心主线', '主角因意外获得关键线索，卷入家族旧案与更大世界的秘密，逐步完成成长与选择。', ['成长逆袭', '真相探寻', '宿命抗争']],
          ['女主线', '女主拥有独立目标，她的家族、记忆与核心伏笔相连，将推动关键转折。', ['身世之谜', '共同成长', '主动行动']],
          ['反派线', '反派不是单纯作恶，而是背负旧时代的创伤与理想，形成镜像对立。', ['复仇之火', '理念冲突', '悲剧宿命']]
        ].map(([title, text, tags]) => `<div class="preview-card"><h3>${title}</h3><p>${text}</p><div>${tags.map((item) => pill(item, 'blue')).join('')}</div></div>`).join('')}
        <div class="preview-card warm"><h3>前三卷规划</h3><ol><li>第一卷 · 命运的开端</li><li>第二卷 · 暗影的追逐</li><li>第三卷 · 真相的低语</li></ol></div>
      </aside>
    </main>
  `;
}

function renderProjectPage(project) {
  if (!project) return emptyProjectPanel();
  const last = project.chapters.at(-1);
  return `
    <main class="page project-overview">
      <div class="page-head">
        <div>
          <h1>项目总览 · ${escapeHtml(project.title)}</h1>
          <p>个人本地 EXE 版，自动管理故事蓝图、角色、伏笔、事件账本与模型生成流程。</p>
        </div>
        <div class="head-actions"><button class="primary-btn" data-route="writing">进入章节写作</button><button class="soft-btn" data-route="generation">生成设置</button></div>
      </div>
      <section class="summary-strip">
        ${[
          ['当前章节', project.currentChapterNumber ? `第 ${project.currentChapterNumber} 章` : '尚未生成', 'pink'],
          ['总字数', number(project.wordCount), 'blue'],
          ['自动化模式', project.mode || 'balanced', 'orange'],
          ['质量评分', `${project.status.qualityScore || 90}/100`, 'mint']
        ].map(([a, b, tone]) => `<div class="card summary-card ${tone}"><h3>${a}</h3><strong class="hero-number">${escapeHtml(b)}</strong>${a === '当前章节' && last ? `<p>${escapeHtml(last.title)}</p>` : ''}</div>`).join('')}
      </section>
      <section class="dashboard-grid">
        <div class="card wide-card"><h2>强自动化闭环</h2><div class="flow-row">${['大纲补全', '故事蓝图', '分卷走向', '角色系统', '伏笔真相', '章节导演', '正文生成', '检查修正', '状态入库'].map((x) => `<span>${x}</span>`).join('')}</div></div>
        <div class="card"><h2>下一步建议</h2><p class="muted">${last ? '继续点击「生成下一章」，系统会自动读取上一章状态并推进剧情。' : '先进入章节写作，生成第一章。'}</p><button class="next-btn small" data-route="writing">开始写作</button></div>
        <div class="card"><h2>状态健康度</h2>${[['主线推进', project.status.mainProgress || 0, 'blue'], ['偏离风险', project.status.deviationRisk || 0.08, 'mint'], ['角色主动性', 86, 'pink'], ['伏笔健康', 88, 'orange']].map(([a, b, c]) => `<div class="metric-line"><b>${a}</b><span>${formatPct(b)}</span>${progress(b, c)}</div>`).join('')}</div>
        <div class="card"><h2>最近章节</h2>${project.chapters.length ? project.chapters.slice(-5).map((ch) => `<div class="title-row"><span>第${ch.number}章</span><b>${escapeHtml(ch.title)}</b></div>`).join('') : '<p class="muted">暂无章节，等待生成。</p>'}</div>
        <div class="card"><h2>核心角色</h2>${project.characters.slice(0, 4).map((char) => `<div class="list-row"><span class="avatar">${char.name.slice(0,1)}</span><div><b>${escapeHtml(char.name)}</b><small>${escapeHtml(char.role)} / ${escapeHtml(char.currentGoal)}</small></div>${pill(`${Math.round(char.agencyScore * 100)} 主动`, 'mint')}</div>`).join('')}</div>
        <div class="card"><h2>高优先伏笔</h2>${project.foreshadows.slice(0, 5).map((fb) => `<div class="list-row"><span class="dot-icon">✧</span><div><b>${escapeHtml(fb.name)}</b><small>计划第 ${fb.plannedPayoff} 章回收</small></div>${pill(fb.status, fb.risk > 0.45 ? 'red' : 'blue')}</div>`).join('')}</div>
      </section>
    </main>
  `;
}

function renderBlueprintPage(project) {
  if (!project) return emptyProjectPanel();
  const volumes = project.storyBible.volumePlan || [];
  return `
    <main class="page blueprint-page">
      <div class="page-head">
        <div><h1>故事蓝图 · ${escapeHtml(project.title)}</h1><p>全局视角规划故事结构、节奏、冲突与伏笔，构建完整的创作蓝图。</p></div>
        <div class="head-actions"><button class="soft-btn" data-action="regenerateBlueprint">重新扩写蓝图</button><button class="primary-btn" data-route="writing">应用并开始写作</button></div>
      </div>
      <section class="summary-strip">
        ${[
          ['核心命题', project.storyBible.corePremise, 'pink'],
          ['主线冲突', project.storyBible.mainConflict, 'blue'],
          ['结局方向', project.storyBible.endingDirection, 'orange'],
          ['写作风格', project.storyBible.style, 'mint']
        ].map(([title, text, tone]) => `<div class="card summary-card ${tone}"><h3>${title}</h3><p>${escapeHtml(text)}</p></div>`).join('')}
      </section>
      <section class="card"><div class="section-title"><h2>分卷规划</h2><button class="tiny-btn">调整卷结构</button></div><div class="volume-grid">${volumes.map((volume) => `<article class="volume-card"><div class="volume-art" style="background:${volume.coverGradient}"><span>${escapeHtml(volume.status)}</span></div><h3>${escapeHtml(volume.name)}</h3><p><b>章节范围：</b>${escapeHtml(volume.range)}</p><p><b>核心目标：</b>${escapeHtml(volume.objective)}</p><p><b>重大转折：</b>${escapeHtml(volume.turningPoint)}</p><p><b>叙事基调：</b>${escapeHtml(volume.tone)}</p></article>`).join('')}</div></section>
      <section class="card roadmap"><h2>阶段计划（每卷走向）</h2><div class="road-line">${[['铺垫期', '1-10章', '建立世界与角色'], ['发展期', '11-30章', '主线推进，矛盾升级'], ['转折期', '31-50章', '关键角色登场'], ['爆发期', '51-60章', '重大事件爆发'], ['沉淀期', '61-80章', '真相逐步拼合'], ['决战期', '81-100章', '命运交汇'], ['终局期', '101-120章', '旧世新生']].map(([a, b, c], i) => `<div class="road-node n${i}"><span></span><b>${a}</b><small>${b}</small><em>${c}</em></div>`).join('')}</div></section>
      <section class="blueprint-bottom">
        <div class="card"><h2>主要角色</h2>${project.characters.map((char) => `<div class="list-row"><span class="avatar">${char.name.slice(0, 1)}</span><div><b>${escapeHtml(char.name)}</b><small>${escapeHtml(char.role)} / ${escapeHtml(char.currentGoal)}</small></div>${pill(Math.round(char.agencyScore * 100) + ' 主动性', 'mint')}</div>`).join('')}</div>
        <div class="card"><h2>伏笔总览</h2>${project.foreshadows.slice(0, 5).map((fb) => `<div class="list-row"><span class="dot-icon">✧</span><div><b>${escapeHtml(fb.name)}</b><small>计划第 ${fb.plannedPayoff} 章回收</small></div>${pill(fb.status, fb.risk > 0.5 ? 'red' : 'blue')}</div>`).join('')}</div>
        <div class="card"><h2>章节标题预览</h2>${project.storyBible.chapterTitlePreview.slice(0, 8).map((chapter) => `<div class="title-row"><span>第${chapter.number}章</span><b>${escapeHtml(chapter.title)}</b></div>`).join('')}</div>
        <aside class="card analysis-panel"><h2>AI 蓝图分析</h2>${[['大纲完整度', 92], ['世界观扩展度', 88], ['角色群像平衡', 85], ['商业节奏', 90]].map(([name, val]) => `<div class="metric-line"><b>${name}</b><span>${val}%</span>${progress(val, 'blue')}</div>`).join('')}<div class="suggestion"><b>自动建议</b><p>建议中期增加一次女主独立推进真相的章节，防止主角中心化。</p></div></aside>
      </section>
    </main>
  `;
}

function renderCharactersPage(project) {
  if (!project) return emptyProjectPanel();
  return `
    <main class="page characters-page">
      <div class="page-head">
        <div><h1>角色系统 · 主动性调度</h1><p>每个角色都有目标、情绪、掌握信息、掉线风险和下一步行动，避免只围绕主角写。</p></div>
        <div class="head-actions"><button class="primary-btn">自动补全角色卡</button><button class="soft-btn">导出角色表</button></div>
      </div>
      <section class="kpi-row compact-kpi">
        ${[
          ['总角色', project.characters.length, '已建档'],
          ['高主动角色', project.characters.filter((c) => c.agencyScore > 0.75).length, '可推动剧情'],
          ['掉线预警', project.characters.filter((c) => c.dropoutRisk > 0.45).length, '需调度回归'],
          ['关系节点', Math.max(6, project.characters.length * 2), '自动维护']
        ].map(([a, b, c]) => `<div class="card kpi blue"><h3>${a}</h3><strong>${b}</strong><small>${c}</small></div>`).join('')}
      </section>
      <section class="characters-layout">
        <div class="character-grid">
          ${project.characters.map((char) => `<article class="card character-card">
            <div class="character-top"><span class="avatar big">${escapeHtml(char.name.slice(0, 1))}</span><div><h2>${escapeHtml(char.name)}</h2><p>${escapeHtml(char.role)}</p></div>${pill(char.dropoutRisk > 0.5 ? '需回归' : '正常', char.dropoutRisk > 0.5 ? 'red' : 'mint')}</div>
            <p class="muted"><b>当前目标：</b>${escapeHtml(char.currentGoal)}</p>
            <p class="muted"><b>隐藏动机：</b>${escapeHtml(char.hiddenGoal || '由 AI 根据蓝图持续补全')}</p>
            <div class="metric-line"><b>主动性</b><span>${Math.round(char.agencyScore * 100)}%</span>${progress(char.agencyScore, 'pink')}</div>
            <div class="metric-line"><b>掉线风险</b><span>${formatPct(char.dropoutRisk)}</span>${progress(char.dropoutRisk, char.dropoutRisk > 0.5 ? 'orange' : 'mint')}</div>
            <div class="chip-row">${['下一章可行动', '知识边界已锁定', '关系线自动维护'].map((x) => pill(x, 'soft')).join('')}</div>
          </article>`).join('')}
        </div>
        <aside class="card role-director">
          <h2>角色导演建议</h2>
          <div class="preview-card"><h3>下一章出场调度</h3><p>优先让女主独立获得线索，主角随后从结果反推，保持双线推动。</p>${pill('女主戏份 ≥ 38%', 'pink')}${pill('主角不超过 55%', 'blue')}</div>
          <div class="preview-card"><h3>信息边界</h3><p>女主可以怀疑旧案关联，但不能确认最终真相；反派只能通过行动施压，不直接解释阴谋。</p></div>
          <h2>关系变化矩阵</h2>
          ${relationRows(project).map((row) => `<div class="relation-row"><b>${row.from}</b><span>→</span><b>${row.to}</b><em>${row.type}</em>${progress(row.score, row.tone)}</div>`).join('')}
        </aside>
      </section>
    </main>
  `;
}

function relationRows(project) {
  const names = project.characters.map((c) => c.name);
  return [
    { from: names[0] || '主角', to: names[1] || '女主', type: '互相试探', score: 62, tone: 'pink' },
    { from: names[0] || '主角', to: names[2] || '配角', type: '合作但保留', score: 48, tone: 'blue' },
    { from: names[1] || '女主', to: names[3] || '反派', type: '信息不对称', score: 35, tone: 'orange' }
  ];
}

function renderTruthPage(project) {
  if (!project) return emptyProjectPanel();
  const truth = project.truthSource || {};
  return `
    <main class="page truth-page">
      <div class="page-head"><div><h1>伏笔与真相 · 生命周期管理</h1><p>同时管理作者真相、读者已知、角色已知和误导信息，防止提前剧透和伏笔丢失。</p></div><div class="head-actions"><button class="primary-btn">自动整理伏笔</button><button class="soft-btn">生成回收计划</button></div></div>
      <section class="truth-grid">
        <div class="card truth-main"><h2>真相源 / 信息层级</h2>${Object.entries(truth).map(([key, val]) => `<div class="metric-line"><b>${truthLabel(key)}</b><span>${val}%</span>${progress(val, key === 'misdirection' ? 'orange' : 'blue')}</div>`).join('')}<p class="muted">作者真相为隐藏真实设定；读者和角色只能按计划逐步接近真相。</p></div>
        <div class="card"><h2>揭示节奏</h2>${[['轻微暗示', 25, '1-20章'], ['阶段线索', 45, '21-45章'], ['误导反转', 64, '46-70章'], ['核心揭露', 88, '71章后']].map(([a,b,c]) => `<div class="title-row"><span>${c}</span><b>${a}</b></div>${progress(b, 'pink')}`).join('')}</div>
        <div class="card"><h2>禁止提前揭露</h2><ul class="doc-list"><li>最终主谋身份不得在前 40% 篇幅确认。</li><li>女主家族真相只能先怀疑，不能直接证实。</li><li>反派不能通过长对白解释完整阴谋。</li></ul></div>
      </section>
      <section class="card"><div class="section-title"><h2>伏笔生命周期表</h2><button class="tiny-btn">新增伏笔</button></div><div class="foreshadow-grid">${project.foreshadows.map((fb) => `<article class="foreshadow-card"><div class="section-title"><h3>${escapeHtml(fb.name)}</h3>${pill(fb.status, fb.risk > 0.5 ? 'red' : fb.status.includes('回收') ? 'orange' : 'blue')}</div><p><b>首次出现：</b>第 ${fb.firstChapter} 章</p><p><b>最后提及：</b>第 ${fb.lastMentioned} 章</p><p><b>计划回收：</b>第 ${fb.plannedPayoff} 章</p><div class="metric-line"><b>遗忘风险</b><span>${formatPct(fb.risk)}</span>${progress(fb.risk, fb.risk > 0.5 ? 'orange' : 'mint')}</div></article>`).join('')}</div></section>
      <section class="card"><h2>真相节点路线图</h2><div class="truth-road">${['埋下异常', '重复回响', '制造误导', '阶段解释', '情绪爆点', '最终回收'].map((x, i) => `<span class="truth-node t${i}">${x}</span>`).join('')}</div></section>
    </main>
  `;
}

function renderWritingPage(project, pendingChapter, state) {
  if (!project) return emptyProjectPanel();
  const viewingIndex = state.viewingChapterIndex;
  let chapter;
  let isPending = false;
  if (pendingChapter && (viewingIndex === -1 || viewingIndex >= project.chapters.length)) {
    chapter = pendingChapter;
    isPending = true;
  } else if (viewingIndex >= 0 && viewingIndex < project.chapters.length) {
    chapter = project.chapters[viewingIndex];
  } else {
    chapter = project.chapters.at(-1) || {
      number: project.currentChapterNumber + 1,
      title: '等待生成',
      wordCount: 0,
      text: '点击下方「生成下一章」，系统会自动读取故事蓝图、角色状态、伏笔生命周期、事件账本和真相源，然后完成导演稿、正文、检查、修正与状态差异预览。',
      directorPlan: { goal: '等待自动生成本章目标', pov: '等待视角调度器安排', roleFocus: { 江离: 0, 沈烁: 0 }, forbidden: ['禁止提前揭露最终真相'] },
      review: { totalScore: project.status.qualityScore || 90, tests: [] },
      stateDelta: { newForeshadows: [], relationshipChanges: [], eventUpdates: [], timeline: [] }
    };
  }
  const dp = chapter.directorPlan || { goal: '', pov: '', roleFocus: {}, forbidden: [] };
  const roleEntries = Object.entries(dp.roleFocus || {});
  const guideText = typeof dp === 'object' ? [
    `【本章目标】\n${dp.goal || ''}`,
    `【视角安排】\n${dp.pov || ''}`,
    `【角色站位】\n${roleEntries.map(([k, v]) => `${k} ${v}%`).join(' / ')}`,
    `【禁止事项】\n${(dp.forbidden || []).join('；')}`
  ].join('\n\n') : '';
  const chapterListItems = project.chapters.map((ch, idx) => {
    const isActive = idx === viewingIndex;
    return `<div class="chapter-list-item ${isActive ? 'active' : ''}" data-action="selectChapter" data-chapter-index="${idx}"><span class="chapter-list-number">第${ch.number}章</span><b class="chapter-list-title">${escapeHtml(ch.title)}</b><span class="pill mint">已确认</span></div>`;
  }).join('');
  const pendingItem = pendingChapter ? `<div class="chapter-list-item ${viewingIndex === -1 || viewingIndex >= project.chapters.length ? 'active' : ''}" data-action="selectChapter" data-chapter-index="-1"><span class="chapter-list-number">第${pendingChapter.number}章</span><b class="chapter-list-title">${escapeHtml(pendingChapter.title)}</b><span class="pill orange">待确认</span></div>` : '';
  return `
    <main class="page writing-grid">
      <aside class="left-cards">
        <section class="card chapter-dir-card"><div class="section-title"><h2>章节目录</h2></div><div class="chapter-list">${chapterListItems}${pendingItem}</div></section>
        <section class="card guide-card" id="guide-card"><div class="section-title"><h2>本章写作指南</h2><button class="tiny-btn" data-action="editGuide">编辑</button></div><div class="guide-block"><b>本章目标</b><p>${escapeHtml(dp.goal)}</p></div><div class="guide-block"><b>视角安排</b><p>${escapeHtml(dp.pov)}</p></div><div class="guide-block"><b>角色站位</b><p>${roleEntries.map(([k, v]) => `${escapeHtml(k)} ${v}%`).join(' / ')}</p></div><div class="guide-block danger"><b>禁止事项</b><p>${(dp.forbidden || []).map(escapeHtml).join('；')}</p></div></section>
        <section class="card progress-card"><h2>章节进度</h2>${[['主线推进', project.status.mainProgress || 0, 'blue'], ['女主戏份', roleEntries.find(([k]) => k.includes('沈'))?.[1] || 35, 'pink'], ['伏笔风险', 28, 'orange'], ['偏离风险', project.status.deviationRisk * 100, 'mint']].map(([a, b, c]) => `<div class="metric-line"><b>${a}</b><span>${Math.round(b)}%</span>${progress(b, c)}</div>`).join('')}</section>
      </aside>
      <section class="card editor-card"><div class="chapter-head"><div><h1>第 ${chapter.number} 章 · ${escapeHtml(chapter.title)}</h1><p>视角：江离　时段：自动判断　字数：${number(chapter.wordCount)}</p></div><button class="circle-btn">···</button></div><article class="novel-text">${escapeHtml(chapter.text).split('\n').map((p) => p ? `<p>${p}</p>` : '<br/>').join('')}</article><div class="editor-footer"><span>字数统计：${number(chapter.wordCount)}</span><span>预计本章字数：${number(getState().settings.chapterWordTargetMin)} - ${number(getState().settings.chapterWordTargetMax)}</span><button class="tiny-btn">写作模式⌄</button></div><div class="chapter-actions"><button class="soft-btn" data-action="generateNextChapter">重写本章</button><button class="next-btn" data-action="generateNextChapter">✦ 生成下一章</button>${isPending ? `<button class="primary-btn" data-action="confirmChapter">确认本章入库</button>` : `<button class="soft-btn">继续写作</button>`}</div></section>
      <aside class="right-panel"><section class="card ai-director"><h2>AI 自动导演</h2><div class="preview-card"><h3>当前主线</h3><p>${escapeHtml(project.storyBible.mainConflict)}</p>${progress(project.status.mainProgress || 0, 'blue')}</div><div class="preview-card"><h3>下一转折</h3><p>系统将根据事件账本和伏笔风险自动安排下一次冲突或揭示。</p></div></section><section class="card risk-card"><h2>风险预警</h2><div class="ring-row"><div class="ring">28%<small>伏笔风险</small></div><div class="ring green">${Math.round(project.status.deviationRisk * 100)}%<small>偏离风险</small></div></div></section><section class="card"><h2>角色活跃度</h2>${project.characters.slice(0, 4).map((char) => `<div class="metric-line"><b>${escapeHtml(char.name)}</b><span>${Math.round((1 - char.dropoutRisk) * 100)}%</span>${progress((1 - char.dropoutRisk) * 100, 'pink')}</div>`).join('')}</section><section class="card"><h2>AI 质量评分</h2><div class="score-big">${(chapter.review && chapter.review.totalScore) || project.status.qualityScore}<small>/100</small></div>${((chapter.review && chapter.review.tests) || []).slice(0, 4).map((test) => `<div class="test-row"><span>${test.passed ? '✓' : '!'}</span><b>${escapeHtml(test.name)}</b><em>${test.score}/100</em></div>`).join('')}</section></aside>
      <section class="card state-delta"><h2>状态变化（本章结束后）</h2>${[['新增信息', (chapter.stateDelta && chapter.stateDelta.newForeshadows) || []], ['角色关系变化', (chapter.stateDelta && chapter.stateDelta.relationshipChanges) || []], ['事件更新', (chapter.stateDelta && chapter.stateDelta.eventUpdates) || []], ['时间线', (chapter.stateDelta && chapter.stateDelta.timeline) || []]].map(([title, list]) => `<div><h3>${title}</h3><ul>${list.length ? list.map((x) => `<li>${escapeHtml(x)}</li>`).join('') : '<li>等待生成后显示</li>'}</ul></div>`).join('')}</section>
    </main>
  `;
}

function renderStatusPage(project) {
  if (!project) return emptyProjectPanel();
  const chapter = project.chapters.at(-1);
  const tests = project.status.tests?.length ? project.status.tests : defaultTests();
  return `
    <main class="page status-page">
      <div class="page-head"><div><h1>状态面板 · 全局运行监控</h1><p>状态驱动、约束驱动、检查驱动的自动化监控中心。</p></div><div class="head-actions"><button class="primary-btn" data-action="analyzeState">重新分析状态</button><button class="soft-btn">生成检查报告</button><button class="soft-btn">锁定本章状态</button></div></div>
      <section class="kpi-row">${[['当前章节', chapter ? `第 ${chapter.number} 章 · ${chapter.title}` : '尚未生成', '字数：' + number(chapter?.wordCount), 'pink'], ['主线推进度', `${project.status.mainProgress || 0}%`, `已推进 ${Math.round((project.status.mainProgress || 0) / 2)} 个主线节点`, 'blue'], ['伏笔总数', project.foreshadows.length, `已记录 ${project.foreshadows.length} 条`, 'purple'], ['角色活跃数', project.characters.length, `活跃角色 / 总角色 ${project.characters.length} / ${project.characters.length + 18}`, 'orange'], ['偏离风险', formatPct(project.status.deviationRisk), '安全', 'mint'], ['AI 质量评分', `${project.status.qualityScore || 90}/100`, '优秀', 'blue']].map(([a, b, c, tone]) => `<div class="card kpi ${tone}"><h3>${a}</h3><strong>${escapeHtml(b)}</strong><small>${escapeHtml(c)}</small>${a.includes('推进') ? progress(project.status.mainProgress || 0, 'blue') : ''}</div>`).join('')}</section>
      <section class="status-grid"><div class="card ledger-panel"><div class="section-title"><h2>事件账本</h2><div><button class="tiny-btn">全部事件</button><button class="tiny-btn">全部角色</button></div></div><table><thead><tr><th>时间</th><th>场景</th><th>角色</th><th>事件</th><th>影响</th><th>可见性</th></tr></thead><tbody>${renderEventRows(project)}</tbody></table></div><div class="card truth-panel"><h2>真相源 / 信息层级</h2>${Object.entries(project.truthSource).map(([key, val]) => `<div class="metric-line"><b>${truthLabel(key)}</b><span>${val}%</span>${progress(val, key === 'misdirection' ? 'orange' : 'blue')}</div>`).join('')}</div><div class="card character-warning"><h2>角色活跃与掉线预警</h2>${project.characters.map((char) => `<div class="warning-row"><b>${escapeHtml(char.name)}</b><span>第 ${char.lastAppeared || '-'} 章</span><em class="${char.dropoutRisk > 0.5 ? 'danger-text' : ''}">${formatPct(char.dropoutRisk)}</em><small>建议第 ${(project.currentChapterNumber || 0) + 1} 章</small></div>`).join('')}</div><div class="card"><h2>伏笔生命周期</h2>${project.foreshadows.slice(-8).map((fb) => `<div class="list-row"><span class="dot-icon">✧</span><div><b>${escapeHtml(fb.name)}</b><small>埋下于第 ${fb.firstChapter} 章，计划第 ${fb.plannedPayoff} 章回收</small></div>${pill(fb.status, fb.risk > 0.5 ? 'red' : 'orange')}</div>`).join('')}</div><div class="card network-card"><h2>角色关系网络（核心）</h2><div class="network"><span class="node center">江离</span><span class="node n1">沈烁</span><span class="node n2">苏照</span><span class="node n3">夜烬</span><span class="node n4">女主线</span></div></div><div class="card test-panel"><h2>检查与测试（小说单元测试）</h2>${tests.map((test) => `<div class="test-row"><span>${test.passed ? '✓' : '!'}</span><b>${escapeHtml(test.name)}</b><em>${test.score}/100</em><small>${escapeHtml(test.note)}</small></div>`).join('')}</div></section>
    </main>
  `;
}

function renderLedgerPage(project) {
  if (!project) return emptyProjectPanel();
  const events = project.events.length ? project.events : defaultEvents();
  return `
    <main class="page ledger-page">
      <div class="page-head"><div><h1>事件账本 · 因果链追踪</h1><p>记录每个场景发生的事件、影响、可见性与角色知识边界，供下一章自动检索。</p></div><div class="head-actions"><button class="primary-btn">重建事件账本</button><button class="soft-btn">导出 CSV</button></div></div>
      <section class="ledger-split"><div class="card"><div class="section-title"><h2>事件时间线</h2><input class="input table-search" placeholder="搜索事件、角色、场景..." /></div><table><thead><tr><th>时间</th><th>场景</th><th>角色</th><th>事件</th><th>影响</th><th>可见性</th></tr></thead><tbody>${events.map((evt) => `<tr><td>${escapeHtml(evt.time || `第${evt.chapter}章`)}</td><td>${escapeHtml(evt.scene)}</td><td>${escapeHtml(evt.characters)}</td><td>${escapeHtml(evt.event)}</td><td>${escapeHtml(evt.impact)}</td><td>${escapeHtml(evt.visibility)}</td></tr>`).join('')}</tbody></table></div><aside class="card"><h2>因果链摘要</h2>${events.slice(-6).map((evt, i) => `<div class="timeline-item"><span>${i + 1}</span><div><b>${escapeHtml(evt.event)}</b><small>${escapeHtml(evt.impact)} / ${escapeHtml(evt.visibility)}</small></div></div>`).join('')}<div class="preview-card warm"><h3>自动用途</h3><p>下一章生成时，记忆检索 Agent 会优先读取事件账本，而不是只读取全文，降低逻辑断层。</p></div></aside></section>
    </main>
  `;
}

function renderMemoryPage(project) {
  if (!project) return emptyProjectPanel();
  const latestSummaries = project.chapters.slice(-5).map((ch) => `第${ch.number}章：${ch.title} · ${ch.stateDelta.eventUpdates?.[0] || '状态已更新'}`);
  const memoryPacks = [
    ['故事蓝图记忆', 'Story Bible、分卷规划、写作风格、禁令规则', 100, 'blue'],
    ['角色状态记忆', '角色目标、关系、知识边界、掉线风险', 86, 'pink'],
    ['伏笔真相记忆', '伏笔生命周期、真相源、误导路径', 78, 'orange'],
    ['事件账本记忆', '场景事件、因果影响、可见性', 92, 'mint']
  ];
  return `
    <main class="page memory-page">
      <div class="page-head"><div><h1>全局记忆 · 自动上下文中心</h1><p>管理每次生成前需要检索的状态包、摘要包、向量记忆与状态快照。</p></div><div class="head-actions"><button class="primary-btn">重建全局记忆</button><button class="soft-btn">压缩历史正文</button></div></div>
      <section class="memory-grid">${memoryPacks.map(([a,b,c,t]) => `<div class="card memory-pack"><h2>${a}</h2><p>${b}</p><div class="metric-line"><b>可用度</b><span>${c}%</span>${progress(c, t)}</div></div>`).join('')}</section>
      <section class="memory-layout"><div class="card"><h2>下一章上下文包预览</h2><div class="context-stack">${['当前卷大纲', '最近 3 章摘要', '本章相关角色卡', '高风险伏笔', '角色知识边界', '用户临时指令', '风格约束', '禁止事项'].map((x) => `<span>${x}</span>`).join('')}</div><div class="preview-card"><h3>Token 控制策略</h3><p>优先使用结构化状态和摘要；正文片段只在相关度高时检索，防止 DeepSeek 输入过长导致超时。</p></div></div><div class="card"><h2>章节摘要记忆</h2>${latestSummaries.length ? latestSummaries.map((x) => `<div class="list-row"><span class="dot-icon">✓</span><div><b>${escapeHtml(x)}</b><small>已写入章节摘要库</small></div></div>`).join('') : '<p class="muted">暂无章节摘要，生成并确认章节后自动写入。</p>'}</div><div class="card"><h2>状态快照</h2>${[0, 1, 2, 3].map((_, i) => `<div class="title-row"><span>Snapshot #${i + 1}</span><b>第 ${Math.max(0, project.currentChapterNumber - i)} 章状态</b></div>`).join('')}</div></section>
    </main>
  `;
}

function renderGenerationSettingsPage(state) {
  const s = state.settings;
  return `
    <main class="page generation-page">
      <div class="page-head"><div><h1>生成设置 · 自动化流水线</h1><p>配置一键生成下一章背后的 Agent 流程、质量阈值、字数、重写次数与 DeepSeek 上下限。</p></div></div>
      <form id="generation-settings-form" class="card settings-form">
        <div class="settings-grid">
          <label><span>Mock 模式</span><select name="mockMode" class="select"><option value="true" ${s.mockMode ? 'selected' : ''}>开启：不用后端也能演示</option><option value="false" ${!s.mockMode ? 'selected' : ''}>关闭：连接本地后端</option></select></label>
          <label><span>生成模式</span><select name="generationMode" class="select"><option value="fast" ${s.generationMode === 'fast' ? 'selected' : ''}>快速模式</option><option value="standard" ${s.generationMode === 'standard' ? 'selected' : ''}>标准模式</option><option value="strict" ${s.generationMode === 'strict' ? 'selected' : ''}>严格模式</option></select></label>
          <label><span>质量阈值</span><input class="input" name="qualityThreshold" type="number" min="50" max="100" value="${s.qualityThreshold}" /></label>
          <label><span>自动重写次数</span><input class="input" name="autoRewriteTimes" type="number" min="0" max="5" value="${s.autoRewriteTimes}" /></label>
          <label><span>单章最少字数</span><input class="input" name="chapterWordTargetMin" type="number" value="${s.chapterWordTargetMin}" /></label>
          <label><span>单章最多字数</span><input class="input" name="chapterWordTargetMax" type="number" value="${s.chapterWordTargetMax}" /></label>
          <label><span>最大输入 Tokens</span><input class="input" name="maxInputTokens" type="number" value="${s.maxInputTokens}" /></label>
          <label><span>最大输出 Tokens</span><input class="input" name="maxOutputTokens" type="number" value="${s.maxOutputTokens}" /></label>
        </div>
        <h2>Agent 开关</h2>
        <div class="agent-grid">${agentList(s).map((agent) => `<label class="toggle-card"><input type="checkbox" name="agent_${agent.key}" ${agent.enabled ? 'checked' : ''} /><span>${agent.name}</span><small>${agent.desc}</small></label>`).join('')}</div>
        <div class="head-actions form-actions"><button class="primary-btn" type="submit">保存生成设置</button><button class="soft-btn" type="button" data-action="resetDemo">清空本地演示数据</button></div>
      </form>
      <section class="card callout"><h2>超时与上限建议</h2><ul class="doc-list"><li>正文生成建议走后端任务队列或流式返回，前端不要直接长时间等待。</li><li>章节写作使用较高输出上限；检查、状态提取使用较低温度和严格 JSON。</li><li>输入上下文应优先使用摘要和结构化状态，不要每章塞入全书正文。</li></ul></section>
    </main>
  `;
}

function agentList(settings) {
  const enabled = settings.agentSwitches || {};
  return [
    ['memory', '记忆检索 Agent', '检索蓝图、角色、伏笔、事件'],
    ['constraint', '约束生成 Agent', '生成必须/禁止/建议事项'],
    ['director', '章节导演 Agent', '生成分镜与小纲'],
    ['character', '角色导演 Agent', '控制角色主动性与戏份'],
    ['foreshadow', '伏笔管理 Agent', '处理回响和回收计划'],
    ['writer', '正文写作 Agent', '生成章节正文'],
    ['review', '检查修正 Agent', '连续性、风格、伏笔检查'],
    ['state', '状态更新 Agent', '提取状态变化并合并']
  ].map(([key, name, desc]) => ({ key, name, desc, enabled: enabled[key] !== false }));
}

function renderModelConfigPage(state) {
  const s = state.settings;
  const routes = s.modelRoutes || defaultModelRoutes();
  return `
    <main class="page models-page">
      <div class="page-head"><div><h1>模型配置 · 任务路由</h1><p>不同 Agent 可以使用不同模型、温度、输出上限和降级策略，降低成本并减少超时。</p></div><div class="head-actions"><button class="primary-btn">测试模型连通性</button><button class="soft-btn">恢复推荐配置</button></div></div>
      <form id="model-settings-form" class="card settings-form">
        <div class="settings-grid">
          <label><span>主写作模型</span><select name="writingModel" class="select">${modelOptions(s.writingModel)}</select></label>
          <label><span>规划/检查模型</span><select name="reviewModel" class="select">${modelOptions(s.reviewModel)}</select></label>
          <label><span>备用模型</span><select name="fallbackModel" class="select">${modelOptions(s.fallbackModel)}</select></label>
          <label><span>Embedding 模型</span><input name="embeddingModel" class="input" value="${escapeHtml(s.embeddingModel)}" /></label>
          <label><span>正文温度</span><input name="temperatureWriting" class="input" type="number" step="0.1" value="${s.temperatureWriting}" /></label>
          <label><span>检查温度</span><input name="temperatureReview" class="input" type="number" step="0.1" value="${s.temperatureReview}" /></label>
        </div>
        <h2>Agent 任务路由表</h2>
        <div class="model-table">${routes.map((r, index) => `<div class="model-row"><b>${escapeHtml(r.task)}</b><span>${escapeHtml(r.model)}</span><em>温度 ${r.temperature}</em><small>输出 ${number(r.maxOutputTokens)} tokens</small><i>${escapeHtml(r.fallback)}</i><input type="hidden" name="route_${index}" value="${escapeHtml(JSON.stringify(r))}" /></div>`).join('')}</div>
        <div class="head-actions form-actions"><button class="primary-btn" type="submit">保存模型配置</button></div>
      </form>
      <section class="card callout"><h2>推荐策略</h2><p class="muted">正文写作可用强写作模型；检查、状态提取、约束生成优先低温度；长文本检索使用本地摘要 + Embedding，避免把全书正文直接塞进模型。</p></section>
    </main>
  `;
}

function modelOptions(selected) {
  return ['deepseek-chat', 'deepseek-reasoner', 'deepseek-fast', 'qwen-long', 'gpt-5.1', 'gemini-pro', 'claude-sonnet', 'custom'].map((m) => `<option value="${m}" ${selected === m ? 'selected' : ''}>${m}</option>`).join('');
}

function defaultModelRoutes() {
  return [
    { task: '大纲补全', model: 'deepseek-reasoner', temperature: 0.6, maxOutputTokens: 12000, fallback: 'deepseek-chat' },
    { task: '章节导演', model: 'deepseek-chat', temperature: 0.5, maxOutputTokens: 6000, fallback: 'deepseek-fast' },
    { task: '正文写作', model: 'deepseek-chat', temperature: 0.9, maxOutputTokens: 16000, fallback: 'deepseek-chat' },
    { task: '连续性检查', model: 'deepseek-reasoner', temperature: 0.2, maxOutputTokens: 6000, fallback: 'deepseek-chat' },
    { task: '状态提取 JSON', model: 'deepseek-chat', temperature: 0.1, maxOutputTokens: 5000, fallback: 'deepseek-fast' }
  ];
}

function renderDeepSeekPage(state) {
  const s = state.settings;
  return `
    <main class="page deepseek-page">
      <div class="page-head"><div><h1>DeepSeek API 设置</h1><p>本页为桌面软件的本地 API 配置界面。正式接入时建议由本地后端保存 Key，前端只发请求到 127.0.0.1。</p></div><div class="head-actions"><button class="primary-btn">连接测试</button><button class="soft-btn">查看请求日志</button></div></div>
      <section class="api-status card"><div><h2>连接状态</h2><p>${s.mockMode ? 'Mock 模式运行中，暂未连接真实 DeepSeek。' : '将连接本地后端，由后端代理 DeepSeek 请求。'}</p></div>${pill(s.mockMode ? '演示模式' : '后端模式', s.mockMode ? 'orange' : 'mint')}</section>
      <form id="deepseek-form" class="card settings-form">
        <div class="settings-grid">
          <label><span>本地后端地址</span><input class="input" name="backendBaseUrl" value="${escapeHtml(s.backendBaseUrl)}" /></label>
          <label><span>DeepSeek Base URL</span><input class="input" name="deepseekBaseUrl" value="${escapeHtml(s.deepseekBaseUrl)}" /></label>
          <label><span>API Key 状态</span><input class="input" name="deepseekApiKey" type="password" placeholder="${s.deepseekApiKeySet ? '已保存到本机配置，重新输入可覆盖' : '输入 API Key，后端阶段会改为安全保存'}" /></label>
          <label><span>主模型名</span><input class="input" name="deepseekMainModel" value="${escapeHtml(s.deepseekMainModel)}" /></label>
          <label><span>快速模型名</span><input class="input" name="deepseekFastModel" value="${escapeHtml(s.deepseekFastModel)}" /></label>
          <label><span>请求超时 ms</span><input class="input" name="requestTimeoutMs" type="number" value="${s.requestTimeoutMs}" /></label>
          <label><span>失败重试次数</span><input class="input" name="retryTimes" type="number" value="${s.retryTimes}" /></label>
          <label><span>流式响应</span><select class="select" name="streaming"><option value="true" ${s.streaming ? 'selected' : ''}>开启：建议正文生成使用</option><option value="false" ${!s.streaming ? 'selected' : ''}>关闭：仅短任务使用</option></select></label>
        </div>
        <div class="head-actions form-actions"><button class="primary-btn" type="submit">保存 DeepSeek 设置</button></div>
      </form>
      <section class="card callout"><h2>给 Trae 的重点</h2><ul class="doc-list"><li>不要让前端直接请求 DeepSeek 官方接口，避免暴露 Key。</li><li>后端要支持任务式生成：创建任务、查询进度、流式输出、失败重试。</li><li>遇到超时先降低 maxOutputTokens 或改成分场景生成，不要无限等待。</li></ul></section>
    </main>
  `;
}

function defaultTests() {
  return [
    { name: '连续性检查', passed: true, score: 98, note: '情节衔接良好' },
    { name: '视角稳定性', passed: true, score: 96, note: '视角切换自然' },
    { name: '女主主动性', passed: true, score: 88, note: '符合设定强度' },
    { name: '时间线一致性', passed: true, score: 97, note: '无时间线冲突' },
    { name: '禁止揭露检查', passed: true, score: 100, note: '无超前泄露' },
    { name: 'AI 味检测', passed: true, score: 91, note: 'AI 痕迹低' }
  ];
}

function defaultEvents() {
  return [
    { time: '第1章 00:12', scene: '开场', characters: '江离', event: '主角获得第一条旧案线索', impact: '推进主线', visibility: '主角/读者' },
    { time: '第1章 00:45', scene: '街口', characters: '沈烁', event: '女主独自追查可疑人物', impact: '角色行动', visibility: '读者' },
    { time: '第1章 01:21', scene: '书房', characters: '苏照', event: '配角隐瞒关键身份', impact: '埋下伏笔', visibility: '读者' }
  ];
}

function truthLabel(key) {
  return ({ authorTruth: '作者真相', readerKnown: '读者已知', protagonistKnown: '主角已知', femaleLeadKnown: '女主已知', misdirection: '误导信息' })[key] || key;
}

function renderEventRows(project) {
  const events = (project.events.length ? project.events : defaultEvents()).slice(-10);
  return events.map((evt) => `<tr><td>${escapeHtml(evt.time || `第${evt.chapter}章`)}</td><td>${escapeHtml(evt.scene)}</td><td>${escapeHtml(evt.characters)}</td><td>${escapeHtml(evt.event)}</td><td>${escapeHtml(evt.impact)}</td><td>${escapeHtml(evt.visibility)}</td></tr>`).join('');
}

function renderMain(state, project) {
  const route = state.activeRoute;
  if (route === 'project') return renderProjectPage(project);
  if (route === 'create') return renderCreatePage();
  if (route === 'blueprint') return renderBlueprintPage(project);
  if (route === 'characters') return renderCharactersPage(project);
  if (route === 'truth') return renderTruthPage(project);
  if (route === 'writing') return renderWritingPage(project, state.pendingChapter, state);
  if (route === 'status') return renderStatusPage(project);
  if (route === 'ledger') return renderLedgerPage(project);
  if (route === 'memory') return renderMemoryPage(project);
  if (route === 'generation') return renderGenerationSettingsPage(state);
  if (route === 'models') return renderModelConfigPage(state);
  if (route === 'deepseek') return renderDeepSeekPage(state);
  return project ? renderProjectPage(project) : renderCreatePage();
}

function render() {
  const state = getState();
  const project = getProject(state);

  // 构建流式进度提示
  let streamHtml = '';
  if (streamProgress) {
    const agentLabel = streamProgress.agent ? `当前 Agent: ${streamProgress.agent}` : '';
    const textPreview = streamProgress.text ? `<p class="stream-text-preview">${escapeHtml(streamProgress.text.slice(-80))}</p>` : '';
    const rewriteHtml = streamProgress.rewriteAttempt
      ? `<p class="stream-rewrite">第 ${streamProgress.rewriteAttempt} 次重写中，原因：${escapeHtml(streamProgress.rewriteReason)}</p>`
      : '';
    streamHtml = `<div class="busy"><div class="spinner"></div><b>${escapeHtml(busyText)}</b>${agentLabel ? `<p>${escapeHtml(agentLabel)}</p>` : ''}${rewriteHtml}${textPreview}<p>自动化流程运行中，请勿关闭程序。</p></div>`;
  } else if (busyText) {
    streamHtml = `<div class="busy"><div class="spinner"></div><b>${escapeHtml(busyText)}</b><p>自动化流程运行中，请勿关闭程序。</p></div>`;
  }

  app.innerHTML = `
    <div class="shell">
      ${renderSidebar(state, project)}
      <div class="workspace">${renderTopbar(state, project)}${renderMain(state, project)}</div>
      ${streamHtml}
      ${toast ? `<div class="toast ${toast.tone}">${escapeHtml(toast.message)}</div>` : ''}
    </div>
  `;
}

app.addEventListener('click', async (event) => {
  const routeButton = event.target.closest('[data-route]');
  if (routeButton) {
    setActiveRoute(routeButton.dataset.route);
    return;
  }

  const actionButton = event.target.closest('[data-action]');
  if (!actionButton) return;

  const action = actionButton.dataset.action;
  const state = getState();
  const project = getProject(state);

  if (action === 'generateNextChapter') {
    if (!project) return showToast('请先创建项目', 'error');
    busyText = 'AI 正在生成下一章：检索记忆、生成导演稿、写正文、检查与修正……';
    streamProgress = { agent: '', text: '', rewriteAttempt: 0, rewriteReason: '' };
    render();
    try {
      const chapter = await api.generateNextChapterStream(project.id, {}, (event) => {
        // 处理流式事件
        if (event.type === 'agent_start') {
          streamProgress.agent = event.agent;
          render();
        } else if (event.type === 'agent_progress') {
          streamProgress.agent = event.agent;
          streamProgress.text = event.text || '';
          render();
        } else if (event.type === 'agent_done') {
          streamProgress.agent = event.agent;
          streamProgress.text = '';
          render();
        } else if (event.type === 'rewrite') {
          streamProgress.rewriteAttempt = event.attempt;
          streamProgress.rewriteReason = event.reason;
          render();
        } else if (event.type === 'chapter_done') {
          // 章节完成，更新 store
          if (event.chapter) {
            setPendingChapter(event.chapter);
          }
        }
      });
      streamProgress = null;
      busyText = '';
      render();
      showToast('下一章已生成，确认后才会写入状态库。');
    } catch (error) {
      streamProgress = null;
      busyText = '';
      render();
      showToast(toUserError(error), 'error');
    }
  }

  if (action === 'confirmChapter') {
    if (!project || !state.pendingChapter) return showToast('没有待确认章节', 'error');
    await runTask('正在确认章节并合并状态……', () => api.confirmChapter(project.id, state.pendingChapter.id));
    showToast('本章已确认，事件账本和状态库已更新。');
  }

  if (action === 'regenerateBlueprint') {
    if (!project) return showToast('请先创建项目', 'error');
    await runTask('AI 正在重新扩写故事蓝图……', () => api.regenerateBlueprint(project.id));
    showToast('故事蓝图已重新扩写。');
  }

  if (action === 'analyzeState') {
    if (!project) return showToast('请先创建项目', 'error');
    const result = await runTask('正在分析全局状态和风险……', () => api.analyzeState(project.id));
    showToast(result.report?.summary || '状态分析完成。');
  }

  if (action === 'resetDemo') {
    resetDemoData();
    showToast('本地演示数据已清空。');
  }

  if (action === 'editGuide') {
    const guideCard = document.querySelector('#guide-card');
    if (!guideCard) return;
    const state = getState();
    const project = getProject(state);
    if (!project) return;
    const viewingIndex = state.viewingChapterIndex;
    let chapter;
    if (state.pendingChapter && (viewingIndex === -1 || viewingIndex >= project.chapters.length)) {
      chapter = state.pendingChapter;
    } else if (viewingIndex >= 0 && viewingIndex < project.chapters.length) {
      chapter = project.chapters[viewingIndex];
    } else {
      chapter = project.chapters.at(-1);
    }
    if (!chapter) return;
    const roleEntries = Object.entries(chapter.directorPlan.roleFocus || {});
    const guideText = [
      `【本章目标】\n${chapter.directorPlan.goal || ''}`,
      `【视角安排】\n${chapter.directorPlan.pov || ''}`,
      `【角色站位】\n${roleEntries.map(([k, v]) => `${k} ${v}%`).join(' / ')}`,
      `【禁止事项】\n${(chapter.directorPlan.forbidden || []).join('；')}`
    ].join('\n\n');
    guideCard.querySelector('.section-title').innerHTML = '<h2>本章写作指南</h2>';
    guideCard.querySelector('.section-title').insertAdjacentHTML('beforeend', '<button class="tiny-btn" data-action="saveGuide">保存</button><button class="tiny-btn" data-action="cancelGuide">取消</button>');
    const guideContent = guideCard.querySelectorAll('.guide-block');
    guideContent.forEach((el) => el.style.display = 'none');
    const textarea = document.createElement('textarea');
    textarea.className = 'textarea guide-textarea';
    textarea.value = guideText;
    guideCard.appendChild(textarea);
    textarea.focus();
  }

  if (action === 'saveGuide') {
    const guideCard = document.querySelector('#guide-card');
    if (!guideCard) return;
    const textarea = guideCard.querySelector('.guide-textarea');
    if (!textarea) return;
    const raw = textarea.value;
    const parseSection = (text, label) => {
      const regex = new RegExp(`【${label}】\\s*([\\s\\S]*?)(?=【|$)`);
      const match = raw.match(regex);
      return match ? match[1].trim() : '';
    };
    const goal = parseSection(raw, '本章目标');
    const pov = parseSection(raw, '视角安排');
    const roleFocusRaw = parseSection(raw, '角色站位');
    const forbiddenRaw = parseSection(raw, '禁止事项');
    const roleFocus = {};
    roleFocusRaw.split('/').forEach((part) => {
      const m = part.trim().match(/^(.+?)\s+(\d+)%$/);
      if (m) roleFocus[m[1].trim()] = Number(m[2]);
    });
    const forbidden = forbiddenRaw.split(/[；;]/).map((s) => s.trim()).filter(Boolean);
    const state = getState();
    const project = getProject(state);
    if (!project) return;
    const viewingIndex = state.viewingChapterIndex;
    const isPending = state.pendingChapter && (viewingIndex === -1 || viewingIndex >= project.chapters.length);
    const newPlan = { goal, pov, roleFocus, forbidden };
    if (isPending) {
      updateState((s) => {
        if (s.pendingChapter) {
          s.pendingChapter.directorPlan = newPlan;
        }
        return s;
      });
    } else {
      const chapterIdx = viewingIndex >= 0 && viewingIndex < project.chapters.length ? viewingIndex : project.chapters.length - 1;
      if (chapterIdx >= 0) {
        updateProject(project.id, (p) => {
          if (p.chapters[chapterIdx]) {
            p.chapters[chapterIdx].directorPlan = newPlan;
          }
          return p;
        });
      }
    }
    showToast('写作指南已保存。');
  }

  if (action === 'cancelGuide') {
    render();
  }

  if (action === 'selectChapter') {
    const index = parseInt(actionButton.dataset.chapterIndex, 10);
    setViewingChapterIndex(index);
  }

  if (action === 'showProjectList') {
    const dropdown = document.querySelector('#project-dropdown');
    if (dropdown) {
      dropdown.classList.toggle('visible');
    }
  }

  if (action === 'switchProject') {
    const projectId = actionButton.dataset.projectId;
    if (projectId) {
      setCurrentProject(projectId);
      showToast('已切换项目。');
    }
  }

  if (action === 'deleteProject') {
    const projectId = actionButton.dataset.projectId;
    if (projectId) {
      event.stopPropagation();
      const state = getState();
      const project = state.projects.find((p) => p.id === projectId);
      const title = project ? project.title || '未命名项目' : '该项目';
      if (confirm(`确定要删除《${title}》吗？此操作不可撤销。`)) {
        deleteProject(projectId);
        showToast('项目已删除。');
      }
    }
  }
});

app.addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.target;

  if (form.id === 'create-form') {
    const data = new FormData(form);
    const payload = {
      title: String(data.get('title') || ''),
      outline: String(data.get('outline') || ''),
      genre: String(data.get('genre') || '奇幻'),
      lengthType: String(data.get('lengthType') || 'long'),
      mode: String(data.get('mode') || 'balanced')
    };
    const result = await runTask('AI 正在自动构建小说：补全大纲、分卷规划、角色系统、伏笔与真相源……', async () => {
      const created = await api.createProject(payload);
      await api.buildProject(created.project.id);
      return created;
    });
    showToast(`《${result.project.title}》已创建完成。`);
  }

  if (form.id === 'generation-settings-form') {
    const data = new FormData(form);
    const switches = {};
    agentList(getState().settings).forEach((agent) => {
      switches[agent.key] = data.get(`agent_${agent.key}`) === 'on';
    });
    setSettings({
      mockMode: data.get('mockMode') === 'true',
      generationMode: String(data.get('generationMode') || 'standard'),
      qualityThreshold: Number(data.get('qualityThreshold') || 85),
      autoRewriteTimes: Number(data.get('autoRewriteTimes') || 2),
      chapterWordTargetMin: Number(data.get('chapterWordTargetMin') || 5000),
      chapterWordTargetMax: Number(data.get('chapterWordTargetMax') || 8000),
      maxInputTokens: Number(data.get('maxInputTokens') || 64000),
      maxOutputTokens: Number(data.get('maxOutputTokens') || 12000),
      agentSwitches: switches
    });
    showToast('生成设置已保存。');
  }

  if (form.id === 'model-settings-form') {
    const data = new FormData(form);
    setSettings({
      writingModel: String(data.get('writingModel') || 'deepseek-chat'),
      reviewModel: String(data.get('reviewModel') || 'deepseek-reasoner'),
      fallbackModel: String(data.get('fallbackModel') || 'deepseek-chat'),
      embeddingModel: String(data.get('embeddingModel') || 'BAAI/bge-m3'),
      temperatureWriting: Number(data.get('temperatureWriting') || 0.9),
      temperatureReview: Number(data.get('temperatureReview') || 0.2)
    });
    showToast('模型配置已保存。');
  }

  if (form.id === 'deepseek-form') {
    const data = new FormData(form);
    const apiKey = String(data.get('deepseekApiKey') || '').trim();
    setSettings({
      backendBaseUrl: String(data.get('backendBaseUrl') || 'http://127.0.0.1:8765'),
      deepseekBaseUrl: String(data.get('deepseekBaseUrl') || 'https://api.deepseek.com'),
      deepseekMainModel: String(data.get('deepseekMainModel') || 'deepseek-chat'),
      deepseekFastModel: String(data.get('deepseekFastModel') || 'deepseek-chat'),
      requestTimeoutMs: Number(data.get('requestTimeoutMs') || 120000),
      retryTimes: Number(data.get('retryTimes') || 1),
      streaming: data.get('streaming') === 'true',
      deepseekApiKeySet: apiKey ? true : getState().settings.deepseekApiKeySet
    });
    showToast(apiKey ? 'DeepSeek 设置已保存，API Key 状态已更新。' : 'DeepSeek 设置已保存。');
  }
});

document.addEventListener('click', (event) => {
  const dropdown = document.querySelector('#project-dropdown');
  if (dropdown && dropdown.classList.contains('visible')) {
    const wrapper = event.target.closest('.project-select-wrapper');
    if (!wrapper) {
      dropdown.classList.remove('visible');
    }
  }
});

subscribe(render);
render();
