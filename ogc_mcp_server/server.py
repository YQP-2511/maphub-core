"""OGC MCP服务模块

基于FastMCP框架提供OGC服务资源访问的MCP服务器，
支持WMS和WFS图层的动态注册、资源管理和空间数据访问功能

采用模块化设计，使用FastMCP的服务器组合功能将不同功能分离到子服务器中
"""

import logging
import signal
import sys
import asyncio
from contextlib import asynccontextmanager
from fastmcp import FastMCP

from .database import init_database, close_database
from .utils.ogc_parser import get_ogc_parser
from .services.web_server.server import get_web_server, stop_web_server

# 导入子服务器模块
from .tools.management_tools import management_server
from .tools.wms_tools import wms_server  
from .tools.wfs_tools import wfs_server
from .resources.layer_resources import layer_resource_server

# 配置日志
logger = logging.getLogger(__name__)

# 全局标志，防止重复导入
_servers_imported = False
_shutdown_in_progress = False


def setup_signal_handlers():
    """设置信号处理器，确保优雅退出"""
    def signal_handler(signum, frame):
        """信号处理函数"""
        global _shutdown_in_progress
        
        if _shutdown_in_progress:
            logger.warning("强制退出信号已接收，正在退出...")
            sys.exit(1)
        
        _shutdown_in_progress = True
        signal_name = "SIGINT" if signum == signal.SIGINT else f"信号{signum}"
        logger.info(f"接收到{signal_name}信号，正在优雅关闭服务器...")
        
        # 创建异步任务来处理关闭
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，创建任务
                loop.create_task(graceful_shutdown())
            else:
                # 如果事件循环未运行，直接运行
                asyncio.run(graceful_shutdown())
        except Exception as e:
            logger.error(f"优雅关闭失败: {e}")
            sys.exit(1)
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)  # 终止信号


async def graceful_shutdown():
    """优雅关闭所有服务"""
    logger.info("开始优雅关闭流程...")
    
    try:
        # 停止Web可视化服务器
        logger.info("正在停止Web可视化服务器...")
        await stop_web_server()
        logger.info("Web可视化服务器已停止")
        
        # 关闭数据库连接
        logger.info("正在关闭数据库连接...")
        await close_database()
        logger.info("数据库连接已关闭")
        
        # 关闭OGC解析器
        logger.info("正在关闭OGC解析器...")
        parser = await get_ogc_parser()
        await parser.close()
        logger.info("OGC解析器已关闭")
        
        logger.info("所有服务已优雅关闭")
        
    except Exception as e:
        logger.error(f"优雅关闭过程中出现错误: {e}")
    finally:
        # 确保退出
        logger.info("退出程序")
        sys.exit(0)


@asynccontextmanager
async def lifespan(app):
    """服务器生命周期管理"""
    global _servers_imported
    
    # 设置信号处理器
    setup_signal_handlers()
    
    # 启动时的初始化操作
    logger.info("正在初始化OGC MCP服务器...")
    
    try:
        # 初始化数据库
        await init_database()
        logger.info("数据库初始化完成")
        
        # 启动统一Web可视化服务器
        try:
            web_server = await get_web_server(port=8080)
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
                await app.import_server(layer_resource_server)                  # 图层资源（无前缀）
                
                _servers_imported = True
                
                logger.info("OGC MCP服务器组合完成")
                logger.info("已导入的服务模块:")
                logger.info("- 管理工具 (mgmt_*)")
                logger.info("- WMS工具 (wms_*)")
                logger.info("- WFS工具 (wfs_*)")
                logger.info("- 图层资源")
                
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
        if not _shutdown_in_progress:
            logger.info("正在关闭OGC MCP服务器...")
            await graceful_shutdown()


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