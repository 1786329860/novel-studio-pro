from __future__ import annotations

import json
from typing import Any


# ======================================================================
# 原有 Prompt 模板（保留向后兼容）
# ======================================================================

def build_outline_expansion_prompt(project: dict[str, Any]) -> list[dict[str, str]]:
    payload = {
        "title": project.get("title"),
        "outline": project.get("outline"),
        "genre": project.get("genre"),
        "lengthType": project.get("lengthType"),
        "mode": project.get("mode"),
    }
    return [
        {
            "role": "system",
            "content": (
                "你是强自动化长篇小说创作引擎的故事蓝图 Agent。\n"
                "用户只提供小说名和粗略大纲，你必须自动生成完整故事蓝图。\n"
                "你必须输出严格 JSON，不要写任何解释文字。\n\n"
                "## JSON 结构要求\n\n"
                "{\n"
                '  "storyBible": {\n'
                '    "corePremise": "核心命题（50-100字，故事的核心主题和哲学思考）",\n'
                '    "mainTheme": "主题（20-40字）",\n'
                '    "mainConflict": "主线冲突（50-100字，核心矛盾和冲突）",\n'
                '    "endingDirection": "结局方向（30-60字，预期的结局走向）",\n'
                '    "style": "写作风格描述（20-40字）",\n'
                '    "genre": "题材类型",\n'
                '    "forbiddenRules": ["禁止提前揭露的规则1", "规则2", "规则3"],\n'
                '    "styleProfile": "文风画像（30-60字，描述叙事风格、语言特点）"\n'
                "  },\n\n"
                '  "volumePlan": [\n'
                '    {"name": "卷名", "range": "1-20章", "objective": "本卷目标（30-50字）", "turningPoint": "本卷转折点（30-50字）", "tone": "基调", "status": "planned", "coverGradient": "linear-gradient(135deg, #667eea, #764ba2)"}\n'
                "  ],\n\n"
                '  "stagePlan": [\n'
                '    {"name": "阶段名", "chapterRange": "1-10章", "description": "阶段描述（20-40字）", "keyEvents": "关键事件描述"}\n'
                "  ],\n\n"
                '  "chapterTitlePreview": [\n'
                '    {"number": 1, "title": "章节标题（6-12字）"}\n'
                "  ],\n\n"
                '  "characters": [\n'
                '    {\n'
                '      "id": "char_1",\n'
                '      "name": "角色全名",\n'
                '      "role": "主角/女主/男主/反派/配角/导师",\n'
                '      "personality": "性格描述（30-60字）",\n'
                '      "background": "背景故事（50-100字）",\n'
                '      "currentGoal": "当前目标（20-40字）",\n'
                '      "hiddenGoal": "隐藏目标（20-40字，可选）",\n'
                '      "emotion": "当前情绪",\n'
                '      "agencyScore": 0.7,\n'
                '      "dropoutRisk": 0.2,\n'
                '      "speakingStyle": "说话风格（20-40字）",\n'
                '      "lastAppearedChapter": 0,\n'
                '      "knowledgeState": ["已知信息1", "已知信息2"]\n'
                "    }\n"
                "  ],\n\n"
                '  "relationships": [\n'
                '    {"from": "角色A", "to": "角色B", "type": "关系类型（如：恋人/对手/师徒/朋友）", "description": "关系描述（20-40字）", "trust": 50, "tension": 30, "tone": "pink/blue/orange/mint"}\n'
                "  ],\n\n"
                '  "foreshadows": [\n'
                '    {\n'
                '      "id": "fs_1",\n'
                '      "name": "伏笔名称（10-20字）",\n'
                '      "description": "伏笔描述（30-60字）",\n'
                '      "status": "planted",\n'
                '      "plantedChapter": 1,\n'
                '      "lastMentionedChapter": 1,\n'
                '      "plannedPayoffChapter": 30,\n'
                '      "importance": "high",\n'
                '      "risk": 0.3,\n'
                '      "nextAction": "下一步处理建议"\n'
                "    }\n"
                "  ],\n\n"
                '  "truthSource": {\n'
                '    "ultimateTruth": "最终真相（50-100字）",\n'
                '    "revealPace": "揭示节奏描述",\n'
                '    "forbiddenReveals": ["禁止提前揭露的内容1", "内容2"]\n'
                "  },\n\n"
                '  "status": {\n'
                '    "mainProgress": 0,\n'
                '    "qualityScore": 85,\n'
                '    "deviationRisk": 0.1,\n'
                '    "dropoutRisk": 0.1,\n'
                '    "tests": []\n'
                "  },\n\n"
                '  "memory": {\n'
                '    "chapterSummaries": [],\n'
                '    "stateSnapshots": []\n'
                "  }\n"
                "}\n\n"
                "## 关键规则\n"
                "1. 角色数量根据大纲复杂度决定，至少4个，最多12个。除了大纲明确提到的角色外，你必须根据故事需要推断并创建：\n"
                "   - 反派/对手角色（如果大纲涉及冲突对抗）\n"
                "   - 关键配角（推动剧情或揭示信息所需的角色）\n"
                "   - 导师/引路人角色（如果大纲涉及成长线）\n"
                "   每个新增角色都必须有存在的叙事必要性，不能为了凑数而创建\n"
                "2. 每个角色必须有完整的 personality、background、currentGoal\n"
                "3. agencyScore 范围 0.0-1.0，dropoutRisk 范围 0.0-1.0\n"
                "4. 伏笔数量根据大纲复杂度决定，至少3个，最多8个\n"
                "5. plannedPayoffChapter 必须是具体的数字，不能是 undefined\n"
                "6. 分卷规划根据 lengthType 决定：short=2-3卷，medium=3-5卷，long=4-6卷\n"
                "7. chapterTitlePreview 至少生成 20 个章节标题\n"
                "8. forbiddenRules 至少 3 条\n"
                "9. 所有描述必须基于用户提供的大纲，不能凭空编造与大纲无关的内容\n"
                "10. 角色名应优先从用户大纲中提取。如果大纲过于简陋（如只有男女主），你必须根据故事类型和冲突需要，合理推断并创建故事必需的配角和反派角色，赋予完整的性格、背景和目标"
            ),
        },
        {
            "role": "user",
            "content": (
                "请根据以下输入生成完整项目初始化数据。\n\n"
                f"输入如下：\n{json.dumps(payload, ensure_ascii=False)}"
            ),
        },
    ]


def build_chapter_generation_prompt(project: dict[str, Any], options: dict[str, Any]) -> list[dict[str, str]]:
    context = {
        "title": project.get("title"),
        "storyBible": project.get("storyBible"),
        "volumePlan": project.get("volumePlan"),
        "status": project.get("status"),
        "characters": project.get("characters", [])[:8],
        "foreshadows": project.get("foreshadows", [])[:12],
        "truthSource": project.get("truthSource"),
        "recentChapters": project.get("chapters", [])[-3:],
        "userInstruction": options.get("userInstruction", ""),
    }
    return [
        {
            "role": "system",
            "content": (
                "你是小说自动导演系统。你必须完成：约束生成、章节导演、正文写作、检查、状态提取。"
                "必须输出严格 JSON，不要写 Markdown。"
                "JSON 顶层必须包含 chapter。chapter 内必须包含 id, number, title, status, wordCount, "
                "directorPlan, text, review, stateDelta。status 固定为 pending。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请基于以下当前项目状态生成下一章。注意：不要提前揭露 forbiddenRules 中禁止揭露的信息；"
                "控制输出长度；若上下文不足，优先保持逻辑一致。\n"
                f"{json.dumps(context, ensure_ascii=False)}"
            ),
        },
    ]


# ======================================================================
# 多 Agent 系统 Prompt 模板
# ======================================================================

def build_constraint_prompt(project: dict[str, Any]) -> list[dict[str, str]]:
    """约束生成 Agent 的 Prompt。

    角色: 小说自动化创作系统的【约束生成 Agent】
    任务: 分析当前项目状态，为即将写作的下一章生成精确的约束条件。

    Args:
        project: 完整的项目数据

    Returns:
        消息列表
    """
    story_bible = project.get("storyBible", {})
    forbidden_rules = story_bible.get("forbiddenRules", [])

    context = {
        "title": project.get("title", ""),
        "genre": story_bible.get("genre", ""),
        "currentChapter": len(project.get("chapters", [])),
        "mainTheme": story_bible.get("mainTheme", ""),
        "mainConflict": story_bible.get("mainConflict", ""),
        "forbiddenRules": forbidden_rules,
        "characters": [
            {
                "name": c.get("name", ""),
                "role": c.get("role", ""),
                "currentGoal": c.get("currentGoal", ""),
                "emotion": c.get("emotion", ""),
                "agencyScore": c.get("agencyScore", 0),
                "dropoutRisk": c.get("dropoutRisk", 0),
                "lastAppearedChapter": c.get("lastAppearedChapter", c.get("lastAppeared", 0)),
            }
            for c in project.get("characters", [])[:8]
        ],
        "foreshadows": [
            {
                "id": f.get("id", ""),
                "name": f.get("name", ""),
                "status": f.get("status", ""),
                "importance": f.get("importance", ""),
                "risk": f.get("risk", 0),
                "plannedPayoffChapter": f.get("plannedPayoffChapter", f.get("plannedPayoff", 999)),
                "nextAction": f.get("nextAction", ""),
            }
            for f in project.get("foreshadows", [])[:10]
        ],
        "truthSource": project.get("truthSource", {}),
        "recentEvents": project.get("events", [])[-8:],
        "relationships": project.get("relationships", [])[:6],
    }

    system_prompt = (
        "你是小说自动化创作系统的【约束生成 Agent】。\n\n"
        "## 角色定位\n"
        "你是一位经验丰富的小说编辑，擅长在写作前为每一章制定精确的约束条件，"
        "确保故事的一致性、节奏感和伏笔管理。\n\n"
        "## 任务\n"
        "分析当前项目状态，为即将写作的下一章生成精确的约束条件。\n\n"
        "## 输出格式\n"
        "你必须输出严格 JSON，不要写任何解释文字。JSON 结构如下：\n"
        "{\n"
        '  "must_happen": ["本章必须发生的事件列表，2-5条"],\n'
        '  "must_not_happen": ["本章禁止发生的事件列表，2-4条"],\n'
        '  "character_allocation": {"角色名": {"min_ratio": 0.1, "max_ratio": 0.4, "scene_type": "主线/支线/过渡"}},\n'
        '  "pov_plan": {"primary": "主视角角色名", "secondary": "次视角角色名", "ratio": "60/30/10"},\n'
        '  "foreshadow_actions": [{"foreshadow_id": "伏笔ID", "action": "轻微回响/推进/回收", "detail": "具体处理方式"}],\n'
        '  "style_constraints": ["文风要求列表"],\n'
        '  "continuity_requirements": ["必须保持的连续性要求"]\n'
        "}\n\n"
        "## 关键规则\n"
        "1. must_not_happen 必须包含 forbiddenRules 中的所有禁止项\n"
        "2. 角色分配必须考虑 dropoutRisk 高的角色需要更多出场\n"
        "3. 伏笔处理不能在 plannedPayoffChapter 之前回收\n"
        "4. 视角分配要考虑角色的 knowledgeState，不能让角色知道不该知道的事\n"
        "5. 真相源中标记为禁止的信息绝对不能在本章揭露\n"
        "6. 每章至少推动主线、角色关系或伏笔之一\n"
        "7. 所有比例之和不超过 1.0"
    )

    user_prompt = (
        "请根据以下项目状态，为下一章生成约束条件：\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_director_prompt(
    project: dict[str, Any],
    constraints: dict[str, Any],
) -> list[dict[str, str]]:
    """导演稿 Agent 的 Prompt。

    角色: 小说自动化创作系统的【导演稿 Agent】
    任务: 根据约束条件和项目状态，为下一章规划 3-6 个场景的导演稿。

    Args:
        project: 完整的项目数据
        constraints: 约束 Agent 的输出

    Returns:
        消息列表
    """
    story_bible = project.get("storyBible", {})

    context = {
        "title": project.get("title", ""),
        "genre": story_bible.get("genre", ""),
        "styleProfile": story_bible.get("styleProfile", ""),
        "mainTheme": story_bible.get("mainTheme", ""),
        "mainConflict": story_bible.get("mainConflict", ""),
        "endingDirection": story_bible.get("endingDirection", ""),
        "currentChapter": len(project.get("chapters", [])),
        "characters": [
            {
                "name": c.get("name", ""),
                "role": c.get("role", ""),
                "personality": c.get("personality", ""),
                "currentGoal": c.get("currentGoal", ""),
                "emotion": c.get("emotion", ""),
            }
            for c in project.get("characters", [])[:6]
        ],
        "constraints": constraints,
        "recentChapterSummaries": [
            {
                "number": c.get("number", 0),
                "title": c.get("title", ""),
                "summary": (c.get("summary") or c.get("text", ""))[:200],
            }
            for c in project.get("chapters", [])[-3:]
        ],
    }

    system_prompt = (
        "你是小说自动化创作系统的【导演稿 Agent】。\n\n"
        "## 角色定位\n"
        "你是一位资深的影视导演，擅长将故事大纲拆解为精确的场景蓝图。"
        "你关注场景的节奏、情绪弧线、角色互动和悬念布局。\n\n"
        "## 任务\n"
        "根据约束条件和项目状态，为下一章规划 3-6 个场景的导演稿。\n\n"
        "## 输出格式\n"
        "你必须输出严格 JSON，不要写任何解释文字。JSON 结构如下：\n"
        "{\n"
        '  "chapter_title": "章节标题（可选，8字以内）",\n'
        '  "scenes": [\n'
        '    {\n'
        '      "number": 1,\n'
        '      "goal": "场景目标（一句话描述）",\n'
        '      "conflict": "核心冲突（一句话描述）",\n'
        '      "turning_point": "转折点（可选，非每个场景都有）",\n'
        '      "hook": "场景结尾钩子（吸引读者继续阅读）",\n'
        '      "characters": ["出场角色名列表"],\n'
        '      "location": "场景地点",\n'
        '      "time": "时间（如：清晨、午后、深夜）",\n'
        '      "mood": "情绪基调（如：紧张、温馨、压抑）"\n'
        '    }\n'
        "  ],\n"
        '  "chapter_goal": "本章总体目标（一句话）",\n'
        '  "chapter_arc": "本章情感弧线描述",\n'
        '  "pacing": "节奏描述（如：缓起-渐紧-高潮-余韵）"\n'
        "}\n\n"
        "## 关键规则\n"
        "1. 场景数量控制在 3-6 个，根据约束中的 must_happen 合理分配\n"
        "2. 每个场景必须遵守约束中的 character_allocation\n"
        "3. 场景的视角必须符合 pov_plan\n"
        "4. 伏笔处理必须按 foreshadow_actions 的指令安排到对应场景\n"
        "5. 情感弧线要有起伏，不能平淡\n"
        "6. 最后一个场景必须有钩子，吸引读者看下一章\n"
        "7. 场景之间要有自然的过渡逻辑\n"
        "8. 绝对不能安排违反 must_not_happen 的内容"
    )

    user_prompt = (
        "请根据以下项目状态和约束条件，生成本章的导演稿：\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_writer_prompt(
    project: dict[str, Any],
    constraints: dict[str, Any],
    director_plan: dict[str, Any],
) -> list[dict[str, str]]:
    """正文写作 Agent 的 Prompt。

    角色: 小说自动化创作系统的【正文写作 Agent】
    任务: 根据导演稿、约束条件和项目状态，撰写高质量的章节正文。

    Args:
        project: 完整的项目数据
        constraints: 约束 Agent 的输出
        director_plan: 导演 Agent 的输出

    Returns:
        消息列表
    """
    story_bible = project.get("storyBible", {})
    chapters = project.get("chapters", [])

    context = {
        "title": project.get("title", ""),
        "genre": story_bible.get("genre", ""),
        "styleProfile": story_bible.get("styleProfile", ""),
        "mainTheme": story_bible.get("mainTheme", ""),
        "constraints": constraints,
        "directorPlan": director_plan,
        "characters": [
            {
                "name": c.get("name", ""),
                "role": c.get("role", ""),
                "personality": c.get("personality", ""),
                "emotion": c.get("emotion", ""),
                "speakingStyle": c.get("speakingStyle", "待推断"),
            }
            for c in project.get("characters", [])[:6]
        ],
        "recentChapterSummaries": [
            {
                "number": c.get("number", 0),
                "title": c.get("title", ""),
                "summary": (c.get("summary") or c.get("text", ""))[:300],
            }
            for c in chapters[-3:]
        ],
        "lastChapterTail": chapters[-1].get("text", "")[-500:] if chapters else "",
        "forbiddenRules": story_bible.get("forbiddenRules", []),
        "foreshadows": [
            {
                "name": f.get("name", ""),
                "status": f.get("status", ""),
                "nextAction": f.get("nextAction", ""),
            }
            for f in project.get("foreshadows", [])[:8]
        ],
        "relationships": project.get("relationships", [])[:6],
    }

    system_prompt = (
        "你是小说自动化创作系统的【正文写作 Agent】。\n\n"
        "## 角色定位\n"
        "你是一位文笔精湛的小说家，擅长将导演稿转化为引人入胜的正文。"
        "你的文字有画面感、节奏感和情绪张力，读者会忘记自己在阅读。\n\n"
        "## 任务\n"
        "根据导演稿、约束条件和项目状态，撰写高质量的章节正文。\n\n"
        "## 输出格式\n"
        "你必须输出严格 JSON，不要写任何解释文字。JSON 结构如下：\n"
        "{\n"
        '  "text": "正文内容（3000-8000字）",\n'
        '  "word_count": 5000,\n'
        '  "dialogue_ratio": 0.3,\n'
        '  "narrative_style": "第三人称有限视角"\n'
        "}\n\n"
        "## 写作规则\n"
        "1. 严格按照导演稿的场景顺序和目标写作\n"
        "2. 遵守所有约束条件（must_happen / must_not_happen）\n"
        "3. 角色分配比例必须符合 character_allocation\n"
        "4. 视角切换必须符合 pov_plan\n"
        "5. 伏笔处理必须按 foreshadow_actions 的指令执行\n"
        "6. 文风必须符合 style_constraints\n"
        "7. 与上一章结尾自然衔接\n"
        "8. 正文必须包含足够的感官细节和情绪描写\n"
        "9. 对话要自然，符合角色性格\n"
        "10. 绝对避免 AI 味重的表达（如'不禁'、'竟然'、'仿佛'等过度使用）\n"
        "11. 每个场景之间要有自然的过渡\n"
        "12. 最后一个场景的结尾要有钩子\n"
        "13. 字数控制在 3000-8000 字之间\n"
        "14. 对话占比控制在 20%-40% 之间\n"
        "15. 不要在正文中直接解释伏笔，要自然融入叙事"
    )

    user_prompt = (
        "请根据以下导演稿和约束条件，撰写章节正文：\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_review_prompt(
    project: dict[str, Any],
    chapter_text: str,
    constraints: dict[str, Any],
    director_plan: dict[str, Any],
) -> list[dict[str, str]]:
    """质量检查 Agent 的 Prompt。

    角色: 小说自动化创作系统的【质量检查 Agent】
    任务: 对已生成的正文进行多维度质量检查。

    Args:
        project: 完整的项目数据
        chapter_text: 已生成的章节正文
        constraints: 约束 Agent 的输出
        director_plan: 导演 Agent 的输出

    Returns:
        消息列表
    """
    story_bible = project.get("storyBible", {})
    chapters = project.get("chapters", [])

    context = {
        "chapterText": chapter_text,
        "chapterNumber": len(chapters) + 1,
        "directorPlan": director_plan,
        "constraints": constraints,
        "forbiddenRules": story_bible.get("forbiddenRules", []),
        "characters": [
            {
                "name": c.get("name", ""),
                "role": c.get("role", ""),
                "personality": c.get("personality", ""),
            }
            for c in project.get("characters", [])[:8]
        ],
        "foreshadows": [
            {
                "id": f.get("id", ""),
                "name": f.get("name", ""),
                "status": f.get("status", ""),
            }
            for f in project.get("foreshadows", [])[:10]
        ],
        "truthSource": project.get("truthSource", {}),
        "recentChapterSummaries": [
            {
                "number": c.get("number", 0),
                "title": c.get("title", ""),
                "summary": (c.get("summary") or c.get("text", ""))[:200],
            }
            for c in chapters[-3:]
        ],
        "relationships": project.get("relationships", [])[:6],
    }

    system_prompt = (
        "你是小说自动化创作系统的【质量检查 Agent】。\n\n"
        "## 角色定位\n"
        "你是一位严格的文学编辑，对小说质量有极高的标准。"
        "你会从连续性、视角、角色主动性、禁止揭露、伏笔处理、约束遵守、AI 味等维度进行检查。\n\n"
        "## 任务\n"
        "对已生成的正文进行多维度质量检查，给出评分和修改建议。\n\n"
        "## 输出格式\n"
        "你必须输出严格 JSON，不要写任何解释文字。JSON 结构如下：\n"
        "{\n"
        '  "total_score": 85,\n'
        '  "tests": [\n'
        '    {"name": "检查项名称", "passed": true, "score": 90, "message": "检查结果描述"}\n'
        "  ],\n"
        '  "rewrite_suggestions": ["修改建议1", "修改建议2"],\n'
        '  "passed": true\n'
        "}\n\n"
        "## 检查维度\n"
        "1. 连续性检查: 与前文是否有矛盾（时间线、人物位置、已知信息）\n"
        "2. 视角稳定性: 是否按照 pov_plan 切换视角，是否有越界\n"
        "3. 角色主动性: 角色是否有自主行动，是否被动接受安排\n"
        "4. 禁止揭露检查: 是否违反 forbiddenRules，是否提前揭露真相\n"
        "5. 伏笔处理检查: 是否按 foreshadow_actions 处理了伏笔\n"
        "6. 约束遵守检查: 是否满足 must_happen，是否违反 must_not_happen\n"
        "7. AI 味检测: 是否存在模板化表达、过度修辞、不自然的描写\n\n"
        "## 评分标准\n"
        "- 90-100: 优秀，无需修改\n"
        "- 80-89: 良好，可有少量修改\n"
        "- 70-79: 及格，建议修改\n"
        "- 60-69: 不及格，需要重写\n"
        "- 60以下: 严重问题，必须重写\n\n"
        "passed 判定: total_score >= 80 且所有关键检查项 passed"
    )

    user_prompt = (
        "请对以下章节正文进行质量检查：\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_state_extract_prompt(
    project: dict[str, Any],
    chapter_text: str,
) -> list[dict[str, str]]:
    """状态提取 Agent 的 Prompt。

    角色: 小说自动化创作系统的【状态提取 Agent】
    任务: 从已生成的章节正文中提取所有状态变化。

    Args:
        project: 完整的项目数据
        chapter_text: 已生成的章节正文

    Returns:
        消息列表
    """
    chapters = project.get("chapters", [])

    context = {
        "chapterText": chapter_text,
        "chapterNumber": len(chapters) + 1,
        "characters": [
            {
                "id": c.get("id", ""),
                "name": c.get("name", ""),
                "role": c.get("role", ""),
                "emotion": c.get("emotion", ""),
                "agencyScore": c.get("agencyScore", 0),
                "dropoutRisk": c.get("dropoutRisk", 0),
                "currentGoal": c.get("currentGoal", ""),
                "knowledgeState": c.get("knowledgeState", []),
            }
            for c in project.get("characters", [])[:8]
        ],
        "foreshadows": [
            {
                "id": f.get("id", ""),
                "name": f.get("name", ""),
                "status": f.get("status", ""),
                "risk": f.get("risk", 0),
                "plannedPayoffChapter": f.get("plannedPayoffChapter", f.get("plannedPayoff", 999)),
            }
            for f in project.get("foreshadows", [])[:10]
        ],
        "relationships": project.get("relationships", [])[:6],
        "previousStateSnapshot": (
            project.get("memory", {}).get("stateSnapshots", [])[-1]
            if project.get("memory", {}).get("stateSnapshots")
            else {}
        ),
        "recentEvents": project.get("events", [])[-5:],
    }

    system_prompt = (
        "你是小说自动化创作系统的【状态提取 Agent】。\n\n"
        "## 角色定位\n"
        "你是一位细致的叙事分析师，擅长从文本中提取隐含的状态变化。"
        "你的提取结果将用于维护小说的全局状态一致性。\n\n"
        "## 任务\n"
        "从已生成的章节正文中提取所有状态变化。\n\n"
        "## 输出格式\n"
        "你必须输出严格 JSON，不要写任何解释文字。JSON 结构如下：\n"
        "{\n"
        '  "state_delta": {\n'
        '    "main_progress_delta": 2,\n'
        '    "character_changes": [\n'
        '      {"character_id": "角色ID", "character_name": "角色名", "field": "emotion/agencyScore/dropoutRisk/goal", "old": "旧值", "new": "新值", "reason": "变化原因"}\n'
        "    ],\n"
        '    "personality_shifts": [\n'
        '      {"character_id": "角色ID", "character_name": "角色名", "shift": "本章中角色性格/行为模式的微妙变化描述", "trigger": "触发变化的事件或情境"}\n'
        "    ],\n"
        '    "relationship_changes": [\n'
        '      {"from": "角色A", "to": "角色B", "field": "trust/tension", "old_value": 50, "new_value": 45, "delta": -5, "reason": "变化原因"}\n'
        "    ],\n"
        '    "foreshadow_changes": [\n'
        '      {"foreshadow_id": "伏笔ID", "action": "回响/推进/回收", "detail": "具体变化描述"}\n'
        "    ],\n"
        '    "new_events": [\n'
        '      {"description": "事件描述", "impact": "影响描述", "visibility": ["看到了此事件的角色名列表"]}\n'
        "    ],\n"
        '    "small_details": [\n'
        '      {"detail": "可能对后续剧情有用的小细节（如角色提到的一个地名、一个习惯动作、一个未解释的反应）", "related_character": "相关角色名"}\n'
        "    ],\n"
        '    "timeline_updates": ["时间线更新描述"],\n'
        '    "knowledge_updates": [\n'
        '      {"character": "角色名", "learned": "学到了什么新信息", "forgot": null}\n'
        "    ]\n"
        "  }\n"
        "}\n\n"
        "## 提取规则\n"
        "1. main_progress_delta: 主线推进程度（0-10），0表示无推进，10表示重大推进\n"
        "2. character_changes: 只提取明确发生变化的角色属性\n"
        "3. personality_shifts: 提取角色性格/行为模式的微妙变化。这是角色成长的关键信号。例如：一向冷静的角色开始焦虑、独来独往的角色主动寻求帮助、乐观的角色出现自我怀疑。即使变化很小也要记录。\n"
        "4. relationship_changes: trust 和 tension 的变化范围在 -20 到 +20 之间\n"
        "5. foreshadow_changes: 只记录正文中实际提及或推进的伏笔\n"
        "6. new_events: 只记录对后续剧情有影响的事件\n"
        "7. small_details: 提取正文中看似不起眼但可能对后续剧情有用的小细节。例如：角色不经意提到的一个地名、一个反复出现的小动作、一个未得到解释的反应、一个被忽略的物品。这些细节是后续情节伏笔的素材。\n"
        "8. timeline_updates: 记录时间线上的重要节点\n"
        "9. knowledge_updates: 记录角色在本章中获得或失去的知识\n"
        "10. 如果某类变化没有发生，对应列表为空数组即可\n"
        "11. 所有变化必须有 reason 或 detail 说明原因\n"
        "12. 不要凭空编造正文中没有的内容"
    )

    user_prompt = (
        "请从以下章节正文中提取所有状态变化：\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


# ======================================================================
# 分场景写作 Prompt 模板
# ======================================================================

def build_scene_writing_prompt(
    project: dict[str, Any],
    scene: dict[str, Any],
    previous_scene_text: str = "",
    target_word_count: int = 1500,
) -> list[dict[str, str]]:
    """单场景写作 Prompt。

    为分场景生成模式设计，每个场景独立调用 AI 生成正文。

    角色: 小说自动化创作系统的【正文写作 Agent - 场景模式】
    任务: 根据单个场景的导演稿，撰写该场景的正文段落。

    Args:
        project: 完整的项目数据
        scene: 单个场景的导演稿（来自 DirectorAgent 的 scenes 列表中的某一项）
        previous_scene_text: 前一个场景的正文结尾（用于衔接）
        target_word_count: 本场景的目标字数

    Returns:
        消息列表
    """
    story_bible = project.get("storyBible", {})
    chapters = project.get("chapters", [])

    # 场景基本信息
    scene_number = scene.get("number", 1)
    scene_goal = scene.get("goal", "")
    scene_conflict = scene.get("conflict", "")
    scene_turning_point = scene.get("turning_point", "")
    scene_hook = scene.get("hook", "")
    scene_characters = scene.get("characters", [])
    scene_location = scene.get("location", "")
    scene_time = scene.get("time", "")
    scene_mood = scene.get("mood", "")

    # 出场角色的详细信息
    character_details = []
    all_characters = project.get("characters", [])
    for char_name in scene_characters:
        char_info = next(
            (c for c in all_characters if c.get("name") == char_name),
            None,
        )
        if char_info:
            character_details.append({
                "name": char_info.get("name", ""),
                "role": char_info.get("role", ""),
                "personality": char_info.get("personality", ""),
                "emotion": char_info.get("emotion", ""),
                "speakingStyle": char_info.get("speakingStyle", "待推断"),
            })
        else:
            character_details.append({"name": char_name, "role": "未知", "personality": "", "emotion": ""})

    context = {
        "title": project.get("title", ""),
        "genre": story_bible.get("genre", ""),
        "styleProfile": story_bible.get("styleProfile", ""),
        "mainTheme": story_bible.get("mainTheme", ""),
        "scene": {
            "number": scene_number,
            "goal": scene_goal,
            "conflict": scene_conflict,
            "turning_point": scene_turning_point,
            "hook": scene_hook,
            "characters": scene_characters,
            "location": scene_location,
            "time": scene_time,
            "mood": scene_mood,
        },
        "characterDetails": character_details,
        "previousSceneTail": previous_scene_text[-300:] if previous_scene_text else "",
        "lastChapterTail": chapters[-1].get("text", "")[-300:] if chapters else "",
        "forbiddenRules": story_bible.get("forbiddenRules", []),
        "targetWordCount": target_word_count,
    }

    # 注入深度记忆（如果有）
    memory_result = project.get("_memory_result", {})
    if memory_result:
        relevant_memories = memory_result.get("relevant_chapters", [])
        if relevant_memories:
            context["deepMemory"] = relevant_memories[:5]
        memory_insights = memory_result.get("insights", "")
        if memory_insights:
            context["memoryInsights"] = memory_insights

    system_prompt = (
        "你是小说自动化创作系统的【正文写作 Agent - 场景模式】。\n\n"
        "## 角色定位\n"
        "你是一位文笔精湛的小说家，擅长将单个场景的导演稿转化为引人入胜的正文段落。\n\n"
        "## 任务\n"
        "根据以下场景导演稿，撰写该场景的正文。\n\n"
        "## 输出格式\n"
        "你必须输出严格 JSON，不要写任何解释文字。JSON 结构如下：\n"
        "{\n"
        '  "text": "场景正文内容",\n'
        '  "word_count": 500\n'
        "}\n\n"
        f"## 字数要求（极其重要，必须严格遵守）\n"
        f"本场景目标字数：{target_word_count} 字。\n"
        f"硬性上限：{int(target_word_count * 1.2)} 字，绝对不能超过。\n"
        f"硬性下限：{int(target_word_count * 0.8)} 字，不能低于此数。\n"
        f"如果写到上限字数还未完成场景，必须立即收束结尾，不能继续写。\n\n"
        "## 写作规则\n"
        "1. 严格按照场景目标、冲突、转折、钩子来写作\n"
        "2. 角色对话要符合角色性格和当前情绪状态\n"
        "3. 与前一场景的结尾自然衔接（如果提供了前文）\n"
        "4. 场景开头要有环境描写或氛围铺垫\n"
        "5. 场景结尾要有钩子（如果导演稿中指定了 hook）\n"
        "6. 绝对避免 AI 味重的表达\n"
        "7. 包含足够的感官细节和情绪描写\n"
        "8. 不要在正文中直接解释伏笔，要自然融入叙事\n"
        "9. 对话占比控制在 20%-40% 之间\n"
        "10. 时刻注意字数，写到上限必须收束\n"
        "11. 不要使用与上一章相同的场景开头方式\n"
        "12. 对话必须有信息量，禁止谜语式对话超过2轮\n"
        "13. 角色反应要具体化，避免标签化行为（如'冷硬地分析'、'神秘地微笑'）"
    )

    user_prompt = (
        f"请根据以下场景导演稿，撰写第 {scene_number} 个场景的正文：\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
