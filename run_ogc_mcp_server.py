"""OGC MCP服务器启动脚本

用于启动独立的OGC MCP服务器进程，使用HTTP Streamable传输协议
"""

import logging
import sys
import os
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

def main():
    """主函数"""
    logger.info("正在启动OGC MCP服务器...")
    
    # 配置CORS中间件
    cors_middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        ),
    ]
    
    # 创建ASGI应用，添加CORS中间件
    http_app = mcp.http_app(middleware=cors_middleware)
    
    # 服务器配置
    port = 3030
    host = "127.0.0.1"
    
    logger.info(f"服务器将在 http://{host}:{port}/mcp 启动")
    logger.info("传输协议: HTTP Streamable with CORS support")
    logger.info("CORS配置: 允许所有来源访问")
    
    try:
        # 使用uvicorn启动服务器，让uvicorn处理所有信号和退出逻辑
        uvicorn.run(
            http_app,
            host=host,
            port=port,
            log_level="info"
        )
    finally:
        # 确保程序完全退出
        logger.info("服务器已关闭")
        os._exit(0)  # 强制退出，确保所有线程都被终止

if __name__ == "__main__":
    main()