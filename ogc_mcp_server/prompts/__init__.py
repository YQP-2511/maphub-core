"""提示词模块

提供FastMCP提示词模板，引导AI使用现有工具进行复杂的地理数据分析和可视化
"""

from .workflow_prompts import workflow_prompts_server

__all__ = ["workflow_prompts_server"]