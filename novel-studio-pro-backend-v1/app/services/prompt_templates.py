from __future__ import annotations

import json
from typing import Any


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
                "你是强自动化长篇小说创作引擎的故事蓝图 Agent。"
                "用户只提供小说名和粗略大纲，你必须自动生成完整故事蓝图。"
                "必须输出严格 JSON，不要写解释。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请根据输入生成完整项目初始化数据。必须包含："
                "storyBible, volumePlan, stagePlan, chapterTitlePreview, characters, relationships, "
                "foreshadows, truthSource, status, memory。\n"
                "输入如下：\n"
                f"{json.dumps(payload, ensure_ascii=False)}"
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
