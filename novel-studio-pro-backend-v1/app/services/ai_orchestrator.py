from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from app.core.utils import make_id, now_iso, truncate_text
from app.services.deepseek_client import deepseek_client
from app.services.prompt_templates import (
    build_chapter_generation_prompt,
    build_outline_expansion_prompt,
)
from app.services.settings_service import settings_service

# 多 Agent 系统
from app.services.agents import (
    ConstraintAgent,
    DirectorAgent,
    WriterAgent,
    ReviewAgent,
    StateExtractorAgent,
    StateMerger,
    ContextBuilder,
    MemoryAgent,
    CharacterDirectorAgent,
    ForeshadowAgent,
)

logger = logging.getLogger(__name__)


# ======================================================================
# 常量与工具函数
# ======================================================================

GENRE_STYLE_MAP = {
    "奇幻": "明亮史诗感，场景富有想象力，冲突清晰，情绪推进直接。",
    "玄幻": "升级爽点明确，压迫与反击循环强，伏笔与世界层级逐步展开。",
    "科幻": "概念清楚，技术设定自洽，悬念与人性选择并行。",
    "都市": "节奏轻快，现实细节充足，人物关系推进自然。",
    "悬疑": "信息不对称强，线索、误导、反转和阶段性答案交替出现。",
    "言情": "情绪浓度高，关系拉扯明确，双主角成长线并进。",
}


def chapter_title(n: int) -> str:
    pool = [
        "黑夜中的火光", "禁忌的代价", "重别与启程", "旧账浮出水面", "命运的第一次选择",
        "来自深渊的低语", "青州旧案", "雨夜追凶", "沉默的家徽", "钟楼下的誓言",
        "王都来信", "暗流涌动", "被抹去的名字", "旧账与夜火", "雾中来客",
        "真相的一角", "不该出现的令牌", "少女的独行", "沉入火中的船", "黎明之前",
    ]
    if n <= len(pool):
        return pool[n - 1]
    return f"第{n}个未解之夜"


def default_characters(title: str, genre: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "char_protagonist",
            "name": "江离",
            "role": "主角 / 复仇者",
            "personality": "冷静、克制、行动力强，习惯隐藏真实情绪。",
            "currentGoal": "查清三年前旧案真相，找出夜火计划背后的势力。",
            "hiddenGoal": "确认自己是否也是旧案的一部分。",
            "emotion": "表面平静，内心压抑。",
            "agencyScore": 92,
            "dropoutRisk": 8,
            "lastAppearedChapter": 0,
            "nextRecommendedChapter": 1,
            "knowledgeState": ["知道旧案与黑石码头有关", "不知道夜火计划真正主导者"],
            "tag": "成长型",
        },
        {
            "id": "char_female_lead",
            "name": "沈烬",
            "role": "女主 / 失忆调查者",
            "personality": "敏锐、独立、外柔内韧，不愿被任何人安排命运。",
            "currentGoal": "找回失去的记忆，弄清自己与夜火计划的关系。",
            "hiddenGoal": "保护自己真正的家族线索不被他人利用。",
            "emotion": "对主角保持警惕，但愿意临时合作。",
            "agencyScore": 86,
            "dropoutRisk": 12,
            "lastAppearedChapter": 0,
            "nextRecommendedChapter": 1,
            "knowledgeState": ["知道自己记忆缺失", "不知道她的家徽与旧案有关"],
            "tag": "主动型",
        },
        {
            "id": "char_support_suzhao",
            "name": "苏照",
            "role": "配角 / 情报商",
            "personality": "爱开玩笑，消息灵通，但关键时刻很谨慎。",
            "currentGoal": "用情报换取自身安全，同时试探江离底线。",
            "hiddenGoal": "替某个未知势力观察江离。",
            "emotion": "轻松表象下有隐忧。",
            "agencyScore": 74,
            "dropoutRisk": 28,
            "lastAppearedChapter": 0,
            "nextRecommendedChapter": 2,
            "knowledgeState": ["知道黑石码头曾被封锁", "不知道夜火计划完整内容"],
            "tag": "信息型",
        },
        {
            "id": "char_villain_shadow",
            "name": "夜枭会长老",
            "role": "阶段反派 / 秘密执行者",
            "personality": "阴冷、守序、极重代价与交易。",
            "currentGoal": "阻止江离继续追查旧案。",
            "hiddenGoal": "替更高层掩盖夜火计划失败记录。",
            "emotion": "自信但开始不安。",
            "agencyScore": 78,
            "dropoutRisk": 38,
            "lastAppearedChapter": 0,
            "nextRecommendedChapter": 3,
            "knowledgeState": ["知道夜火计划部分真相", "不知道女主已开始恢复记忆"],
            "tag": "压迫型",
        },
        {
            "id": "char_mentor",
            "name": "林栖",
            "role": "导师 / 旧案知情人",
            "personality": "温和、克制、避谈过去。",
            "currentGoal": "保护主角不要过早接触真相。",
            "hiddenGoal": "赎清自己三年前的沉默。",
            "emotion": "愧疚。",
            "agencyScore": 61,
            "dropoutRisk": 55,
            "lastAppearedChapter": 0,
            "nextRecommendedChapter": 4,
            "knowledgeState": ["知道旧案不是单纯灭门", "不知道夜火印记已经苏醒"],
            "tag": "引导型",
        },
    ]


def default_relationships() -> list[dict[str, Any]]:
    return [
        {"from": "江离", "to": "沈烬", "type": "互相试探", "trust": 35, "tension": 72, "change": "临时合作但互相隐瞒。"},
        {"from": "江离", "to": "苏照", "type": "利益合作", "trust": 46, "tension": 48, "change": "情报交易关系。"},
        {"from": "江离", "to": "夜枭会长老", "type": "敌对", "trust": 0, "tension": 90, "change": "旧案冲突正在正面化。"},
        {"from": "沈烬", "to": "苏照", "type": "谨慎合作", "trust": 40, "tension": 42, "change": "女主对苏照情报来源存疑。"},
    ]


def default_foreshadows() -> list[dict[str, Any]]:
    return [
        {"id": "fb_night_fire_plan", "name": "夜火计划", "firstChapter": 1, "lastMentionedChapter": 0, "status": "已埋下", "importance": "high", "risk": 22, "plannedPayoffChapter": 48, "nextAction": "第3-5章轻微回响。"},
        {"id": "fb_family_emblem", "name": "破损家徽", "firstChapter": 2, "lastMentionedChapter": 0, "status": "已埋下", "importance": "medium", "risk": 18, "plannedPayoffChapter": 20, "nextAction": "与女主身世线关联。"},
        {"id": "fb_fire_truth", "name": "三年前火夜真相", "firstChapter": 1, "lastMentionedChapter": 0, "status": "待回收", "importance": "high", "risk": 34, "plannedPayoffChapter": 60, "nextAction": "不能过早揭露主谋。"},
        {"id": "fb_mysterious_token", "name": "神秘令牌的来源", "firstChapter": 4, "lastMentionedChapter": 0, "status": "未触发", "importance": "medium", "risk": 26, "plannedPayoffChapter": 30, "nextAction": "在码头或账本中出现图案。"},
    ]


# ======================================================================
# Mock 蓝图构建（保留原有功能）
# ======================================================================

def build_mock_blueprint(project: dict[str, Any], variant: str = "standard") -> dict[str, Any]:
    title = project.get("title") or "未命名小说"
    genre = project.get("genre") or "奇幻"
    style = GENRE_STYLE_MAP.get(genre, "青春活力、节奏明快、冲突清晰、情绪自然。")
    outline = truncate_text(project.get("outline", ""), 1200)

    volume_plan = [
        {"id": "vol_1", "name": "卷一 · 青州卷", "range": "第1章 - 第30章", "objective": "建立世界与角色，查明旧案第一层真相。", "turningPoint": "真凶现身，主角被迫离开青州。", "tone": "探索 / 觉醒 / 羁绊", "status": "完成" if project.get("chapters") else "规划中"},
        {"id": "vol_2", "name": "卷二 · 王都卷", "range": "第31章 - 第60章", "objective": "进入权力中心，揭开夜火计划的政治线。", "turningPoint": "皇太子之死，局势骤变。", "tone": "权谋 / 阴谋 / 反转", "status": "未开始"},
        {"id": "vol_3", "name": "卷三 · 宗门卷", "range": "第61章 - 第90章", "objective": "进入宗门，寻找旧世界秘辛。", "turningPoint": "宗门内乱，真相浮出水面。", "tone": "修行 / 迷雾 / 选择", "status": "未开始"},
        {"id": "vol_4", "name": "卷四 · 终局卷", "range": "第91章 - 第120章", "objective": "决战天命，完成角色命运闭环。", "turningPoint": "夜火降临，旧世终结。", "tone": "史诗 / 决战 / 升华", "status": "未开始"},
    ]

    stage_plan = [
        {"name": "铺垫期", "range": "1-10章", "goal": "建立世界、角色和核心伏笔。"},
        {"name": "发展期", "range": "11-30章", "goal": "主线推进，矛盾升级，真相初现。"},
        {"name": "转折期", "range": "31-50章", "goal": "格局扩大，关键角色登场。"},
        {"name": "爆发期", "range": "51-60章", "goal": "重大事件爆发，局势逆转。"},
        {"name": "沉淀期", "range": "61-80章", "goal": "深入宗门秘辛，真相拼合。"},
        {"name": "决战期", "range": "81-100章", "goal": "终局前奏，命运交汇。"},
        {"name": "终局期", "range": "101-120章", "goal": "终极对决，旧世新生。"},
    ]

    chapter_titles = [{"number": i, "title": chapter_title(i)} for i in range(1, 121)]
    characters = default_characters(title, genre)
    foreshadows = default_foreshadows()

    # 兼容前端 v3 的字段格式：风险和主动性使用 0-1 小数。
    for character in characters:
        if character.get("agencyScore", 0) > 1:
            character["agencyScore"] = round(character["agencyScore"] / 100, 2)
        if character.get("dropoutRisk", 0) > 1:
            character["dropoutRisk"] = round(character["dropoutRisk"] / 100, 2)
        character["lastAppeared"] = character.get("lastAppearedChapter", 0)
        character.setdefault("trust", 50)
    for foreshadow in foreshadows:
        if foreshadow.get("risk", 0) > 1:
            foreshadow["risk"] = round(foreshadow["risk"] / 100, 2)
        foreshadow["lastMentioned"] = foreshadow.get("lastMentionedChapter", 0)
        foreshadow["plannedPayoff"] = foreshadow.get("plannedPayoffChapter", 20)

    return {
        "totalTargetChapters": 120 if project.get("lengthType") != "superlong" else 220,
        "wordCount": project.get("wordCount", 0),
        "currentChapterNumber": len(project.get("chapters", [])),
        "storyBible": {
            "title": title,
            "genre": genre,
            "originalOutline": outline,
            "styleProfile": style,
            "style": style,
            "volumePlan": volume_plan,
            "chapterTitlePreview": chapter_titles,
            "corePremise": "在魔法、权力与旧案交织的世界中，主角因三年前的火夜被迫追寻真相，并逐步发现自身与夜火计划的联系。",
            "mainTheme": "命运不是被揭示的答案，而是在选择中被重新书写。",
            "mainConflict": "主角追查旧案，却发现真相会伤害他想守护的人。",
            "endingDirection": "主角打破旧秩序，让夜火从毁灭象征转化为新生火种。",
            "forbiddenRules": [
                "前30章不得让主角确认夜火计划的最终主谋。",
                "女主不能在前20章完全恢复记忆。",
                "阶段反派不能用长段独白直接解释阴谋。",
                "每章必须至少推动主线、角色关系或伏笔之一。",
            ],
        },
        "volumePlan": volume_plan,
        "stagePlan": stage_plan,
        "chapterTitlePreview": chapter_titles,
        "characters": characters,
        "relationships": default_relationships(),
        "foreshadows": foreshadows,
        "truthSource": {
            "authorTruth": 100,
            "readerKnown": 8,
            "protagonistKnown": 6,
            "femaleLeadKnown": 4,
            "misdirection": 12
        },
        "status": {
            "currentChapter": 0,
            "currentChapterTitle": "尚未开始",
            "mainProgress": 0,
            "foreshadowTotal": len(foreshadows),
            "foreshadowResolved": 0,
            "activeCharacters": 0,
            "totalCharacters": len(characters),
            "deviationRisk": 0.08,
            "qualityScore": 92,
            "worldConsistency": 95,
            "characterConsistency": 93,
            "foreshadowHealth": 88,
            "overallRating": "A-",
            "lastAnalyzedAt": now_iso(),
        },
        "memory": {
            "storyBibleMemory": "已生成故事蓝图、分卷规划、角色与伏笔初始状态。",
            "chapterSummaries": [],
            "stateSnapshots": [],
            "nextContextPack": {
                "priority": ["故事蓝图", "当前主线", "角色目标", "高风险伏笔", "最近三章摘要"],
                "tokenStrategy": "结构化状态优先，正文片段按相关度检索。",
            },
        },
    }


# ======================================================================
# 蓝图构建（保留原有 DeepSeek / Mock 双模式）
# ======================================================================

async def maybe_deepseek_blueprint(project: dict[str, Any]) -> dict[str, Any] | None:
    generation = settings_service.get_all(safe=False).get("generation", {})
    if generation.get("mockMode", True) or not deepseek_client.is_ready():
        return None
    routes = settings_service.get_all(safe=False).get("modelRoutes", {})
    route = routes.get("outlineExpansion", {})
    messages = build_outline_expansion_prompt(project)
    try:
        data = await deepseek_client.chat_json(
            messages=messages,
            model=route.get("model"),
            temperature=float(route.get("temperature", 0.75)),
            max_tokens=int(route.get("maxOutputTokens", 12000)),
            task_name="outlineExpansion",
        )
        return data
    except Exception:
        # 第一版不让 DeepSeek 错误打断个人创作流程，自动回退 Mock。
        return None


async def build_story_blueprint(project: dict[str, Any], variant: str = "standard") -> dict[str, Any]:
    """构建故事蓝图。

    优先尝试 DeepSeek AI 生成，失败则回退 Mock 模式。
    """
    ai_data = await maybe_deepseek_blueprint(project)
    if ai_data:
        return ai_data
    return build_mock_blueprint(project, variant=variant)


# ======================================================================
# Mock 章节生成（保留原有功能，供 Mock 模式使用）
# ======================================================================

def build_mock_chapter(project: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
    """Mock 模式下的章节生成（保留原有逻辑）。"""
    chapters = project.get("chapters", [])
    number = len(chapters) + 1
    title = chapter_title(number)
    preview = project.get("chapterTitlePreview", [])
    title = preview[number - 1].get("title", title) if number - 1 < len(preview) else title

    protagonist = next((c for c in project.get("characters", []) if c.get("id") == "char_protagonist"), {"name": "江离"})
    female = next((c for c in project.get("characters", []) if c.get("id") == "char_female_lead"), {"name": "沈烬"})
    user_instruction = options.get("userInstruction") or ""

    director_plan = {
        "goal": f"推进旧案调查，并让{female.get('name')}拥有独立行动段落。",
        "pov": f"第三人称有限视角；主视角：{protagonist.get('name')} 55%，次视角：{female.get('name')} 35%，配角/反派势力 10%。",
        "roleFocus": {protagonist.get("name", "主角"): 55, female.get("name", "女主"): 35, "配角与反派势力": 10},
        "forbidden": ["不得提前揭露夜火计划最终主谋", "不得让女主完全恢复记忆", "不得让反派长段解释阴谋"],
        "userInstructionApplied": user_instruction,
    }

    paragraphs = [
        f"清晨的光落在城南旧街，瓦檐上的露水像一串细碎的星。{protagonist.get('name')}站在半掩的铺门前，手指按着袖中那枚发冷的残牌，昨夜留下的焦味仍像一根细针，刺在他的记忆深处。",
        f"他没有急着进去。街口传来马车碾过石板的声音，几名穿青灰短衣的人停在巷外，像是在等某个不会准时出现的人。{protagonist.get('name')}看了他们一眼，目光很轻，却把每个人的站位都记了下来。",
        f"另一边，{female.get('name')}没有按照约定去茶楼。她独自绕到后巷，推开一扇几乎被藤蔓遮住的小门。门后是一间废弃账房，桌上积灰很厚，唯有最里面的木匣被人动过。",
        f"木匣里没有账本，只有一枚压扁的铜扣。铜扣边缘刻着半圈火纹，与{protagonist.get('name')}手中的残牌极像。{female.get('name')}垂下眼，没有立刻把这件事告诉任何人。她意识到，自己失去的记忆里，或许藏着比旧案更危险的东西。",
        f"午后，苏照带来消息：夜枭会的人昨夜离开了黑石码头，但没有出城，而是去了钟楼。钟楼三年前曾被封过一次，封条上的字迹至今无人敢认。",
        f"{protagonist.get('name')}终于抬头。风从窗缝灌入，把桌上那页残纸掀开一角。纸背上只有两个字：夜火。",
        "他忽然明白，旧账从来不是被时间埋住的。它只是等着某个人再次把火点燃。",
    ]
    text = "\n\n".join(paragraphs)
    word_count = len(text)

    review = {
        "totalScore": 91,
        "tests": [
            {"name": "连续性检查", "passed": True, "score": 96, "message": "未发现前后冲突。"},
            {"name": "视角稳定性", "passed": True, "score": 93, "message": "视角切换清楚。"},
            {"name": "女主主动性", "passed": True, "score": 89, "message": "女主有独立调查行动。"},
            {"name": "禁止揭露检查", "passed": True, "score": 100, "message": "未提前揭露核心真相。"},
            {"name": "AI 味检测", "passed": True, "score": 88, "message": "模板化表达较少。"},
        ],
    }

    new_event_id = make_id("evt")
    state_delta = {
        "newForeshadows": ["铜扣上的半圈火纹"],
        "relationshipChanges": [f"{protagonist.get('name')} ↔ {female.get('name')}：互相隐瞒的信息增加，信任 -3，张力 +8"],
        "eventUpdates": [
            "主角发现夜枭会成员在旧街活动",
            "女主独自找到刻有火纹的铜扣",
        ],
        "timeline": [
            "三年前：火夜旧案发生",
            "当日清晨：城南旧街出现夜枭会踪迹",
            "当日午后：钟楼线索浮出水面",
        ],
    }

    return {
        "id": make_id("chapter"),
        "number": number,
        "title": title,
        "status": "pending",
        "wordCount": word_count,
        "directorPlan": director_plan,
        "text": text,
        "review": review,
        "stateDelta": state_delta,
        "createdAt": now_iso(),
    }


# ======================================================================
# 原有 DeepSeek 单步章节生成（保留向后兼容）
# ======================================================================

async def maybe_deepseek_chapter(project: dict[str, Any], options: dict[str, Any]) -> dict[str, Any] | None:
    """原有单步 DeepSeek 章节生成（保留向后兼容）。"""
    generation = settings_service.get_all(safe=False).get("generation", {})
    if generation.get("mockMode", True) or not deepseek_client.is_ready():
        return None
    routes = settings_service.get_all(safe=False).get("modelRoutes", {})
    route = routes.get("chapterWriting", {})
    messages = build_chapter_generation_prompt(project, options)
    try:
        data = await deepseek_client.chat_json(
            messages=messages,
            model=route.get("model"),
            temperature=float(route.get("temperature", 0.9)),
            max_tokens=int(options.get("maxOutputTokens") or route.get("maxOutputTokens", 12000)),
            task_name="chapterWriting",
        )
        chapter = data.get("chapter", data)
        chapter.setdefault("id", make_id("chapter"))
        chapter.setdefault("status", "pending")
        chapter.setdefault("number", len(project.get("chapters", [])) + 1)
        chapter.setdefault("createdAt", now_iso())
        if "wordCount" not in chapter:
            chapter["wordCount"] = len(chapter.get("text", ""))
        return chapter
    except Exception:
        return None


# ======================================================================
# 多 Agent 章节生成流水线（核心新逻辑）
# ======================================================================

async def _agent_pipeline_chapter(
    project: dict[str, Any],
    options: dict[str, Any],
) -> dict[str, Any] | None:
    """使用多 Agent 流水线生成章节（含自动重写循环）。

    流程:
        1. ConstraintAgent   - 约束生成
        2. DirectorAgent     - 导演稿生成
        3. WriterAgent       - 正文写作
        4. ReviewAgent       - 质量检查
        5. StateExtractorAgent - 状态提取
        6. StateMerger       - 状态合并验证

    自动重写:
        如果质量评分低于阈值，自动使用 review 建议重新生成。

    Returns:
        完整的章节数据，失败返回 None。
    """
    # 读取重写配置
    generation = settings_service.get_all(safe=False).get("generation", {})
    max_rewrites = int(generation.get("autoRewriteTimes", 2))
    quality_threshold = int(generation.get("qualityThreshold", 75))

    chapter = None
    rewrite_options = dict(options)

    for attempt in range(max_rewrites + 1):
        chapter = await _run_full_pipeline(project, rewrite_options)

        if chapter is None:
            break

        # 检查质量评分
        review = chapter.get("review", {})
        total_score = int(review.get("total_score", review.get("totalScore", 100)))

        if total_score >= quality_threshold or attempt >= max_rewrites:
            break

        # 质量不达标，准备重写
        suggestions = review.get("rewrite_suggestions", "")
        if not suggestions:
            # 从测试项中提取失败项作为建议
            failed_tests = [
                t for t in review.get("tests", [])
                if not t.get("passed", True)
            ]
            suggestions = "；".join(
                f"{t.get('name', '')}: {t.get('message', '')}" for t in failed_tests
            )

        logger.info(
            "[Pipeline] 质量评分 %d 低于阈值 %d，第 %d 次重写",
            total_score, quality_threshold, attempt + 1,
        )

        rewrite_options = dict(rewrite_options)
        rewrite_options["userInstruction"] = (
            f"上次质量评分 {total_score}，需要改进：{suggestions}"
        )

    return chapter


async def _run_full_pipeline(
    project: dict[str, Any],
    options: dict[str, Any],
) -> dict[str, Any] | None:
    """执行完整的 Agent 流水线（单次，不含重写循环）。

    流水线步骤:
        1. MemoryAgent          - 检索相关记忆
        2. ForeshadowAgent      - 规划伏笔处理
        3. ConstraintAgent      - 生成约束（使用 ForeshadowAgent 的输出）
        4. CharacterDirectorAgent - 规划角色戏份
        5. DirectorAgent        - 生成导演稿（使用 CharacterDirectorAgent 的输出）
        6. WriterAgent          - 写正文
        7. ReviewAgent          - 质量检查
        8. StateExtractorAgent  - 提取状态
        9. StateMerger          - 合并状态
    """
    context_builder = ContextBuilder()

    # 步骤 1: 记忆检索
    logger.info("[Pipeline] 步骤 1/9: 记忆检索...")
    memory_ctx = context_builder.build_constraint_context(project)
    memory_ctx["project"] = project
    memory_ctx["taskDescription"] = "生成下一章"
    memory_result = await MemoryAgent().run(memory_ctx)

    # 步骤 2: 伏笔规划
    logger.info("[Pipeline] 步骤 2/9: 伏笔规划...")
    foreshadow_ctx = context_builder.build_constraint_context(project)
    foreshadow_ctx["project"] = project
    foreshadow_result = await ForeshadowAgent().run(foreshadow_ctx)

    # 步骤 3: 约束生成（使用伏笔规划结果）
    logger.info("[Pipeline] 步骤 3/9: 约束生成...")
    constraint_ctx = context_builder.build_constraint_context(project)
    constraint_ctx["project"] = project
    constraint_ctx["foreshadow_plan"] = foreshadow_result.get("foreshadow_plan", [])
    constraints = await ConstraintAgent().run(constraint_ctx)

    # 步骤 4: 角色戏份规划
    logger.info("[Pipeline] 步骤 4/9: 角色戏份规划...")
    char_director_ctx = context_builder.build_director_context(project, constraints)
    char_director_ctx["project"] = project
    char_director_ctx["constraints"] = constraints
    char_plan = await CharacterDirectorAgent().run(char_director_ctx)

    # 步骤 5: 导演稿生成（使用角色规划结果）
    logger.info("[Pipeline] 步骤 5/9: 导演稿生成...")
    director_ctx = context_builder.build_director_context(project, constraints)
    director_ctx["project"] = project
    director_ctx["character_plan"] = char_plan.get("character_plan", {})
    director_plan = await DirectorAgent().run(director_ctx)

    # 步骤 6: 正文写作
    logger.info("[Pipeline] 步骤 6/9: 正文写作...")
    writer_ctx = context_builder.build_writer_context(project, constraints, director_plan)
    writer_ctx["project"] = project

    # 分场景生成判断：如果导演稿有 3+ 个场景，使用分场景生成
    scenes = director_plan.get("scenes", [])
    if len(scenes) >= 3:
        logger.info(
            "[Pipeline] 检测到 %d 个场景，启用分场景生成模式",
            len(scenes),
        )
        writer_agent = WriterAgent()
        chapter_text = await writer_agent.write_by_scene(
            writer_ctx, scenes, target_total_words=5000
        )
    else:
        # 1-2 个场景，使用整章生成（原有逻辑）
        logger.info(
            "[Pipeline] 检测到 %d 个场景，使用整章生成模式",
            len(scenes),
        )
        chapter_text = await WriterAgent().run(writer_ctx)

    # 步骤 7: 质量检查
    logger.info("[Pipeline] 步骤 7/9: 质量检查...")
    # 构建一个临时 chapter 对象供 ReviewAgent 使用
    temp_chapter = {
        "text": chapter_text.get("text", ""),
        "title": director_plan.get("chapter_goal", ""),
        "number": len(project.get("chapters", [])) + 1,
        "wordCount": chapter_text.get("word_count", 0),
        "directorPlan": director_plan,
        "constraints": constraints,
    }
    review_ctx = context_builder.build_review_context(project, temp_chapter)
    review = await ReviewAgent().run(review_ctx)

    # 步骤 8: 状态提取
    logger.info("[Pipeline] 步骤 8/9: 状态提取...")
    state_extract_ctx = context_builder.build_state_extract_context(project, temp_chapter)
    state_extract_ctx["project"] = project
    state_result = await StateExtractorAgent().run(state_extract_ctx)

    # 步骤 9: 状态合并验证
    logger.info("[Pipeline] 步骤 9/9: 状态合并验证...")
    state_delta = state_result.get("state_delta", {})
    merger = StateMerger()
    merged, preview = merger.validate_and_merge(project, state_delta)

    # 确定章节标题
    chapters = project.get("chapters", [])
    number = len(chapters) + 1
    title = chapter_title(number)
    preview = project.get("chapterTitlePreview", [])
    title = preview[number - 1].get("title", title) if number - 1 < len(preview) else title
    # 如果导演稿中有更合适的标题，优先使用
    if director_plan.get("chapter_goal"):
        # 保留默认标题，但可以将 goal 作为补充信息
        pass

    # 组装完整章节
    result = {
        "id": make_id("chapter"),
        "number": number,
        "title": title,
        "status": "pending",
        "wordCount": chapter_text.get("word_count", 0),
        "directorPlan": director_plan,
        "text": chapter_text.get("text", ""),
        "review": review,
        "stateDelta": state_delta,
        "statePreview": preview,
        "constraints": constraints,
        # 保存原始正文用于后续修改检测
        "_originalText": chapter_text.get("text", ""),
        # 附加新 Agent 的输出
        "memoryResult": memory_result,
        "foreshadowPlan": foreshadow_result,
        "characterPlan": char_plan,
        "createdAt": now_iso(),
    }

    logger.info(
        "[Pipeline] 章节生成完成: 第%d章「%s」, 字数=%d, 质量分=%s",
        number,
        title,
        result["wordCount"],
        review.get("total_score", "N/A"),
    )

    return result


async def generate_next_chapter(
    project: dict[str, Any],
    options: dict[str, Any],
) -> dict[str, Any]:
    """生成下一章（多 Agent 流水线 + 向后兼容）。

    优先使用多 Agent 流水线，Mock 模式下各 Agent 自动使用 Mock 逻辑。
    保留原有的 maybe_deepseek_chapter 作为降级方案。
    """
    # 优先使用多 Agent 流水线
    try:
        agent_chapter = await _agent_pipeline_chapter(project, options)
        if agent_chapter:
            return agent_chapter
    except Exception as exc:
        logger.warning("[Pipeline] 多 Agent 流水线失败，降级到原有模式: %s", exc)

    # 降级: 尝试原有 DeepSeek 单步生成
    ai_chapter = await maybe_deepseek_chapter(project, options)
    if ai_chapter:
        return ai_chapter

    # 最终降级: Mock 模式
    return build_mock_chapter(project, options)


async def generate_next_chapter_stream(
    project_id: str,
    options: dict[str, Any],
) -> AsyncGenerator[dict[str, Any], None]:
    """流式生成下一章（SSE 事件流）。

    生成的事件类型:
        - {"type": "agent_start", "agent": "constraint"} - Agent 开始执行
        - {"type": "agent_progress", "agent": "writer", "text": "..."} - Agent 进度
        - {"type": "agent_done", "agent": "review", "result": {...}} - Agent 完成
        - {"type": "rewrite", "attempt": 2, "reason": "质量评分72低于阈值75"} - 重写事件
        - {"type": "chapter_done", "chapter": {...}} - 章节生成完成
        - {"type": "error", "message": "..."} - 错误

    Yields:
        SSE 事件 dict
    """
    from app.services.project_service import project_service

    try:
        project = project_service.get_project(project_id)

        # 若项目没有蓝图，自动先构建
        if not project.get("storyBible"):
            yield {"type": "agent_start", "agent": "blueprint"}
            await project_service.build_project(project_id)
            project = project_service.get_project(project_id)
            yield {"type": "agent_done", "agent": "blueprint", "result": {"status": "ok"}}

        # 读取重写配置
        generation = settings_service.get_all(safe=False).get("generation", {})
        max_rewrites = int(generation.get("autoRewriteTimes", 2))
        quality_threshold = int(generation.get("qualityThreshold", 75))

        chapter = None
        rewrite_options = dict(options)

        for attempt in range(max_rewrites + 1):
            # 步骤 1: 记忆检索
            yield {"type": "agent_start", "agent": "memory"}
            context_builder = ContextBuilder()
            memory_ctx = context_builder.build_constraint_context(project)
            memory_ctx["project"] = project
            memory_ctx["taskDescription"] = "生成下一章"
            memory_result = await MemoryAgent().run(memory_ctx)
            yield {"type": "agent_done", "agent": "memory", "result": memory_result}

            # 步骤 2: 伏笔规划
            yield {"type": "agent_start", "agent": "foreshadow"}
            foreshadow_ctx = context_builder.build_constraint_context(project)
            foreshadow_ctx["project"] = project
            foreshadow_result = await ForeshadowAgent().run(foreshadow_ctx)
            yield {"type": "agent_done", "agent": "foreshadow", "result": foreshadow_result}

            # 步骤 3: 约束生成（使用伏笔规划结果）
            yield {"type": "agent_start", "agent": "constraint"}
            constraint_ctx = context_builder.build_constraint_context(project)
            constraint_ctx["project"] = project
            constraint_ctx["foreshadow_plan"] = foreshadow_result.get("foreshadow_plan", [])
            constraints = await ConstraintAgent().run(constraint_ctx)
            yield {"type": "agent_done", "agent": "constraint", "result": constraints}

            # 步骤 4: 角色戏份规划
            yield {"type": "agent_start", "agent": "character_director"}
            char_director_ctx = context_builder.build_director_context(project, constraints)
            char_director_ctx["project"] = project
            char_director_ctx["constraints"] = constraints
            char_plan = await CharacterDirectorAgent().run(char_director_ctx)
            yield {"type": "agent_done", "agent": "character_director", "result": char_plan}

            # 步骤 5: 导演稿生成（使用角色规划结果）
            yield {"type": "agent_start", "agent": "director"}
            director_ctx = context_builder.build_director_context(project, constraints)
            director_ctx["project"] = project
            director_ctx["character_plan"] = char_plan.get("character_plan", {})
            director_plan = await DirectorAgent().run(director_ctx)
            yield {"type": "agent_done", "agent": "director", "result": director_plan}

            # 步骤 6: 正文写作（流式）
            yield {"type": "agent_start", "agent": "writer"}
            writer_ctx = context_builder.build_writer_context(project, constraints, director_plan)
            writer_ctx["project"] = project
            chapter_text = None

            # 分场景生成判断
            stream_scenes = director_plan.get("scenes", [])
            if len(stream_scenes) >= 3:
                # 分场景流式生成
                yield {
                    "type": "agent_progress",
                    "agent": "writer",
                    "text": f"检测到 {len(stream_scenes)} 个场景，启用分场景生成模式...",
                }
                writer_agent = WriterAgent()
                async for event in writer_agent.write_by_scene_stream(
                    writer_ctx, stream_scenes, target_total_words=5000
                ):
                    if event.get("type") == "scene_start":
                        yield {
                            "type": "agent_progress",
                            "agent": "writer",
                            "text": f"[场景 {event.get('scene_number')}/{event.get('total_scenes')}] {event.get('scene_goal', '')}",
                        }
                    elif event.get("type") == "progress":
                        yield {"type": "agent_progress", "agent": "writer", "text": event.get("text", "")}
                    elif event.get("type") == "scene_done":
                        yield {
                            "type": "agent_progress",
                            "agent": "writer",
                            "text": f"[场景 {event.get('scene_number')} 完成, {event.get('word_count', 0)} 字]",
                        }
                    elif event.get("type") == "result":
                        chapter_text = event.get("data", {})
            else:
                # 整章流式生成（原有逻辑）
                async for event in WriterAgent().run_stream(writer_ctx):
                    if event.get("type") == "progress":
                        yield {"type": "agent_progress", "agent": "writer", "text": event.get("text", "")}
                    elif event.get("type") == "result":
                        chapter_text = event.get("data", {})
            yield {"type": "agent_done", "agent": "writer", "result": chapter_text}

            if not chapter_text:
                break

            # 步骤 4: 质量检查
            yield {"type": "agent_start", "agent": "review"}
            temp_chapter = {
                "text": chapter_text.get("text", ""),
                "title": director_plan.get("chapter_goal", ""),
                "number": len(project.get("chapters", [])) + 1,
                "wordCount": chapter_text.get("word_count", 0),
                "directorPlan": director_plan,
                "constraints": constraints,
            }
            review_ctx = context_builder.build_review_context(project, temp_chapter)
            review = await ReviewAgent().run(review_ctx)
            yield {"type": "agent_done", "agent": "review", "result": review}

            # 步骤 5: 状态提取
            yield {"type": "agent_start", "agent": "state_extractor"}
            state_extract_ctx = context_builder.build_state_extract_context(project, temp_chapter)
            state_extract_ctx["project"] = project
            state_result = await StateExtractorAgent().run(state_extract_ctx)
            yield {"type": "agent_done", "agent": "state_extractor", "result": state_result}

            # 步骤 6: 状态合并验证
            yield {"type": "agent_start", "agent": "state_merger"}
            state_delta = state_result.get("state_delta", {})
            merger = StateMerger()
            merged, preview = merger.validate_and_merge(project, state_delta)
            yield {"type": "agent_done", "agent": "state_merger", "result": {"status": "ok"}}

            # 组装完整章节
            chapters = project.get("chapters", [])
            number = len(chapters) + 1
            title = chapter_title(number)
            preview = project.get("chapterTitlePreview", [])
            title = preview[number - 1].get("title", title) if number - 1 < len(preview) else title

            chapter = {
                "id": make_id("chapter"),
                "number": number,
                "title": title,
                "status": "pending",
                "wordCount": chapter_text.get("word_count", 0),
                "directorPlan": director_plan,
                "text": chapter_text.get("text", ""),
                "review": review,
                "stateDelta": state_delta,
                "statePreview": preview,
                "constraints": constraints,
                "createdAt": now_iso(),
            }

            # 检查质量评分，决定是否重写
            total_score = int(review.get("total_score", review.get("totalScore", 100)))

            if total_score >= quality_threshold or attempt >= max_rewrites:
                break

            # 质量不达标，发送重写事件
            suggestions = review.get("rewrite_suggestions", "")
            if not suggestions:
                failed_tests = [
                    t for t in review.get("tests", [])
                    if not t.get("passed", True)
                ]
                suggestions = "；".join(
                    f"{t.get('name', '')}: {t.get('message', '')}" for t in failed_tests
                )

            reason = f"质量评分{total_score}低于阈值{quality_threshold}"
            yield {
                "type": "rewrite",
                "attempt": attempt + 1,
                "reason": reason,
            }

            logger.info(
                "[Pipeline-Stream] 质量评分 %d 低于阈值 %d，第 %d 次重写",
                total_score, quality_threshold, attempt + 1,
            )

            rewrite_options = dict(rewrite_options)
            rewrite_options["userInstruction"] = (
                f"上次质量评分 {total_score}，需要改进：{suggestions}"
            )

        if chapter:
            # 保存到 pendingChapters
            def mut(data: dict[str, Any]) -> dict[str, Any]:
                current = data["projects"][project_id]
                current.setdefault("pendingChapters", {})[chapter["id"]] = chapter
                current["updatedAt"] = now_iso()
                return chapter

            from app.core.storage import store
            store.update(mut)

            yield {"type": "chapter_done", "chapter": chapter}
        else:
            yield {"type": "error", "message": "章节生成失败"}

    except Exception as exc:
        logger.error("[Pipeline-Stream] 流式生成错误: %s", exc)
        yield {"type": "error", "message": str(exc)}


# ======================================================================
# 项目状态分析（保留原有功能）
# ======================================================================

def analyze_project_state(project: dict[str, Any]) -> dict[str, Any]:
    status = project.get("status", {})
    chapters = project.get("chapters", [])
    foreshadows = project.get("foreshadows", [])
    high_risk = [f for f in foreshadows if int(f.get("risk", 0)) >= 60]
    score = max(60, min(98, 92 - len(high_risk) * 3 + min(len(chapters), 10)))
    return {
        "generatedAt": now_iso(),
        "summary": "状态良好。主线推进稳定，伏笔风险可控。" if len(high_risk) <= 1 else "存在高风险伏笔，建议下一章安排回响或阶段性线索。",
        "score": score,
        "metrics": {
            "chapters": len(chapters),
            "mainProgress": status.get("mainProgress", 0),
            "foreshadowTotal": len(foreshadows),
            "highRiskForeshadows": len(high_risk),
            "characterCount": len(project.get("characters", [])),
            "eventCount": len(project.get("events", [])),
        },
    }
