"""地理数据可视化工作流提示词模块

基于FastMCP最佳实践的简洁高效地理数据可视化工作流
"""

import logging
from fastmcp import FastMCP
from fastmcp.prompts.prompt import PromptMessage, TextContent
from pydantic import Field
from typing_extensions import Annotated

logger = logging.getLogger(__name__)

# 创建工作流提示词子服务器
workflow_prompts_server = FastMCP(name="地理数据可视化工作流")


@workflow_prompts_server.prompt(
    name="geo_workflow",
    description="地理数据可视化工作流",
    tags={"workflow", "visualization"}
)
def geo_workflow(
    user_request: Annotated[str, Field(description="用户需求描述")]
) -> PromptMessage:
    """地理数据可视化工作流
    
    标准化的地理数据可视化执行流程
    """
    
    instruction_text = f"""{user_request}

🎯 执行流程：
1. clear_visualization_layers() - 清理现有图层
2. search_and_list_geographic_data() - 搜索相关数据，每次任务必须执行
3. add_wms_layer() - 添加底图
4. add_wfs_layer() - 添加WFS图层
5. create_composite_visualization() - 创建可视化，在图层添加完才能执行

⚡ 立即执行！"""

    return PromptMessage(
        role="user", 
        content=TextContent(type="text", text=instruction_text)
    )


@workflow_prompts_server.prompt(
    name="wfs_filter_detector",
    description="WFS过滤需求检测器",
    tags={"wfs", "filter", "detection"}
)
def wfs_filter_detector(
    user_query: Annotated[str, Field(description="用户查询内容")]
) -> PromptMessage:
    """WFS过滤需求检测器
    
    智能识别用户查询中是否需要过滤条件
    """
    
    instruction_text = f"""用户查询：{user_query}

🔍 过滤需求判断：
分析用户查询，判断是否包含具体的过滤条件：

**需要过滤的情况：**
- 包含具体地名、区域名称
- 包含分类、类型限定词
- 包含数值范围、大小条件
- 包含时间范围限定

**不需要过滤的情况：**
- 概览性需求（"所有"、"全部"、"整体"）

🎯 输出格式：
需要过滤：是/否
过滤类型：[地名/分类/数值/时间/无]
关键词：[提取的过滤关键词]

⚡ 快速判断！"""

    return PromptMessage(
        role="user", 
        content=TextContent(type="text", text=instruction_text)
    )