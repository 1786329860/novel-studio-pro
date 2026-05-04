"""导演稿 Agent。

任务: 根据约束生成 3-6 个场景的导演稿。
这是流水线的第二步，为写作 Agent 提供详细的场景蓝图。

输出结构:
    - scenes: 场景列表（目标、冲突、转折、钩子、角色、地点、时间、情绪）
    - chapter_goal: 本章总体目标
    - chapter_arc: 本章情感弧线
    - pacing: 节奏描述
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any

from app.services.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class DirectorAgent(BaseAgent):
    """导演稿 Agent。

    根据约束包和项目状态，规划本章的场景结构、情感弧线和节奏。
    """

    def __init__(self) -> None:
        super().__init__()
        self._name = "DirectorAgent"
        self._description = "根据约束生成章节导演稿"

    @property
    def model_route_key(self) -> str:
        return "chapterDirector"

    @property
    def default_temperature(self) -> float:
        return 0.5

    @property
    def default_max_tokens(self) -> int:
        return 6000

    # ------------------------------------------------------------------
    # Prompt 构建
    # ------------------------------------------------------------------

    def build_messages(self, context: dict[str, Any]) -> list[dict[str, str]]:
        """构建导演稿生成的 Prompt。

        Args:
            context: 由 ContextBuilder.build_director_context() 构建的上下文

        Returns:
            消息列表
        """
        # 根据目标字数动态计算推荐场景数量
        target_words = context.get("target_total_words", 5000)
        if target_words <= 2000:
            scene_hint = "1-2 个场景（目标字数较少，每个场景应有足够篇幅展开）"
        elif target_words <= 4000:
            scene_hint = "2-3 个场景"
        elif target_words <= 6000:
            scene_hint = "3-4 个场景"
        else:
            scene_hint = "4-6 个场景"

        system_prompt = (
            "你是小说自动化创作系统的【导演稿 Agent】。\n"
            "你的任务是根据约束条件和项目状态，为下一章规划 3-6 个场景的导演稿。\n\n"
            "你必须输出严格 JSON，不要写任何解释文字。\n"
            "JSON 结构如下：\n"
            "{\n"
            '  "scenes": [\n'
            '    {\n'
            '      "number": 1,\n'
            '      "goal": "场景目标（一句话描述）",\n'
            '      "conflict": "核心冲突（一句话描述）",\n'
            '      "turning_point": "转折点（可选，非每个场景都有）",\n'
            '      "hook": "场景结尾钩子（吸引读者继续阅读）",\n'
            '      "characters": ["出场角色名列表"],\n'
            '      "location": "场景地点",\n'
            '      "time": "时间（禁止连续章节使用相同时间段开头，如：黎明、上午、正午、下午、傍晚、入夜、深夜、凌晨）",\n'
            '      "mood": "情绪基调（如：紧张、温馨、压抑）"\n'
            '    }\n'
            "  ],\n"
            '  "chapter_goal": "本章总体目标（一句话）",\n'
            '  "chapter_arc": "本章情感弧线描述",\n'
            '  "pacing": "节奏描述（如：缓起-渐紧-高潮-余韵）"\n'
            "}\n\n"
            "关键规则：\n"
            f"1. 场景数量控制在 {scene_hint}，根据约束中的 must_happen 合理分配\n"
            "2. 每个场景必须遵守约束中的 character_allocation\n"
            "3. 场景的视角必须符合 pov_plan\n"
            "4. 伏笔处理必须按 foreshadow_actions 的指令安排到对应场景\n"
            "5. 情感弧线要有起伏，不能平淡\n"
            "6. 最后一个场景必须有钩子，吸引读者看下一章\n"
            "7. 场景之间要有自然的过渡逻辑\n"
            "8. 绝对不能安排违反 must_not_happen 的内容\n"
            "9. 场景时间必须多样化！禁止连续两章使用相同的时间段开头。\n"
            "10. 场景地点必须多样化！不要每章都去档案室、暗巷等固定地点。\n"
            "11. 每章的场景结构应该不同：可以只有2个场景，也可以有4个；可以从黄昏开始，也可以从深夜开始。\n"
            "12. 禁止使用'手机震动/陌生号码发来消息/短信'作为推动情节的手段，每章最多出现1次。\n"
        )

        # 构建用户消息
        user_content = {
            "storyBibleSummary": context.get("storyBibleSummary", {}),
            "currentVolume": context.get("currentVolume", {}),
            "characters": context.get("characters", []),
            "foreshadows": context.get("foreshadows", []),
            "truthSource": context.get("truthSource", {}),
            "recentEvents": context.get("recentEvents", []),
            "recentChapterSummaries": context.get("recentChapterSummaries", []),
            "forbiddenRules": context.get("forbiddenRules", []),
            "constraints": context.get("constraints", {}),
            "styleProfile": context.get("styleProfile", ""),
            "mainConflict": context.get("mainConflict", ""),
            "endingDirection": context.get("endingDirection", ""),
        }

        user_prompt = (
            "请根据以下项目状态和约束条件，生成本章的导演稿：\n\n"
            f"{json.dumps(user_content, ensure_ascii=False, indent=2)}"
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    # ------------------------------------------------------------------
    # 响应解析
    # ------------------------------------------------------------------

    def parse_response(self, content: str) -> dict[str, Any]:
        """解析 AI 返回的导演稿 JSON。

        Args:
            content: AI 返回的 JSON 字符串

        Returns:
            结构化的导演稿 dict
        """
        data = self._safe_parse_json(content)

        # 确保必要字段存在
        data.setdefault("scenes", [])
        data.setdefault("chapter_goal", "")
        data.setdefault("chapter_arc", "")
        data.setdefault("pacing", "")

        # 验证场景结构
        for scene in data["scenes"]:
            scene.setdefault("number", 0)
            scene.setdefault("goal", "")
            scene.setdefault("conflict", "")
            scene.setdefault("turning_point", "")
            scene.setdefault("hook", "")
            scene.setdefault("characters", [])
            scene.setdefault("location", "")
            scene.setdefault("time", "")
            scene.setdefault("mood", "")

        return data

    # ------------------------------------------------------------------
    # Mock 模式
    # ------------------------------------------------------------------

    async def mock_run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Mock 模式: 根据项目实际状态动态生成导演稿。

        Args:
            context: 上下文数据

        Returns:
            模拟的导演稿输出
        """
        project = context.get("project", {})
        constraints = context.get("constraints", {})
        characters = project.get("characters", [])
        story_bible = project.get("storyBible", {})
        chapters = project.get("chapters", [])
        current_chapter = len(chapters)

        # 获取主要角色名
        protagonist = next(
            (c for c in characters if "主角" in c.get("role", "")),
            {"name": "主角"},
        )
        female_lead = next(
            (c for c in characters if "女主" in c.get("role", "")),
            {"name": "女主"},
        )
        support = next(
            (c for c in characters if "配角" in c.get("role", "")),
            {"name": "配角"},
        )

        # 从约束中获取必要信息
        must_happen = constraints.get("must_happen", [])
        pov_plan = constraints.get("pov_plan", {})
        foreshadow_actions = constraints.get("foreshadow_actions", [])

        # 根据当前章节阶段决定场景数量和风格
        if current_chapter <= 5:
            scene_count = 3
            arc_pattern = "铺垫-试探-悬念"
            pacing = "缓起-渐入-留钩"
        elif current_chapter <= 15:
            scene_count = 4
            arc_pattern = "日常-冲突-升级-转折"
            pacing = "平稳-渐紧-加速-悬念"
        else:
            scene_count = 5
            arc_pattern = "承接-推进-冲突-高潮-余韵"
            pacing = "缓起-渐紧-爆发-收束-钩子"

        # 生成场景
        scenes = []
        all_times = ["黎明", "上午", "正午", "下午", "傍晚", "入夜", "深夜", "凌晨"]
        random.shuffle(all_times)
        time_sequence = all_times[:scene_count]
        all_moods = ["平静", "微紧", "紧张", "爆发", "余韵", "悬疑", "温情", "压抑"]
        random.shuffle(all_moods)
        mood_sequence = all_moods[:scene_count]

        # 场景 1: 铺垫/承接
        scene1_goal = must_happen[0] if must_happen else f"{protagonist.get('name')}推进当前目标。"
        scenes.append({
            "number": 1,
            "goal": scene1_goal,
            "conflict": f"{protagonist.get('name')}面临选择困境。",
            "turning_point": "",
            "hook": f"一个意想不到的消息打破了{protagonist.get('name')}的计划。",
            "characters": [protagonist.get("name", "主角")],
            "location": self._get_location(project, 0),
            "time": time_sequence[0],
            "mood": mood_sequence[0],
        })

        # 场景 2: 推进/发展
        scene2_chars = [protagonist.get("name", "主角")]
        if female_lead.get("name"):
            scene2_chars.append(female_lead.get("name"))
        scenes.append({
            "number": 2,
            "goal": must_happen[1] if len(must_happen) > 1 else "角色关系推进。",
            "conflict": f"{protagonist.get('name')}与{female_lead.get('name', '配角')}之间出现分歧。",
            "turning_point": "",
            "hook": "一段对话揭示了隐藏的信息。",
            "characters": scene2_chars,
            "location": self._get_location(project, 1),
            "time": time_sequence[1],
            "mood": mood_sequence[1],
        })

        # 场景 3: 冲突/升级
        scene3_chars = [protagonist.get("name", "主角")]
        if support.get("name"):
            scene3_chars.append(support.get("name"))
        scenes.append({
            "number": 3,
            "goal": "矛盾升级，局势复杂化。",
            "conflict": f"外部压力迫使{protagonist.get('name')}做出艰难决定。",
            "turning_point": "一个关键线索改变了局势。",
            "hook": "危机迫在眉睫。",
            "characters": scene3_chars,
            "location": self._get_location(project, 2),
            "time": time_sequence[2],
            "mood": mood_sequence[2],
        })

        # 场景 4: 高潮（如果需要）
        if scene_count >= 4:
            scenes.append({
                "number": 4,
                "goal": "本章核心冲突爆发。",
                "conflict": f"{protagonist.get('name')}直面最大挑战。",
                "turning_point": "局势出现意外转折。",
                "hook": "一个更大的谜团浮出水面。",
                "characters": [protagonist.get("name", "主角"), female_lead.get("name", "女主")],
                "location": self._get_location(project, 3),
                "time": time_sequence[3],
                "mood": mood_sequence[3],
            })

        # 场景 5: 余韵/钩子（如果需要）
        if scene_count >= 5:
            scenes.append({
                "number": 5,
                "goal": "收束本章，为下一章埋下钩子。",
                "conflict": "表面平静下暗流涌动。",
                "turning_point": "",
                "hook": "结尾揭示一个令人不安的细节。",
                "characters": [protagonist.get("name", "主角")],
                "location": self._get_location(project, 4),
                "time": time_sequence[4],
                "mood": mood_sequence[4],
            })

        # 如果有伏笔处理指令，分配到合适的场景
        for fs_action in foreshadow_actions:
            target_scene = min(len(scenes) - 1, 1)  # 通常放在第 2 个场景
            if scenes:
                scenes[target_scene]["goal"] += f"（伏笔「{fs_action.get('foreshadow_id', '')}」{fs_action.get('action', '回响')}）"

        # 生成章节目标
        chapter_goal = must_happen[0] if must_happen else "推进主线剧情。"

        return {
            "scenes": scenes,
            "chapter_goal": chapter_goal,
            "chapter_arc": arc_pattern,
            "pacing": pacing,
        }

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _get_location(project: dict[str, Any], index: int) -> str:
        """根据项目类型和索引获取场景地点。

        Args:
            project: 项目数据
            index: 场景索引

        Returns:
            场景地点描述
        """
        genre = project.get("storyBible", {}).get("genre", "奇幻")
        locations_map = {
            "奇幻": ["城门广场", "魔法塔内部", "密林深处", "古战场遗迹", "星空下营地", "地下洞穴", "精灵集市", "龙巢边缘", "诅咒沼泽", "浮空岛码头"],
            "玄幻": ["宗门大殿", "修炼密室", "灵药园", "比武场", "悬崖边", "藏经阁", "炼丹房", "灵兽山脉", "古遗迹入口", "拍卖行", "传送阵前", "禁地边缘"],
            "科幻": ["空间站走廊", "实验室", "星舰驾驶舱", "废墟城市", "量子隧道", "休眠舱", "外星集市", "黑洞观测台", "生态穹顶", "地下掩体"],
            "都市": ["办公室", "咖啡馆", "公寓", "停车场", "天台", "酒吧", "出租屋", "地铁站", "商场", "健身房", "便利店", "餐厅", "公园长椅", "地下车库"],
            "悬疑": ["案发现场", "档案室", "暗巷", "审讯室", "钟楼", "河边", "废弃工厂", "医院走廊", "死者家中", "天台", "地下车库", "咖啡馆", "老式公寓", "火车站", "码头"],
            "言情": ["校园", "图书馆", "雨中街道", "海边", "客厅", "咖啡厅", "公园", "天台", "厨房", "书店", "花店", "电影院"],
        }
        locations = locations_map.get(genre, ["场景一", "场景二", "场景三", "场景四", "场景五"])
        return locations[index % len(locations)]
