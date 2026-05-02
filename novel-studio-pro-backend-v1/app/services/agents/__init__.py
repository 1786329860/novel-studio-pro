"""多 Agent 小说创作系统。

本模块实现了小说自动化创作的多 Agent 协作框架，每个 Agent 负责一个专门任务，
通过结构化 JSON 输入输出串联完成完整的章节生成流程。

Agent 执行流水线:
    1. ConstraintAgent  - 约束生成
    2. DirectorAgent    - 导演稿生成
    3. WriterAgent      - 正文写作
    4. ReviewAgent      - 质量检查
    5. StateExtractorAgent - 状态提取
    6. StateMerger      - 状态合并

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

__all__ = [
    "BaseAgent",
    "ContextBuilder",
    "ConstraintAgent",
    "DirectorAgent",
    "WriterAgent",
    "ReviewAgent",
    "StateExtractorAgent",
    "StateMerger",
]
