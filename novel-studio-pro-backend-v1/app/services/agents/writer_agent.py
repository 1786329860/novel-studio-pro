"""正文写作 Agent。

任务: 根据导演稿写正文。
这是流水线的第三步，是实际产出章节内容的核心 Agent。

输出结构:
    - text: 正文内容（3000-8000字）
    - word_count: 字数统计
    - dialogue_ratio: 对话占比
    - narrative_style: 叙事风格
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class WriterAgent(BaseAgent):
    """正文写作 Agent。

    根据导演稿、约束包和项目状态，撰写高质量的章节正文。
    """

    def __init__(self) -> None:
        super().__init__()
        self._name = "WriterAgent"
        self._description = "根据导演稿撰写章节正文"

    @property
    def model_route_key(self) -> str:
        return "chapterWriting"

    @property
    def default_temperature(self) -> float:
        return 0.9

    @property
    def default_max_tokens(self) -> int:
        return 12000

    # ------------------------------------------------------------------
    # Prompt 构建
    # ------------------------------------------------------------------

    def build_messages(self, context: dict[str, Any]) -> list[dict[str, str]]:
        """构建正文写作的 Prompt。

        Args:
            context: 由 ContextBuilder.build_writer_context() 构建的上下文

        Returns:
            消息列表
        """
        system_prompt = (
            "你是小说自动化创作系统的【正文写作 Agent】。\n"
            "你的任务是根据导演稿、约束条件和项目状态，撰写高质量的章节正文。\n\n"
            "你必须输出严格 JSON，不要写任何解释文字。\n"
            "JSON 结构如下：\n"
            "{\n"
            '  "text": "正文内容（3000-8000字）",\n'
            '  "word_count": 5000,\n'
            '  "dialogue_ratio": 0.3,\n'
            '  "narrative_style": "第三人称有限视角"\n'
            "}\n\n"
            "写作规则：\n"
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
            "14. 对话占比控制在 20%-40% 之间"
        )

        # 构建用户消息
        user_content = {
            "storyBibleSummary": context.get("storyBibleSummary", {}),
            "styleProfile": context.get("styleProfile", ""),
            "mainTheme": context.get("mainTheme", ""),
            "constraints": context.get("constraints", {}),
            "directorPlan": context.get("directorPlan", {}),
            "characters": context.get("characters", []),
            "recentChapterSummaries": context.get("recentChapterSummaries", []),
            "lastChapterTail": context.get("lastChapterTail", ""),
            "forbiddenRules": context.get("forbiddenRules", []),
            "foreshadows": context.get("foreshadows", []),
            "relationships": context.get("relationships", []),
        }

        user_prompt = (
            "请根据以下导演稿和约束条件，撰写章节正文：\n\n"
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
        """解析 AI 返回的正文 JSON。

        Args:
            content: AI 返回的 JSON 字符串

        Returns:
            结构化的正文 dict
        """
        data = self._safe_parse_json(content)

        text = data.get("text", "")
        word_count = data.get("word_count", len(text))

        return {
            "text": text,
            "word_count": word_count,
            "dialogue_ratio": data.get("dialogue_ratio", 0.3),
            "narrative_style": data.get("narrative_style", "第三人称有限视角"),
        }

    # ------------------------------------------------------------------
    # Mock 模式
    # ------------------------------------------------------------------

    async def mock_run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Mock 模式: 根据导演稿和项目状态动态生成模拟正文。

        Args:
            context: 上下文数据

        Returns:
            模拟的正文输出
        """
        project = context.get("project", {})
        constraints = context.get("constraints", {})
        director_plan = context.get("directorPlan", {})
        characters = project.get("characters", [])
        story_bible = project.get("storyBible", {})
        chapters = project.get("chapters", [])

        # 获取角色名
        protagonist = next(
            (c for c in characters if "主角" in c.get("role", "")),
            {"name": "江离"},
        )
        female_lead = next(
            (c for c in characters if "女主" in c.get("role", "")),
            {"name": "沈烬"},
        )
        support = next(
            (c for c in characters if "配角" in c.get("role", "")),
            {"name": "苏照"},
        )

        p_name = protagonist.get("name", "江离")
        f_name = female_lead.get("name", "沈烬")
        s_name = support.get("name", "苏照")

        # 获取场景信息
        scenes = director_plan.get("scenes", [])
        if not scenes:
            scenes = [
                {"goal": "推进主线", "location": "城门广场", "time": "清晨", "mood": "平静"},
                {"goal": "角色互动", "location": "茶楼", "time": "午后", "mood": "微紧"},
                {"goal": "冲突升级", "location": "暗巷", "time": "深夜", "mood": "紧张"},
            ]

        # 获取文风
        genre = story_bible.get("genre", "奇幻")
        style_constraints = constraints.get("style_constraints", [])

        # 根据场景动态生成正文段落
        paragraphs = []

        # 如果有上一章结尾，生成衔接段落
        last_tail = context.get("lastChapterTail", "")
        if last_tail and chapters:
            paragraphs.append(
                f"上一章的余波尚未散去。{p_name}站在原地，回想着刚才发生的一切，"
                f"心中隐隐感到不安。"
            )

        # 为每个场景生成段落
        for i, scene in enumerate(scenes):
            location = scene.get("location", "某处")
            time_str = scene.get("time", "午后")
            mood = scene.get("mood", "平静")
            goal = scene.get("goal", "推进剧情")
            scene_chars = scene.get("characters", [p_name])

            # 场景开头 - 环境描写
            env_templates = [
                f"{time_str}的{location}笼罩在一层薄雾中，{mood}的气氛弥漫在空气中。",
                f"{location}在{time_str}显得格外安静，只有远处传来几声不知名的鸟鸣。",
                f"{time_str}的光线斜斜地照进{location}，在地面投下长长的影子。",
            ]
            paragraphs.append(env_templates[i % len(env_templates)])

            # 场景发展 - 角色行动
            if p_name in scene_chars and f_name in scene_chars:
                paragraphs.append(
                    f"{p_name}没有说话，目光扫过{location}的每一个角落。"
                    f"{f_name}跟在他身后，脚步很轻，像是怕惊动什么。"
                    f"两人之间的沉默比任何对话都更有重量。"
                )
                paragraphs.append(
                    f"「你确定要这么做？」{f_name}终于开口，声音压得很低。\n\n"
                    f"{p_name}停下脚步，没有回头。「没有别的选择了。」\n\n"
                    f"「每次你这么说，后面都会出事。」{f_name}的语气里带着一丝无奈。"
                )
            elif p_name in scene_chars:
                paragraphs.append(
                    f"{p_name}独自走进{location}，手指无意识地摩挲着袖口的边缘。"
                    f"他在等一个人，或者说，在等一个答案。"
                )
                paragraphs.append(
                    f"空气中有一股若有若无的焦味，和三年前那个夜晚一模一样。"
                    f"{p_name}的瞳孔微微收缩，但他的表情没有变化。"
                    f"多年的习惯让他学会了在最不安的时候保持最平静的样子。"
                )
            elif f_name in scene_chars:
                paragraphs.append(
                    f"{f_name}没有按照约定等待。她独自绕到{location}的后面，"
                    f"推开一扇几乎被藤蔓遮住的小门。"
                )
                paragraphs.append(
                    f"门后是一间废弃的房间，桌上积灰很厚，唯有最里面的木匣被人动过。"
                    f"{f_name}垂下眼，没有立刻把这件事告诉任何人。"
                )

            # 场景中的配角互动
            if s_name in scene_chars and i > 0:
                paragraphs.append(
                    f"{s_name}靠在墙边，手里转着一枚旧铜扣。"
                    f"「有个消息你们可能想知道，」他说，语气比平时认真了几分，"
                    f"「不过听完之后，可能会让事情变得更复杂。」"
                )

            # 场景结尾 - 钩子
            hook_templates = [
                f"远处传来一声沉闷的钟响，{p_name}抬头望去，"
                f"钟楼的方向升起了一缕几乎看不见的烟。",
                f"就在这时，一个不该出现在这里的人从阴影中走了出来。",
                f"{p_name}低头看着手中那张被揉皱的纸条，上面的字迹让他愣住了。"
                f"那不是任何人的笔迹——那是他自己的。",
                f"风从窗缝灌入，把桌上那页残纸掀开一角。纸背上只有两个字。",
            ]
            paragraphs.append(hook_templates[i % len(hook_templates)])

            # 场景间过渡
            if i < len(scenes) - 1:
                paragraphs.append("")

        text = "\n\n".join(paragraphs)
        word_count = len(text)

        # 估算对话占比
        dialogue_chars = sum(1 for c in text if c in "「」""")
        dialogue_ratio = round(dialogue_chars / max(word_count, 1), 2)

        # 确定叙事风格
        pov_plan = constraints.get("pov_plan", {})
        narrative_style = "第三人称有限视角"
        if pov_plan.get("primary") and pov_plan.get("secondary"):
            narrative_style = (
                f"第三人称有限视角；主视角：{pov_plan['primary']}，"
                f"次视角：{pov_plan['secondary']}"
            )

        return {
            "text": text,
            "word_count": word_count,
            "dialogue_ratio": min(dialogue_ratio, 0.4),
            "narrative_style": narrative_style,
        }
