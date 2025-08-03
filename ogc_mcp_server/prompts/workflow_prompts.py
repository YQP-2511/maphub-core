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
    name="simple_geo_workflow",
    description="简洁地理数据可视化工作流 - 专注WFS数据展示",
    tags={"workflow", "simple", "wfs", "visualization"}
)
def simple_geo_workflow(
    user_request: Annotated[str, Field(description="用户需求描述")]
) -> PromptMessage:
    """简洁地理数据可视化工作流 - 专注于WFS数据的高效展示"""
    
    instruction_text = f"""简洁地理数据可视化工作流

用户需求：{user_request}

🎯 目标：快速创建地理数据可视化

📋 执行步骤：

1. **清理环境**
   clear_visualization_layers()

2. **搜索数据**
   search_and_list_geographic_data()
   - 找到与"{user_request}"相关的WFS图层

3. **添加WFS数据**
   add_wfs_layer()
   - 选择最相关的WFS图层
   - 如果需求包含过滤条件，设置attribute_filter和filter_values
   - 示例：
     * "加州的县" → attribute_filter="STATE_NAME", filter_values="California"
     * "人口>100万" → attribute_filter="POPULATION", filter_values=">1000000"

4. **创建可视化**
   create_composite_visualization()
   - 生成可访问的地图链接

5. **输出结果**
   - 显示添加的图层信息
   - 提供可视化访问链接
   - 说明应用的过滤条件（如有）

🚨 重要提醒：
- 专注于WFS数据图层
- 避免添加过多复杂图层
- 确保过滤条件准确有效
- 最终必须生成可用的可视化链接

立即开始执行！"""

    return PromptMessage(
        role="user", 
        content=TextContent(type="text", text=instruction_text)
    )