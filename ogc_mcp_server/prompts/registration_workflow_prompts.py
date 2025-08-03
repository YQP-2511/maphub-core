"""OGC服务注册工作流提示词模块

简洁高效的OGC服务注册功能
基于FastMCP最佳实践设计
"""

import logging
from fastmcp import FastMCP
from fastmcp.prompts.prompt import PromptMessage, TextContent
from pydantic import Field
from typing_extensions import Annotated

logger = logging.getLogger(__name__)

# 创建注册工作流提示词服务器
registration_workflow_server = FastMCP(name="OGC服务注册工作流")


@registration_workflow_server.prompt(
    name="ogc_service_registration",
    description="OGC服务快速注册",
    tags={"registration", "ogc", "simple"}
)
def ogc_service_registration(
    service_urls: Annotated[str, Field(description="OGC服务URL列表，多个URL用逗号分隔")]
) -> PromptMessage:
    """OGC服务快速注册工作流
    
    用户提供URL，快速注册并列出结果
    """
    
    instruction_text = f"""OGC服务快速注册

服务URL：{service_urls}

执行步骤：

1. **解析URL**：
   - 将逗号分隔的URL转换为列表
   - 验证URL格式

2. **执行注册**：
   使用 register_ogc_services() 工具注册服务

3. **输出结果**：
   简洁列出：
   - 成功注册的服务数量
   - 每个服务的图层数量
   - 失败的URL（如果有）

注册原则：
- 快速高效，直接注册
- 简洁输出，只显示关键信息
- 注册完成即结束，不进行其他操作

开始注册服务。"""

    return PromptMessage(
        role="user",
        content=TextContent(type="text", text=instruction_text)
    )