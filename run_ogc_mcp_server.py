"""GeoServer MCP服务器启动脚本

用于启动独立的GeoServer MCP服务器进程
"""

import logging
import sys
from ogc_mcp_server.server import ogc_mcp_server

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('geoserver_mcp_server.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("正在启动OGC MCP服务器...")
    try:
        # 使用streamable-http传输协议启动服务器
        ogc_mcp_server.run(transport="streamable-http")
    except Exception as e:
        logger.error(f"启动OGC MCP服务器时出错: {e}")
        sys.exit(1)