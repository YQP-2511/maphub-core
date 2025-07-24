"""Web可视化服务器核心模块

提供统一的Web服务器，用于展示MCP工具的可视化结果
"""

import asyncio
import logging
import threading
import json
import shutil
import atexit
from typing import Dict, Any, Optional, List
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import tempfile
import os

from .handlers import MapHandler, GeoJSONHandler, LayerHandler, CompositeHandler
from .templates import WebTemplates

logger = logging.getLogger(__name__)


class WebVisualizationServer:
    """统一Web可视化服务器
    
    提供OGC MCP工具结果的Web可视化服务，支持：
    - WMS地图可视化
    - WFS GeoJSON可视化
    - 复合图层可视化
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
        self.composite_handler = CompositeHandler(self.templates)
        
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
            
            # 强制关闭HTTP服务器
            if self.server:
                logger.info("正在强制关闭HTTP服务器...")
                
                # 在单独线程中执行关闭操作，避免阻塞
                def force_shutdown():
                    try:
                        self.server.shutdown()
                        self.server.server_close()
                        logger.info("HTTP服务器已强制关闭")
                    except Exception as e:
                        logger.warning(f"强制关闭HTTP服务器时出现异常: {e}")
                
                # 启动关闭线程
                shutdown_thread = threading.Thread(target=force_shutdown, daemon=True)
                shutdown_thread.start()
                
                # 等待关闭完成，但不超过2秒
                shutdown_thread.join(timeout=2)
                if shutdown_thread.is_alive():
                    logger.warning("HTTP服务器关闭超时，继续执行")
            
            # 强制结束服务器线程
            if self.server_thread and self.server_thread.is_alive():
                logger.info("正在强制结束服务器线程...")
                # 减少等待时间到3秒
                self.server_thread.join(timeout=3)
                if self.server_thread.is_alive():
                    logger.warning("服务器线程强制结束超时")
                else:
                    logger.info("服务器线程已结束")
            
            self.is_running = False
            
            # 同步清理资源，避免异步任务
            self._cleanup_resources_sync()
            
            logger.info("Web可视化服务器已停止")
            
        except Exception as e:
            logger.error(f"停止Web服务器失败: {e}")
    
    def _cleanup_resources_sync(self):
        """同步清理资源"""
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
    
    async def _cleanup_resources(self):
        """异步清理资源（保留用于正常关闭）"""
        self._cleanup_resources_sync()
    
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
    
    async def add_composite_visualization(self, title: str, layers: List[Dict[str, Any]], 
                                        map_config: Dict[str, Any]) -> str:
        """添加复合图层可视化
        
        Args:
            title: 地图标题
            layers: 图层配置列表，每个图层包含type、layer_info等信息
            map_config: 地图配置
            
        Returns:
            可视化页面URL
        """
        # 生成可视化ID
        viz_id = f"composite_{title.replace(' ', '_').replace(':', '_').replace('/', '_')}"
        
        try:
            # 处理图层数据
            processed_layers = []
            for layer_config in layers:
                processed_layer = self.composite_handler.process_layer_data(layer_config)
                processed_layers.append(processed_layer)
            
            # 计算地图边界（如果没有提供中心点）
            if 'center' not in map_config:
                bounds = self.composite_handler.calculate_map_bounds(processed_layers)
                if bounds:
                    center_lat = (bounds['north'] + bounds['south']) / 2
                    center_lng = (bounds['east'] + bounds['west']) / 2
                    map_config['center'] = [center_lat, center_lng]
                else:
                    map_config['center'] = [39.9042, 116.4074]  # 默认北京
            
            # 生成复合地图HTML
            html_content = await self.composite_handler.generate_composite_map(
                title, processed_layers, map_config
            )
            
            # 保存到Web目录
            html_path = os.path.join(self.web_dir, f"{viz_id}.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # 存储可视化信息
            self.visualizations[viz_id] = {
                "type": "composite",
                "layer_name": title,
                "layer_info": {
                    "layer_title": title,
                    "service_name": "复合可视化",
                    "crs": "EPSG:4326"
                },
                "layers": processed_layers,
                "map_config": map_config,
                "html_file": html_path,
                "url": f"{self._get_base_url()}/{viz_id}.html",
                "created_at": asyncio.get_event_loop().time()
            }
            
            # 更新首页
            await self._update_index_page()
            
            logger.info(f"复合可视化创建成功: {title}, 包含 {len(processed_layers)} 个图层")
            
            return self.visualizations[viz_id]["url"]
            
        except Exception as e:
            logger.error(f"创建复合可视化失败: {e}")
            raise
    
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
    
    def get_visualization_by_id(self, viz_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取可视化信息
        
        Args:
            viz_id: 可视化ID
            
        Returns:
            可视化信息，如果不存在则返回None
        """
        return self.visualizations.get(viz_id)
    
    def remove_visualization(self, viz_id: str) -> bool:
        """删除可视化
        
        Args:
            viz_id: 可视化ID
            
        Returns:
            是否删除成功
        """
        if viz_id not in self.visualizations:
            return False
        
        try:
            # 删除HTML文件
            viz_info = self.visualizations[viz_id]
            html_file = viz_info.get("html_file")
            if html_file and os.path.exists(html_file):
                os.remove(html_file)
            
            # 从内存中删除
            del self.visualizations[viz_id]
            
            # 更新首页
            asyncio.create_task(self._update_index_page())
            
            logger.info(f"可视化已删除: {viz_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除可视化失败: {e}")
            return False
    
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
            
            def do_DELETE(self):
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
                    elif path.startswith('api/visualizations/'):
                        # 单个可视化API
                        viz_id = path.split('/')[-1]
                        self._serve_visualization_api(viz_id)
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
            
            def _serve_visualization_api(self, viz_id: str):
                """提供单个可视化API"""
                try:
                    if self.command == 'GET':
                        # 获取可视化信息
                        viz_info = self.web_server.get_visualization_by_id(viz_id)
                        if viz_info:
                            content = json.dumps(viz_info, ensure_ascii=False, indent=2)
                            self._send_response(200, content, 'application/json')
                        else:
                            self._send_error(404, f"可视化未找到: {viz_id}")
                    
                    elif self.command == 'DELETE':
                        # 删除可视化
                        success = self.web_server.remove_visualization(viz_id)
                        if success:
                            content = json.dumps({"message": "删除成功"}, ensure_ascii=False)
                            self._send_response(200, content, 'application/json')
                        else:
                            self._send_error(404, f"可视化未找到: {viz_id}")
                    
                    else:
                        self._send_error(405, "方法不允许")
                        
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
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
                    self.send_header('Access-Control-Allow-Headers', 'Content-Type')
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