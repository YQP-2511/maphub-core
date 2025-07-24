"""Web可视化服务器核心模块

提供统一的Web服务器，用于展示MCP工具的可视化结果
"""

import asyncio
import logging
import threading
import json
import shutil
import atexit
from typing import Dict, Any, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import tempfile
import os

from .handlers import MapHandler, GeoJSONHandler, LayerHandler
from .templates import WebTemplates

logger = logging.getLogger(__name__)


class WebVisualizationServer:
    """统一Web可视化服务器
    
    提供OGC MCP工具结果的Web可视化服务，支持：
    - WMS地图可视化
    - WFS GeoJSON可视化
    - 图层管理界面
    - 结果展示和交互
    """
    
    def __init__(self, port: int = 8080, host: str = "localhost"):
        """初始化Web服务器
        
        Args:
            port: 服务端口
            host: 服务主机
        """
        self.port = port
        self.host = host
        self.server = None
        self.server_thread = None
        self.is_running = False
        self.web_dir = None
        self._shutdown_event = threading.Event()
        
        # 初始化处理器
        self.map_handler = MapHandler()
        self.geojson_handler = GeoJSONHandler()
        self.layer_handler = LayerHandler()
        self.templates = WebTemplates()
        
        # 存储可视化结果
        self.visualizations = {}
        
        # 注册退出时的清理函数
        atexit.register(self._cleanup_on_exit)
        
    async def start(self) -> Dict[str, Any]:
        """启动Web服务器
        
        Returns:
            服务器信息字典
        """
        if self.is_running:
            return self._get_server_info()
        
        try:
            # 创建临时Web目录
            self.web_dir = tempfile.mkdtemp(prefix="ogc_web_server_")
            logger.info(f"创建Web目录: {self.web_dir}")
            
            # 创建静态资源
            await self._setup_static_resources()
            
            # 启动HTTP服务器
            self._start_http_server()
            
            self.is_running = True
            
            server_info = self._get_server_info()
            logger.info(f"Web可视化服务器启动成功: {server_info['base_url']}")
            
            return server_info
            
        except Exception as e:
            logger.error(f"启动Web服务器失败: {e}")
            await self._cleanup_resources()
            raise
    
    def stop(self):
        """停止Web服务器"""
        if not self.is_running:
            return
        
        logger.info("正在停止Web可视化服务器...")
        
        try:
            # 设置关闭事件
            self._shutdown_event.set()
            
            # 关闭HTTP服务器
            if self.server:
                logger.info("正在关闭HTTP服务器...")
                self.server.shutdown()
                self.server.server_close()
                logger.info("HTTP服务器已关闭")
            
            # 等待服务器线程结束
            if self.server_thread and self.server_thread.is_alive():
                logger.info("等待服务器线程结束...")
                self.server_thread.join(timeout=10)  # 增加超时时间
                if self.server_thread.is_alive():
                    logger.warning("服务器线程未能在超时时间内结束")
                else:
                    logger.info("服务器线程已结束")
            
            self.is_running = False
            
            # 清理资源
            asyncio.create_task(self._cleanup_resources())
            
            logger.info("Web可视化服务器已停止")
            
        except Exception as e:
            logger.error(f"停止Web服务器失败: {e}")
    
    async def _cleanup_resources(self):
        """清理资源"""
        try:
            # 清理临时Web目录
            if self.web_dir and os.path.exists(self.web_dir):
                logger.info(f"清理Web目录: {self.web_dir}")
                shutil.rmtree(self.web_dir, ignore_errors=True)
                self.web_dir = None
            
            # 清理可视化数据
            self.visualizations.clear()
            
        except Exception as e:
            logger.error(f"清理资源失败: {e}")
    
    def _cleanup_on_exit(self):
        """程序退出时的清理函数"""
        if self.is_running:
            logger.info("程序退出，清理Web服务器资源...")
            self.stop()
    
    async def add_wms_visualization(self, layer_name: str, layer_info: Dict[str, Any], 
                                   map_config: Dict[str, Any]) -> str:
        """添加WMS地图可视化
        
        Args:
            layer_name: 图层名称
            layer_info: 图层信息
            map_config: 地图配置
            
        Returns:
            可视化页面URL
        """
        viz_id = f"wms_{layer_name.replace(':', '_').replace('/', '_')}"
        
        # 生成WMS地图HTML
        html_content = await self.map_handler.generate_wms_map(
            layer_name, layer_info, map_config
        )
        
        # 保存到Web目录
        html_path = os.path.join(self.web_dir, f"{viz_id}.html")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # 存储可视化信息
        self.visualizations[viz_id] = {
            "type": "wms",
            "layer_name": layer_name,
            "layer_info": layer_info,
            "map_config": map_config,
            "html_file": html_path,
            "url": f"{self._get_base_url()}/{viz_id}.html",
            "created_at": asyncio.get_event_loop().time()
        }
        
        # 更新首页
        await self._update_index_page()
        
        return self.visualizations[viz_id]["url"]
    
    async def add_geojson_visualization(self, layer_name: str, layer_info: Dict[str, Any],
                                      geojson_data: Dict[str, Any], stats: Dict[str, Any],
                                      map_config: Dict[str, Any]) -> str:
        """添加GeoJSON可视化
        
        Args:
            layer_name: 图层名称
            layer_info: 图层信息
            geojson_data: GeoJSON数据
            stats: 统计信息
            map_config: 地图配置
            
        Returns:
            可视化页面URL
        """
        viz_id = f"geojson_{layer_name.replace(':', '_').replace('/', '_')}"
        
        # 生成GeoJSON地图HTML
        html_content = await self.geojson_handler.generate_geojson_map(
            layer_name, layer_info, geojson_data, stats, map_config
        )
        
        # 保存到Web目录
        html_path = os.path.join(self.web_dir, f"{viz_id}.html")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # 存储可视化信息
        self.visualizations[viz_id] = {
            "type": "geojson",
            "layer_name": layer_name,
            "layer_info": layer_info,
            "geojson_stats": stats,
            "map_config": map_config,
            "html_file": html_path,
            "url": f"{self._get_base_url()}/{viz_id}.html",
            "created_at": asyncio.get_event_loop().time()
        }
        
        # 更新首页
        await self._update_index_page()
        
        return self.visualizations[viz_id]["url"]
    
    def get_visualization_url(self, viz_id: str) -> Optional[str]:
        """获取可视化URL
        
        Args:
            viz_id: 可视化ID
            
        Returns:
            可视化URL，如果不存在则返回None
        """
        if viz_id in self.visualizations:
            return self.visualizations[viz_id]["url"]
        return None
    
    def list_visualizations(self) -> Dict[str, Any]:
        """列出所有可视化
        
        Returns:
            可视化列表字典
        """
        return {
            "total": len(self.visualizations),
            "visualizations": list(self.visualizations.values()),
            "base_url": self._get_base_url()
        }
    
    def _start_http_server(self):
        """启动HTTP服务器"""
        class RequestHandler(BaseHTTPRequestHandler):
            def __init__(self, *args, web_server=None, **kwargs):
                self.web_server = web_server
                super().__init__(*args, **kwargs)
            
            def do_GET(self):
                self._handle_request()
            
            def do_POST(self):
                self._handle_request()
            
            def _handle_request(self):
                # 检查是否需要关闭
                if self.web_server._shutdown_event.is_set():
                    return
                
                try:
                    parsed_url = urlparse(self.path)
                    path = parsed_url.path.lstrip('/')
                    
                    if not path or path == 'index.html':
                        # 首页
                        self._serve_index()
                    elif path.endswith('.html'):
                        # HTML文件
                        self._serve_html_file(path)
                    elif path == 'api/visualizations':
                        # API接口
                        self._serve_api()
                    else:
                        # 静态资源
                        self._serve_static_file(path)
                        
                except Exception as e:
                    logger.error(f"处理请求失败: {e}")
                    self._send_error(500, str(e))
            
            def _serve_index(self):
                """提供首页"""
                try:
                    index_path = os.path.join(self.web_server.web_dir, 'index.html')
                    if os.path.exists(index_path):
                        with open(index_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        self._send_response(200, content, 'text/html')
                    else:
                        self._send_error(404, "首页未找到")
                except Exception as e:
                    self._send_error(500, str(e))
            
            def _serve_html_file(self, filename):
                """提供HTML文件"""
                try:
                    file_path = os.path.join(self.web_server.web_dir, filename)
                    if os.path.exists(file_path):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        self._send_response(200, content, 'text/html')
                    else:
                        self._send_error(404, f"文件未找到: {filename}")
                except Exception as e:
                    self._send_error(500, str(e))
            
            def _serve_api(self):
                """提供API接口"""
                try:
                    data = self.web_server.list_visualizations()
                    content = json.dumps(data, ensure_ascii=False, indent=2)
                    self._send_response(200, content, 'application/json')
                except Exception as e:
                    self._send_error(500, str(e))
            
            def _serve_static_file(self, filename):
                """提供静态文件"""
                self._send_error(404, f"静态文件未找到: {filename}")
            
            def _send_response(self, status_code, content, content_type):
                """发送响应"""
                try:
                    self.send_response(status_code)
                    self.send_header('Content-Type', f'{content_type}; charset=utf-8')
                    self.send_header('Content-Length', str(len(content.encode('utf-8'))))
                    self.end_headers()
                    self.wfile.write(content.encode('utf-8'))
                except Exception as e:
                    logger.error(f"发送响应失败: {e}")
            
            def _send_error(self, status_code, message):
                """发送错误响应"""
                try:
                    content = f"<html><body><h1>错误 {status_code}</h1><p>{message}</p></body></html>"
                    self._send_response(status_code, content, 'text/html')
                except Exception as e:
                    logger.error(f"发送错误响应失败: {e}")
            
            def log_message(self, format, *args):
                # 简化日志输出，避免过多日志
                pass
        
        # 创建服务器
        def handler_factory(*args, **kwargs):
            return RequestHandler(*args, web_server=self, **kwargs)
        
        try:
            self.server = HTTPServer((self.host, self.port), handler_factory)
            self.server.timeout = 1  # 设置超时，便于响应关闭信号
            
            # 在后台线程启动服务器
            def run_server():
                try:
                    logger.info(f"HTTP服务器线程启动，监听 {self.host}:{self.port}")
                    while not self._shutdown_event.is_set():
                        self.server.handle_request()
                except Exception as e:
                    if not self._shutdown_event.is_set():
                        logger.error(f"HTTP服务器运行错误: {e}")
                finally:
                    logger.info("HTTP服务器线程结束")
            
            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()
            
        except Exception as e:
            logger.error(f"启动HTTP服务器失败: {e}")
            raise
    
    async def _setup_static_resources(self):
        """设置静态资源"""
        # 创建初始首页
        await self._update_index_page()
    
    async def _update_index_page(self):
        """更新首页"""
        try:
            index_content = self.templates.generate_index_page(
                self.visualizations, self._get_server_info()
            )
            
            index_path = os.path.join(self.web_dir, 'index.html')
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(index_content)
        except Exception as e:
            logger.error(f"更新首页失败: {e}")
    
    def _get_base_url(self) -> str:
        """获取基础URL"""
        return f"http://{self.host}:{self.port}"
    
    def _get_server_info(self) -> Dict[str, Any]:
        """获取服务器信息"""
        return {
            "status": "running" if self.is_running else "stopped",
            "host": self.host,
            "port": self.port,
            "base_url": self._get_base_url(),
            "web_directory": self.web_dir,
            "total_visualizations": len(self.visualizations)
        }


# 全局Web服务器实例
_web_server_instance = None


async def get_web_server(port: int = 8080, host: str = "localhost") -> WebVisualizationServer:
    """获取Web服务器实例（单例模式）
    
    Args:
        port: 服务端口
        host: 服务主机
        
    Returns:
        Web服务器实例
    """
    global _web_server_instance
    
    if _web_server_instance is None:
        _web_server_instance = WebVisualizationServer(port, host)
        await _web_server_instance.start()
    
    return _web_server_instance


async def stop_web_server():
    """停止Web服务器"""
    global _web_server_instance
    
    if _web_server_instance:
        _web_server_instance.stop()
        # 等待一小段时间确保清理完成
        await asyncio.sleep(0.5)
        _web_server_instance = None
        logger.info("Web服务器实例已清理")