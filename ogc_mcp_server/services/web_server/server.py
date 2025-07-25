"""Web可视化服务器核心模块

提供统一的Web服务器，用于展示MCP工具的可视化结果
"""

import asyncio
import logging
import threading
import json
import shutil
import atexit
import re
import hashlib
import time
from typing import Dict, Any, Optional, List
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote
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
    
    def _generate_safe_id(self, title: str, prefix: str = "", max_length: int = 50) -> str:
        """生成安全的URL ID
        
        Args:
            title: 原始标题
            prefix: ID前缀
            max_length: 最大长度
            
        Returns:
            安全的URL ID
        """
        # 移除或替换特殊字符
        safe_title = re.sub(r'[^\w\s-]', '', title)
        safe_title = re.sub(r'[-\s]+', '_', safe_title)
        
        # 如果包含中文或其他非ASCII字符，使用英文替换或哈希
        if not safe_title.isascii() or not safe_title:
            # 预定义的中文到英文映射
            chinese_to_english = {
                '分层地图': 'layered_map',
                '可视化': 'visualization',
                '底图': 'basemap',
                '数据图层': 'data_layer',
                '复合': 'composite',
                '地图': 'map',
                '图层': 'layer',
                'WMS': 'wms',
                'WFS': 'wfs',
                'GeoJSON': 'geojson'
            }
            
            # 尝试翻译常见中文词汇
            english_title = title
            for chinese, english in chinese_to_english.items():
                english_title = english_title.replace(chinese, english)
            
            # 再次清理
            safe_title = re.sub(r'[^\w\s-]', '', english_title)
            safe_title = re.sub(r'[-\s]+', '_', safe_title)
            
            # 如果仍然包含非ASCII字符，使用哈希
            if not safe_title.isascii() or not safe_title:
                # 使用标题的哈希值作为ID
                hash_value = hashlib.md5(title.encode('utf-8')).hexdigest()[:8]
                safe_title = f"viz_{hash_value}"
        
        # 限制长度
        if len(safe_title) > max_length:
            safe_title = safe_title[:max_length]
        
        # 添加前缀
        if prefix:
            safe_id = f"{prefix}_{safe_title}"
        else:
            safe_id = safe_title
        
        # 确保ID唯一性
        base_id = safe_id
        counter = 1
        while safe_id in self.visualizations:
            safe_id = f"{base_id}_{counter}"
            counter += 1
        
        return safe_id.lower()
        
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
        viz_id = self._generate_safe_id(layer_name, "wms")
        
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
        viz_id = self._generate_safe_id(layer_name, "geojson")
        
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
        # 使用新的安全ID生成函数
        viz_id = self._generate_safe_id(title, "composite")
        
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
                    if self.command == 'GET':
                        # 返回可视化列表
                        visualizations = self.web_server.list_visualizations()
                        self._send_json_response(200, visualizations)
                    else:
                        self._send_error(405, "方法不允许")
                except Exception as e:
                    self._send_error(500, str(e))
            
            def _serve_visualization_api(self, viz_id):
                """提供单个可视化API"""
                try:
                    if self.command == 'GET':
                        # 返回可视化信息
                        viz_info = self.web_server.get_visualization_by_id(viz_id)
                        if viz_info:
                            self._send_json_response(200, viz_info)
                        else:
                            self._send_error(404, f"可视化未找到: {viz_id}")
                    elif self.command == 'DELETE':
                        # 删除可视化
                        success = self.web_server.remove_visualization(viz_id)
                        if success:
                            self._send_json_response(200, {"message": "删除成功"})
                        else:
                            self._send_error(404, f"可视化未找到: {viz_id}")
                    else:
                        self._send_error(405, "方法不允许")
                except Exception as e:
                    self._send_error(500, str(e))
            
            def _serve_static_file(self, path):
                """提供静态文件"""
                try:
                    # 简单的静态文件服务
                    self._send_error(404, f"静态文件未找到: {path}")
                except Exception as e:
                    self._send_error(500, str(e))
            
            def _send_response(self, status_code, content, content_type='text/html'):
                """发送响应"""
                self.send_response(status_code)
                self.send_header('Content-Type', f'{content_type}; charset=utf-8')
                self.send_header('Content-Length', str(len(content.encode('utf-8'))))
                self.end_headers()
                self.wfile.write(content.encode('utf-8'))
            
            def _send_json_response(self, status_code, data):
                """发送JSON响应"""
                content = json.dumps(data, ensure_ascii=False, indent=2)
                self._send_response(status_code, content, 'application/json')
            
            def _send_error(self, status_code, message):
                """发送错误响应"""
                error_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>错误 {status_code}</title>
                    <meta charset="utf-8">
                </head>
                <body>
                    <h1>错误 {status_code}</h1>
                    <p>{message}</p>
                    <p><a href="/">返回首页</a></p>
                </body>
                </html>
                """
                self._send_response(status_code, error_content)
            
            def log_message(self, format, *args):
                """重写日志方法，避免过多输出"""
                pass
        
        # 创建HTTP服务器
        def create_handler(*args, **kwargs):
            return RequestHandler(*args, web_server=self, **kwargs)
        
        self.server = HTTPServer((self.host, self.port), create_handler)
        
        # 在单独线程中运行服务器
        def run_server():
            try:
                logger.info(f"HTTP服务器启动在 {self.host}:{self.port}")
                self.server.serve_forever()
            except Exception as e:
                if not self._shutdown_event.is_set():
                    logger.error(f"HTTP服务器运行失败: {e}")
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
    
    def _get_base_url(self) -> str:
        """获取基础URL"""
        return f"http://{self.host}:{self.port}"
    
    def _get_server_info(self) -> Dict[str, Any]:
        """获取服务器信息"""
        return {
            "host": self.host,
            "port": self.port,
            "base_url": self._get_base_url(),
            "status": "running" if self.is_running else "stopped",
            "web_dir": self.web_dir,
            "visualizations_count": len(self.visualizations)
        }
    
    async def _setup_static_resources(self):
        """设置静态资源"""
        # 创建初始首页
        await self._update_index_page()
    
    async def _update_index_page(self):
        """更新首页"""
        try:
            # 生成首页HTML
            html_content = self.templates.generate_index_page(
                self.visualizations, self._get_server_info()
            )
            
            # 保存首页
            index_path = os.path.join(self.web_dir, 'index.html')
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
                
        except Exception as e:
            logger.error(f"更新首页失败: {e}")


# 全局Web服务器实例
_web_server_instance = None
_web_server_lock = asyncio.Lock()


async def get_web_server() -> WebVisualizationServer:
    """获取Web服务器实例（单例模式）
    
    Returns:
        Web服务器实例
    """
    global _web_server_instance
    
    async with _web_server_lock:
        if _web_server_instance is None:
            _web_server_instance = WebVisualizationServer()
            await _web_server_instance.start()
        elif not _web_server_instance.is_running:
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