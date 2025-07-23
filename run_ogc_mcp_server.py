"""OGC MCP服务器启动脚本

用于启动独立的OGC MCP服务器进程，使用HTTP Streamable传输协议
"""

import logging
import sys
import signal
import asyncio
import uvicorn
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
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    """信号处理器"""
    logger.info(f"收到信号 {signum}，正在关闭服务器...")
    shutdown_event.set()

if __name__ == "__main__":
    logger.info("正在启动OGC MCP服务器...")
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
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