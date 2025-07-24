"""OGC MCP服务器启动脚本

用于启动独立的OGC MCP服务器进程，使用HTTP Streamable传输协议
"""

import logging
import sys
import signal
import asyncio
import uvicorn
import threading
import time
import os
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from ogc_mcp_server.server import mcp

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('ogc_mcp_server.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# 全局变量用于优雅关闭
shutdown_in_progress = False

def force_exit():
    """强制退出函数"""
    time.sleep(2.0)  # 等待2秒让优雅关闭完成
    logger.warning("强制退出程序")
    
    # 尝试清理所有活跃线程
    try:
        for thread in threading.enumerate():
            if thread != threading.current_thread() and thread.is_alive():
                logger.debug(f"发现活跃线程: {thread.name}")
    except Exception as e:
        logger.debug(f"清理线程时出错: {e}")
    
    # 强制退出
    os._exit(0)

def signal_handler(signum, frame):
    """信号处理器"""
    global shutdown_in_progress
    
    if shutdown_in_progress:
        logger.warning("重复接收到退出信号，强制退出...")
        os._exit(1)
        return
    
    shutdown_in_progress = True
    signal_name = "SIGINT" if signum == signal.SIGINT else f"信号{signum}"
    logger.info(f"收到{signal_name}，正在优雅关闭服务器...")
    
    # 启动强制退出定时器
    force_exit_timer = threading.Timer(2.0, force_exit)
    force_exit_timer.daemon = True
    force_exit_timer.start()

if __name__ == "__main__":
    logger.info("正在启动OGC MCP服务器...")
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 配置CORS中间件
        cors_middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],  # 允许所有来源，生产环境中应该限制为特定域名
                allow_credentials=True,
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["*"],
            ),
        ]
        
        # 创建ASGI应用，添加CORS中间件
        http_app = mcp.http_app(middleware=cors_middleware)
        
        # 服务器配置
        port = 8000
        host = "127.0.0.1"
        
        logger.info(f"服务器将在 http://{host}:{port}/mcp 启动")
        logger.info("传输协议: HTTP Streamable with CORS support")
        logger.info("CORS配置: 允许所有来源访问")
        
        # 使用uvicorn启动服务器
        uvicorn.run(
            http_app,
            host=host,
            port=port,
            log_level="info"
        )
        
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭服务器...")
    except Exception as e:
        logger.error(f"启动OGC MCP服务器时出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        logger.info("服务器已关闭")
        sys.exit(0)