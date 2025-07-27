"""
OGC MCP服务器主模块

使用FastMCP框架构建的OGC服务MCP服务器，提供WMS/WFS服务的管理和访问功能。
支持服务器组合模式，将多个子服务器组合成一个完整的服务。
"""

import logging
from contextlib import asynccontextmanager
from fastmcp import FastMCP

from .database import init_database, close_database
from .services.web_server.server import get_web_server, stop_web_server

# 导入子服务器模块
from .tools.management_tools import management_server
from .tools.wms_tools import wms_server  
from .tools.wfs_tools import wfs_server
from .tools.visualization_tools import visualization_server
from .resources.layer_registry import layer_registry_server
from .prompts.workflow_prompts import workflow_prompts_server

# 配置日志
logger = logging.getLogger(__name__)

# 全局标志，防止重复导入和重复清理
_servers_imported = False
_cleanup_done = False


async def cleanup_resources():
    """清理资源"""
    global _cleanup_done
    
    if _cleanup_done:
        logger.info("资源已清理，跳过重复清理")
        return
    
    logger.info("正在清理资源...")
    
    try:
        # 停止Web可视化服务器
        logger.info("正在停止Web可视化服务器...")
        await stop_web_server()
        
        # 关闭数据库连接
        logger.info("正在关闭数据库连接...")
        await close_database()
        logger.info("数据库连接已关闭")
        
        _cleanup_done = True
        logger.info("资源清理完成")
        
    except Exception as e:
        logger.error(f"资源清理过程中出现错误: {e}")


@asynccontextmanager
async def lifespan(app):
    """服务器生命周期管理"""
    global _servers_imported
    
    # 启动时的初始化操作
    logger.info("正在初始化OGC MCP服务器...")
    
    try:
        # 初始化数据库
        await init_database()
        logger.info("数据库初始化完成")
        
        # 启动统一Web可视化服务器
        try:
            web_server = await get_web_server()
            logger.info(f"统一Web可视化服务器启动成功: {web_server._get_base_url()}")
        except Exception as e:
            logger.error(f"启动Web可视化服务器失败: {e}")
            # 不阻止MCP服务器启动
        
        # 只在第一次启动时导入子服务器
        if not _servers_imported:
            logger.info("正在组合子服务器...")
            
            try:
                # 导入各个子服务器的组件（异步操作）
                await app.import_server(management_server, prefix="mgmt")        # 管理工具
                await app.import_server(wms_server, prefix="wms")               # WMS工具
                await app.import_server(wfs_server, prefix="wfs")               # WFS工具
                await app.import_server(visualization_server, prefix="viz")     # 通用可视化工具
                await app.import_server(workflow_prompts_server, prefix="workflow")  # 工作流提示词
                await app.import_server(layer_registry_server)                 # 图层注册表资源（无前缀）
                
                _servers_imported = True
                
                logger.info("OGC MCP服务器组合完成")
                logger.info("已导入的服务模块:")
                logger.info("- 管理工具 (mgmt_*)")
                logger.info("- WMS工具 (wms_*)")
                logger.info("- WFS工具 (wfs_*)")
                logger.info("- 通用可视化工具 (viz_*)")
                logger.info("- 工作流提示词 (workflow_*)")
                logger.info("- 图层注册表资源 (ogc://)")
                
            except Exception as e:
                logger.error(f"导入子服务器失败: {e}")
                # 即使导入失败，也标记为已尝试，避免重复尝试
                _servers_imported = True
                raise
        else:
            logger.info("子服务器已导入，跳过重复导入")
        
        logger.info("OGC MCP服务器启动完成")
        logger.info("使用 Ctrl+C 可以优雅关闭服务器")
        
        yield
        
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")
        raise
    finally:
        # 关闭时的清理操作
        logger.info("正在关闭OGC MCP服务器...")
        await cleanup_resources()


# 创建单一的OGC MCP服务器实例（遵循FastMCP最佳实践）
mcp = FastMCP(name="OGC服务", lifespan=lifespan)

logger.info("OGC MCP服务器实例创建完成")
logger.info("子服务器将在启动时进行组合")


def get_ogc_mcp_server() -> FastMCP:
    """获取OGC MCP服务器实例
    
    用于依赖注入，提供OGC MCP服务器实例
    
    Returns:
        FastMCP: OGC MCP服务器实例
    """
    return mcp