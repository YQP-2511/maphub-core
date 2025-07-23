"""GeoServer MCP服务模块

提供GeoServer资源访问的MCP服务，将工作空间-存储仓库-图层列表作为资源直接访问
"""

import logging
from mcp.server.fastmcp import FastMCP

# 配置日志
logger = logging.getLogger(__name__)

# 创建OGC MCP服务器实例
ogc_mcp_server = FastMCP(
    "OGC服务",  # 服务器名称
    description="连接OGC服务的MCP服务，提供图层访问和空间分析功能",
    version="0.2.0",
    reload=True,
    stateless_http=False,  # 使用有状态服务器，保持会话状态
    port=8767   # 使用不同于其他MCP服务器的端口
)
def get_ogc_mcp_server() -> FastMCP:
    """获取OGC MCP服务器实例
    
    用于依赖注入，提供OGC MCP服务器实例
    
    Returns:
        FastMCP: OGC MCP服务器实例
    """
    return ogc_mcp_server
