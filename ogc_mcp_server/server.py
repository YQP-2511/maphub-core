"""OGC MCP服务模块

基于FastMCP框架提供OGC服务资源访问的MCP服务器，
支持WMS和WFS图层的动态注册、资源管理和空间数据访问功能

采用模块化设计，使用FastMCP的服务器组合功能将不同功能分离到子服务器中
"""

import logging
from contextlib import asynccontextmanager
from fastmcp import FastMCP

from .database import init_database, close_database
from .utils.ogc_parser import get_ogc_parser

# 导入子服务器模块
from .tools.management_tools import management_server
from .tools.wms_tools import wms_server  
from .tools.wfs_tools import wfs_server
from .tools.web_tools import web_server
from .resources.layer_resources import layer_resource_server

# 配置日志
logger = logging.getLogger(__name__)

# 全局标志，防止重复导入
_servers_imported = False


@asynccontextmanager
async def lifespan(app):
    """服务器生命周期管理"""
    global _servers_imported
    
    # 启动时的初始化操作
    logger.info("正在初始化OGC MCP服务器...")
    
    # 初始化数据库
    await init_database()
    logger.info("数据库初始化完成")
    
    # 只在第一次启动时导入子服务器
    if not _servers_imported:
        logger.info("正在组合子服务器...")
        
        try:
            # 导入各个子服务器的组件（异步操作）
            await app.import_server(management_server, prefix="mgmt")  # 管理工具
            await app.import_server(wms_server, prefix="wms")          # WMS工具
            await app.import_server(wfs_server, prefix="wfs")          # WFS工具
            await app.import_server(web_server, prefix="web")          # Web服务工具
            await app.import_server(layer_resource_server)             # 图层资源（无前缀）
            
            _servers_imported = True
            
            logger.info("OGC MCP服务器组合完成")
            logger.info("已导入的服务模块:")
            logger.info("- 管理工具 (mgmt_*)")
            logger.info("- WMS工具 (wms_*)")
            logger.info("- WFS工具 (wfs_*)")
            logger.info("- Web服务工具 (web_*)")
            logger.info("- 图层资源")
            
        except Exception as e:
            logger.error(f"导入子服务器失败: {e}")
            # 即使导入失败，也标记为已尝试，避免重复尝试
            _servers_imported = True
            raise
    else:
        logger.info("子服务器已导入，跳过重复导入")
    
    logger.info("OGC MCP服务器启动完成")
    
    yield
    
    # 关闭时的清理操作
    logger.info("正在关闭OGC MCP服务器...")
    
    # 关闭数据库连接
    await close_database()
    logger.info("数据库连接已关闭")
    
    # 关闭OGC解析器
    parser = await get_ogc_parser()
    await parser.close()
    logger.info("OGC解析器已关闭")
    
    logger.info("OGC MCP服务器已关闭")


def create_ogc_mcp_server() -> FastMCP:
    """创建OGC MCP服务器
    
    使用FastMCP的服务器组合功能，将各个子服务器组合成一个完整的服务。
    子服务器的组合在 lifespan 函数中异步进行。
    
    Returns:
        FastMCP服务器实例
    """
    # 创建主服务器实例，子服务器组合将在启动时进行
    main_server = FastMCP(name="OGC服务", lifespan=lifespan)
    
    logger.info("OGC MCP服务器实例创建完成")
    logger.info("子服务器将在启动时进行组合")
    
    return main_server


# 创建OGC MCP服务器实例
mcp = create_ogc_mcp_server()


def get_ogc_mcp_server() -> FastMCP:
    """获取OGC MCP服务器实例
    
    用于依赖注入，提供OGC MCP服务器实例
    
    Returns:
        FastMCP: OGC MCP服务器实例
    """
    return mcp