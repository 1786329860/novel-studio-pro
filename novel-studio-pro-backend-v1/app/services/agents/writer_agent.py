"""正文写作 Agent。

任务: 根据导演稿写正文。
这是流水线的第三步，是实际产出章节内容的核心 Agent。

输出结构:
    - text: 正文内容（3000-8000字）
    - word_count: 字数统计
    - dialogue_ratio: 对话占比
    - narrative_style: 叙事风格

支持两种写作模式:
    - 整章生成: 一次性生成整章正文（原有逻辑）
    - 分场景生成: 逐场景生成正文，自动拼接（新增）
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from app.services.agents.base import BaseAgent
from app.services.deepseek_client import deepseek_client
from app.services.prompt_templates import build_scene_writing_prompt
from app.services.settings_service import settings_service

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
            '  "text": "正文内容",\n'
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
            f"13. 目标字数：{context.get('target_total_words', 5000)} 字"
            f"（严格控制在 {context.get('min_words', 3000)}-{context.get('target_total_words', 5000)} 字范围内）\n"
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
    # 流式执行
    # ------------------------------------------------------------------

    async def run_stream(self, context: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
        """流式执行正文写作。

        使用 deepseek_client.chat_stream() 实现逐字输出。
        Mock 模式下回退到 mock_run。

        Yields:
            {"type": "progress", "text": "..."} - 文本片段
            {"type": "result", "data": {...}} - 最终结构化结果
        """
        generation = settings_service.get_generation()
        is_mock = not deepseek_client.is_ready()
        is_ready = deepseek_client.is_ready()

        if is_mock or not is_ready:
            # Mock 模式：一次性返回结果
            result = await self.mock_run(context)
            yield {"type": "result", "data": result}
            return

        # 真实 AI 流式模式
        try:
            messages = self.build_messages(context)
            routes = settings_service.get_all(safe=False).get("modelRoutes", {})
            route = routes.get(self.model_route_key, {})
            target_words = context.get("target_total_words", 5000)
            calc_max = max(500, int(target_words * 1.8) + 200)
            route_max = int(route.get("maxOutputTokens", self.default_max_tokens))

            full_content = ""
            async for chunk in deepseek_client.chat_stream(
                messages=messages,
                model=route.get("model"),
                temperature=float(route.get("temperature", self.default_temperature)),
                max_tokens=min(calc_max, route_max),
                json_mode=True,
                task_name=self.name,
            ):
                full_content = chunk  # JSON 模式下最后一次 yield 是完整 JSON
                # 尝试提取 text 字段进行实时展示
                try:
                    parsed = json.loads(chunk)
                    text = parsed.get("text", "")
                    if text:
                        yield {"type": "progress", "text": text}
                except json.JSONDecodeError:
                    # 还在累积中，跳过
                    pass

            # 解析最终结果
            result = self.parse_response(full_content)
            yield {"type": "result", "data": result}
            logger.info("[AI] %s 流式执行成功", self.name)
        except Exception as exc:
            logger.warning("[AI] %s 流式执行失败，回退 Mock: %s", self.name, exc)
            try:
                result = await self.mock_run(context)
                yield {"type": "result", "data": result}
            except Exception:
                yield {"type": "result", "data": self._fallback_mock(context)}

    # ------------------------------------------------------------------
    # 分场景写作
    # ------------------------------------------------------------------

    async def write_by_scene(
        self,
        context: dict[str, Any],
        scenes: list[dict[str, Any]],
        target_total_words: int = 5000,
    ) -> dict[str, Any]:
        """分场景生成正文。

        逐场景调用 AI 生成正文，自动拼接场景过渡段落，控制总字数在目标范围内。

        Args:
            context: 上下文数据（包含 project, constraints 等）
            scenes: 导演稿的场景列表
            target_total_words: 目标总字数

        Returns:
            与 run() 输出格式一致的结构化 dict
        """
        generation = settings_service.get_generation()
        is_mock = not deepseek_client.is_ready()
        is_ready = deepseek_client.is_ready()

        project = context.get("project", {})

        # 根据场景数量和重要性分配字数
        scene_word_counts = self._allocate_word_counts(
            scenes, target_total_words
        )

        scene_texts: list[str] = []
        previous_scene_text = ""

        for i, scene in enumerate(scenes):
            scene_target = scene_word_counts[i]
            logger.info(
                "[Writer] 分场景写作: 场景 %d/%d, 目标字数=%d",
                i + 1, len(scenes), scene_target,
            )

            if is_mock or not is_ready:
                # Mock 模式：为每个场景生成独立的模板正文
                scene_result = await self._mock_single_scene(
                    context, scene, previous_scene_text, scene_target
                )
            else:
                # AI 模式：调用 AI 生成单个场景
                scene_result = await self._ai_write_single_scene(
                    context, scene, previous_scene_text, scene_target
                )

            scene_text = scene_result.get("text", "")

            # 添加场景过渡段落（非最后一个场景）
            if i < len(scenes) - 1 and scene_text:
                transition = self._generate_transition(scene, scenes[i + 1])
                scene_text = scene_text + "\n\n" + transition

            scene_texts.append(scene_text)
            previous_scene_text = scene_text

        # 拼接所有场景正文
        full_text = "\n\n".join(scene_texts)

        # 硬性截断：如果总字数超过目标上限的120%，截断到最后一个完整段落
        max_words = context.get("max_words", target_total_words * 1.2)
        if len(full_text) > max_words:
            paragraphs = full_text.split('\n\n')
            truncated = []
            current_len = 0
            for p in paragraphs:
                if current_len + len(p) > max_words and truncated:
                    break
                truncated.append(p)
                current_len += len(p)
            full_text = '\n\n'.join(truncated)
            logger.warning("[Writer] 总字数 %d 超过上限 %d，已截断", len(full_text), int(max_words))

        word_count = len(full_text)

        # 估算对话占比
        dialogue_chars = sum(1 for c in full_text if c in "\u300c\u300d")
        dialogue_ratio = round(dialogue_chars / max(word_count, 1), 2)

        # 确定叙事风格
        constraints = context.get("constraints", {})
        pov_plan = constraints.get("pov_plan", {})
        narrative_style = "第三人称有限视角"
        if pov_plan.get("primary") and pov_plan.get("secondary"):
            narrative_style = (
                f"第三人称有限视角；主视角：{pov_plan['primary']}，"
                f"次视角：{pov_plan['secondary']}"
            )

        logger.info(
            "[Writer] 分场景写作完成: %d 个场景, 总字数=%d",
            len(scenes), word_count,
        )

        return {
            "text": full_text,
            "word_count": word_count,
            "dialogue_ratio": min(dialogue_ratio, 0.4),
            "narrative_style": narrative_style,
        }

    async def write_by_scene_stream(
        self,
        context: dict[str, Any],
        scenes: list[dict[str, Any]],
        target_total_words: int = 5000,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """分场景流式生成正文。

        逐场景调用 AI 生成正文，每个场景的进度都会 yield 出去。

        Yields:
            {"type": "scene_start", "scene_number": 1, "total_scenes": 5}
            {"type": "progress", "text": "..."} - 文本片段
            {"type": "scene_done", "scene_number": 1, "word_count": 1200}
            {"type": "result", "data": {...}} - 最终结构化结果
        """
        generation = settings_service.get_generation()
        is_mock = not deepseek_client.is_ready()
        is_ready = deepseek_client.is_ready()

        project = context.get("project", {})

        # 根据场景数量和重要性分配字数
        scene_word_counts = self._allocate_word_counts(
            scenes, target_total_words
        )

        scene_texts: list[str] = []
        previous_scene_text = ""

        for i, scene in enumerate(scenes):
            scene_target = scene_word_counts[i]
            yield {
                "type": "scene_start",
                "scene_number": i + 1,
                "total_scenes": len(scenes),
                "scene_goal": scene.get("goal", ""),
            }

            if is_mock or not is_ready:
                # Mock 模式
                scene_result = await self._mock_single_scene(
                    context, scene, previous_scene_text, scene_target
                )
                scene_text = scene_result.get("text", "")
                yield {"type": "progress", "text": scene_text}
            else:
                # AI 流式模式
                scene_text = ""
                try:
                    messages = build_scene_writing_prompt(
                        project, scene, previous_scene_text, scene_target
                    )
                    routes = settings_service.get_all(safe=False).get("modelRoutes", {})
                    route = routes.get(self.model_route_key, {})
                    scene_calc_max = max(500, int(scene_target * 1.8) + 200)
                    scene_route_max = int(route.get("maxOutputTokens", self.default_max_tokens))

                    full_content = ""
                    async for chunk in deepseek_client.chat_stream(
                        messages=messages,
                        model=route.get("model"),
                        temperature=float(route.get("temperature", self.default_temperature)),
                        max_tokens=min(scene_calc_max, scene_route_max),
                        json_mode=True,
                        task_name=f"{self.name}_scene_{i + 1}",
                    ):
                        full_content = chunk
                        try:
                            parsed = json.loads(chunk)
                            t = parsed.get("text", "")
                            if t:
                                scene_text = t
                                yield {"type": "progress", "text": t}
                        except json.JSONDecodeError:
                            pass

                    # 解析最终结果
                    if full_content:
                        data = self._safe_parse_json(full_content)
                        scene_text = data.get("text", scene_text)
                except Exception as exc:
                    logger.warning(
                        "[Writer] 场景 %d AI 生成失败，回退 Mock: %s",
                        i + 1, exc,
                    )
                    scene_result = await self._mock_single_scene(
                        context, scene, previous_scene_text, scene_target
                    )
                    scene_text = scene_result.get("text", "")
                    yield {"type": "progress", "text": scene_text}

            # 添加场景过渡段落
            if i < len(scenes) - 1 and scene_text:
                transition = self._generate_transition(scene, scenes[i + 1])
                scene_text = scene_text + "\n\n" + transition

            scene_texts.append(scene_text)
            previous_scene_text = scene_text

            yield {
                "type": "scene_done",
                "scene_number": i + 1,
                "word_count": len(scene_text),
            }

        # 拼接所有场景正文
        full_text = "\n\n".join(scene_texts)

        # 硬性截断：如果总字数超过目标上限的120%，截断到最后一个完整段落
        max_words = context.get("max_words", target_total_words * 1.2)
        if len(full_text) > max_words:
            paragraphs = full_text.split('\n\n')
            truncated = []
            current_len = 0
            for p in paragraphs:
                if current_len + len(p) > max_words and truncated:
                    break
                truncated.append(p)
                current_len += len(p)
            full_text = '\n\n'.join(truncated)
            logger.warning("[Writer] 总字数 %d 超过上限 %d，已截断", len(full_text), int(max_words))

        word_count = len(full_text)

        # 估算对话占比
        dialogue_chars = sum(1 for c in full_text if c in "\u300c\u300d")
        dialogue_ratio = round(dialogue_chars / max(word_count, 1), 2)

        # 确定叙事风格
        constraints = context.get("constraints", {})
        pov_plan = constraints.get("pov_plan", {})
        narrative_style = "第三人称有限视角"
        if pov_plan.get("primary") and pov_plan.get("secondary"):
            narrative_style = (
                f"第三人称有限视角；主视角：{pov_plan['primary']}，"
                f"次视角：{pov_plan['secondary']}"
            )

        result = {
            "text": full_text,
            "word_count": word_count,
            "dialogue_ratio": min(dialogue_ratio, 0.4),
            "narrative_style": narrative_style,
        }

        yield {"type": "result", "data": result}

    # ------------------------------------------------------------------
    # 分场景辅助方法
    # ------------------------------------------------------------------

    def _allocate_word_counts(
        self,
        scenes: list[dict[str, Any]],
        target_total: int,
    ) -> list[int]:
        """根据场景重要性分配字数。

        有冲突或转折的场景分配更多字数。

        Args:
            scenes: 场景列表
            target_total: 目标总字数

        Returns:
            每个场景的目标字数列表
        """
        if not scenes:
            return []

        # 计算每个场景的权重
        weights: list[float] = []
        for scene in scenes:
            weight = 1.0
            # 有冲突的场景权重更高
            if scene.get("conflict"):
                weight += 0.3
            # 有转折的场景权重更高
            if scene.get("turning_point"):
                weight += 0.2
            # 最后一个场景（钩子）权重略高
            if scene == scenes[-1]:
                weight += 0.1
            weights.append(weight)

        total_weight = sum(weights)
        # 按权重分配字数
        allocated = [int(target_total * w / total_weight) for w in weights]

        # 修正舍入误差，确保总和等于目标
        diff = target_total - sum(allocated)
        if diff != 0 and allocated:
            # 把误差加到最后一个场景
            allocated[-1] += diff

        return allocated

    async def _ai_write_single_scene(
        self,
        context: dict[str, Any],
        scene: dict[str, Any],
        previous_scene_text: str,
        target_word_count: int,
    ) -> dict[str, Any]:
        """使用 AI 生成单个场景的正文。

        Args:
            context: 上下文数据
            scene: 场景导演稿
            previous_scene_text: 前一场景正文
            target_word_count: 目标字数

        Returns:
            包含 text 和 word_count 的 dict
        """
        project = context.get("project", {})
        messages = build_scene_writing_prompt(
            project, scene, previous_scene_text, target_word_count
        )

        routes = settings_service.get_all(safe=False).get("modelRoutes", {})
        route = routes.get(self.model_route_key, {})

        # max_tokens 基于目标字数计算（汉字约1.5 token/字），加上JSON包装开销
        scene_max_tokens = max(500, int(target_word_count * 1.8) + 200)
        route_max = int(route.get("maxOutputTokens", self.default_max_tokens))
        final_max_tokens = min(scene_max_tokens, route_max)

        content = await deepseek_client.chat(
            messages=messages,
            model=route.get("model"),
            temperature=float(route.get("temperature", self.default_temperature)),
            max_tokens=final_max_tokens,
            json_mode=True,
            task_name=f"{self.name}_scene",
        )

        data = self._safe_parse_json(content)
        text = data.get("text", "")
        word_count = data.get("word_count", len(text))

        return {"text": text, "word_count": word_count}

    async def _mock_single_scene(
        self,
        context: dict[str, Any],
        scene: dict[str, Any],
        previous_scene_text: str,
        target_word_count: int,
    ) -> dict[str, Any]:
        """Mock 模式下生成单个场景的正文。

        Args:
            context: 上下文数据
            scene: 场景导演稿
            previous_scene_text: 前一场景正文
            target_word_count: 目标字数

        Returns:
            包含 text 和 word_count 的 dict
        """
        project = context.get("project", {})
        characters = project.get("characters", [])

        # 获取出场角色名
        scene_chars = scene.get("characters", [])
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

        location = scene.get("location", "某处")
        time_str = scene.get("time", "午后")
        mood = scene.get("mood", "平静")
        goal = scene.get("goal", "推进剧情")
        conflict = scene.get("conflict", "")
        hook = scene.get("hook", "")

        paragraphs = []

        # 与前一场的衔接
        if previous_scene_text:
            paragraphs.append(
                f"风从远处吹来，带着一丝若有若无的凉意。"
                f"{p_name}深吸一口气，目光投向{location}的方向。"
            )

        # 环境描写
        env_templates = [
            f"{time_str}的{location}笼罩在一层薄雾中，{mood}的气氛弥漫在空气中。",
            f"{location}在{time_str}显得格外安静，只有远处传来几声不知名的鸟鸣。",
            f"{time_str}的光线斜斜地照进{location}，在地面投下长长的影子。",
        ]
        paragraphs.append(env_templates[scene.get("number", 1) % len(env_templates)])

        # 角色行动
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

        # 配角互动
        if s_name in scene_chars:
            paragraphs.append(
                f"{s_name}靠在墙边，手里转着一枚旧铜扣。"
                f"「有个消息你们可能想知道，」他说，语气比平时认真了几分，"
                f"「不过听完之后，可能会让事情变得更复杂。」"
            )

        # 冲突描写
        if conflict:
            paragraphs.append(
                f"局势的变化比预想中来得更快。{conflict}"
            )

        # 钩子
        if hook:
            paragraphs.append(hook)
        else:
            hook_templates = [
                f"远处传来一声沉闷的钟响，{p_name}抬头望去，"
                f"钟楼的方向升起了一缕几乎看不见的烟。",
                f"就在这时，一个不该出现在这里的人从阴影中走了出来。",
                f"{p_name}低头看着手中那张被揉皱的纸条，上面的字迹让他愣住了。",
            ]
            paragraphs.append(hook_templates[scene.get("number", 1) % len(hook_templates)])

        text = "\n\n".join(paragraphs)
        return {"text": text, "word_count": len(text)}

    @staticmethod
    def _generate_transition(
        current_scene: dict[str, Any],
        next_scene: dict[str, Any],
    ) -> str:
        """生成两个场景之间的过渡段落。

        根据场景的时间、地点变化生成自然的过渡。

        Args:
            current_scene: 当前场景
            next_scene: 下一个场景

        Returns:
            过渡段落文本
        """
        current_time = current_scene.get("time", "")
        next_time = next_scene.get("time", "")
        current_location = current_scene.get("location", "")
        next_location = next_scene.get("location", "")

        # 时间变化
        time_transitions = {
            ("清晨", "午后"): "午后的阳光渐渐变得炽烈，时间在不知不觉中流逝。",
            ("午后", "黄昏"): "天边开始泛起橙红色的光，黄昏悄然降临。",
            ("黄昏", "深夜"): "夜色如墨，城市的灯火次第亮起。",
            ("深夜", "黎明"): "漫长的夜终于过去，东方的天际露出一抹鱼肚白。",
        }

        transition = ""

        # 查找时间过渡
        time_key = (current_time, next_time)
        if time_key in time_transitions:
            transition = time_transitions[time_key]
        elif current_time != next_time and current_time and next_time:
            transition = f"时间从{current_time}转到了{next_time}。"

        # 地点变化
        if current_location != next_location and current_location and next_location:
            if transition:
                transition += f" {next_location}的景象与之前截然不同。"
            else:
                transition = f"场景从{current_location}转移到了{next_location}。"

        # 如果没有变化，使用通用过渡
        if not transition:
            transition = ""

        return transition

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
