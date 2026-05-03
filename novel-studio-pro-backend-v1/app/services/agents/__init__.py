"""多 Agent 小说创作系统。

本模块实现了小说自动化创作的多 Agent 协作框架，每个 Agent 负责一个专门任务，
通过结构化 JSON 输入输出串联完成完整的章节生成流程。

Agent 执行流水线:
    1. MemoryAgent          - 记忆检索
    2. ForeshadowAgent      - 伏笔规划
    3. ConstraintAgent      - 约束生成
    4. CharacterDirectorAgent - 角色戏份规划
    5. DirectorAgent        - 导演稿生成
    6. WriterAgent          - 正文写作
    7. ReviewAgent          - 质量检查
    8. StateExtractorAgent  - 状态提取
    9. StateMerger          - 状态合并

辅助模块:
    - ContextBuilder: 为每个 Agent 构建精确的上下文包
    - BaseAgent: 所有 Agent 的基类
"""

from app.services.agents.base import BaseAgent
from app.services.agents.context_builder import ContextBuilder
from app.services.agents.constraint_agent import ConstraintAgent
from app.services.agents.director_agent import DirectorAgent
from app.services.agents.writer_agent import WriterAgent
from app.services.agents.review_agent import ReviewAgent
from app.services.agents.state_extractor_agent import StateExtractorAgent
from app.services.agents.state_merger import StateMerger
from app.services.agents.memory_agent import MemoryAgent
from app.services.agents.character_director_agent import CharacterDirectorAgent
from app.services.agents.foreshadow_agent import ForeshadowAgent

__all__ = [
    "BaseAgent",
    "ContextBuilder",
    "ConstraintAgent",
    "DirectorAgent",
    "WriterAgent",
    "ReviewAgent",
    "StateExtractorAgent",
    "StateMerger",
    "MemoryAgent",
    "CharacterDirectorAgent",
    "ForeshadowAgent",
]
