"""Web工具模块

提供Web服务相关的工具函数，包括交互式地图的Web服务启动
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from fastmcp import FastMCP, Context
from pydantic import Field
from typing_extensions import Annotated

from .wms_tools import get_interactive_map
from ..utils.geojson_utils import (
    fetch_geojson_data, analyze_geojson_data, parse_style_config,
    calculate_map_center, save_geojson_map_file
)
from ..utils.html_templates import generate_geojson_map_html
from ..database import get_layer_repository, LayerResourceQuery

logger = logging.getLogger(__name__)

# 创建Web工具子服务器
web_server = FastMCP(name="Web工具服务")


@web_server.tool
async def serve_interactive_map(
    layer_name: Annotated[str, Field(description="图层名称")],
    width: Annotated[int, Field(description="地图容器宽度", ge=300, le=2000)] = 1000,
    height: Annotated[int, Field(description="地图容器高度", ge=300, le=2000)] = 700,
    initial_zoom: Annotated[int, Field(description="初始缩放级别", ge=1, le=18)] = 10,
    port: Annotated[int, Field(description="Web服务端口", ge=8000, le=9999)] = 8080,
    ctx: Context = None
) -> Dict[str, Any]:
    """启动交互式地图Web服务
    
    生成交互式地图并启动本地Web服务器，提供浏览器访问。
    支持WMS和WFS图层的可视化展示。
    """
    if ctx:
        await ctx.info(f"正在启动交互式地图Web服务: {layer_name}")
    
    try:
        # 生成交互式地图
        map_result = await get_interactive_map(
            layer_name, width, height, initial_zoom, ctx
        )
        
        # 启动Web服务器
        web_info = _start_web_server(layer_name, map_result, port)
        
        result = {
            "service_info": {
                "status": "running",
                "service_type": "Interactive Map",
                "port": port,
                "web_directory": web_info["web_dir"],
                "base_url": web_info["base_url"],
                "map_url": web_info["map_url"],
                "index_url": web_info["index_url"]
            },
            "layer_info": map_result["layer_info"],
            "map_config": map_result["map_config"],
            "files": web_info["files"],
            "instructions": {
                "access": f"在浏览器中访问: {web_info['map_url']}",
                "index": f"服务首页: {web_info['base_url']}",
                "features": [
                    "交互式地图浏览",
                    "图层切换和控制",
                    "缩放和平移操作",
                    "坐标显示",
                    "比例尺显示"
                ],
                "note": "服务将在后台运行，可随时访问地图页面"
            }
        }
        
        if ctx:
            await ctx.info(f"交互式地图Web服务启动成功，访问地址: {web_info['map_url']}")
        
        logger.info(f"交互式地图Web服务启动成功，端口: {port}，地址: {web_info['map_url']}")
        return result
        
    except Exception as e:
        error_msg = f"启动交互式地图Web服务失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


@web_server.tool
async def serve_geojson_map(
    layer_name: Annotated[str, Field(description="WFS图层名称")],
    max_features: Annotated[int, Field(description="最大要素数量", ge=1, le=1000)] = 100,
    width: Annotated[int, Field(description="地图容器宽度", ge=300, le=2000)] = 1000,
    height: Annotated[int, Field(description="地图容器高度", ge=300, le=2000)] = 700,
    initial_zoom: Annotated[int, Field(description="初始缩放级别", ge=1, le=18)] = 10,
    style_config: Annotated[Optional[str], Field(description="样式配置JSON字符串")] = None,
    port: Annotated[int, Field(description="Web服务端口", ge=8000, le=9999)] = 8081,
    ctx: Context = None
) -> Dict[str, Any]:
    """启动WFS GeoJSON交互式地图Web服务
    
    获取WFS图层的GeoJSON数据，生成交互式地图并启动本地Web服务器。
    支持要素属性查看、样式自定义等功能。
    """
    if ctx:
        await ctx.info(f"正在启动WFS GeoJSON地图Web服务: {layer_name}")
    
    try:
        # 直接调用内部函数生成GeoJSON地图
        map_result = await _create_geojson_map_internal(
            layer_name, max_features, width, height, initial_zoom, style_config, None, ctx
        )
        
        # 启动Web服务器
        web_info = _start_geojson_web_server(layer_name, map_result, port)
        
        result = {
            "service_info": {
                "status": "running",
                "service_type": "WFS GeoJSON",
                "port": port,
                "web_directory": web_info["web_dir"],
                "base_url": web_info["base_url"],
                "map_url": web_info["map_url"],
                "index_url": web_info["index_url"]
            },
            "layer_info": map_result["layer_info"],
            "geojson_statistics": map_result["geojson_statistics"],
            "map_config": map_result["map_config"],
            "files": web_info["files"],
            "instructions": {
                "access": f"在浏览器中访问: {web_info['map_url']}",
                "index": f"服务首页: {web_info['base_url']}",
                "features": [
                    "WFS GeoJSON要素可视化",
                    "要素属性弹窗查看",
                    "交互式地图操作",
                    "样式自定义和图层控制",
                    "坐标显示和测量工具"
                ],
                "note": "服务将在后台运行，可随时访问GeoJSON地图页面"
            }
        }
        
        if ctx:
            await ctx.info(f"WFS GeoJSON地图Web服务启动成功，访问地址: {web_info['map_url']}")
        
        logger.info(f"WFS GeoJSON地图Web服务启动成功，端口: {port}，地址: {web_info['map_url']}")
        return result
        
    except Exception as e:
        error_msg = f"启动WFS GeoJSON地图Web服务失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


# 内部辅助函数
async def _create_geojson_map_internal(
    layer_name: str, max_features: int, width: int, height: int, 
    initial_zoom: int, style_config: Optional[str], bbox: Optional[str], 
    ctx: Context = None
) -> Dict[str, Any]:
    """内部GeoJSON地图创建函数
    
    Args:
        layer_name: WFS图层名称
        max_features: 最大要素数量
        width: 地图容器宽度
        height: 地图容器高度
        initial_zoom: 初始缩放级别
        style_config: 样式配置JSON字符串
        bbox: 边界框过滤
        ctx: MCP上下文对象
        
    Returns:
        地图生成结果字典
    """
    try:
        # 获取图层信息
        repository = await get_layer_repository()
        query = LayerResourceQuery(layer_name=layer_name, service_type="WFS", limit=1)
        layers = await repository.list_resources(query)
        
        if not layers:
            raise ValueError(f"未找到WFS图层: {layer_name}")
        
        layer = layers[0]
        
        # 构建WFS GetFeature请求参数
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeName": layer.layer_name,
            "outputFormat": "application/json",
            "maxFeatures": max_features
        }
        
        if bbox:
            params["bbox"] = bbox
        
        # 获取GeoJSON数据
        geojson_data = await fetch_geojson_data(layer.service_url, params, ctx)
        stats = analyze_geojson_data(geojson_data)
        
        # 构建图层信息
        layer_info = {
            "resource_id": layer.resource_id,
            "service_name": layer.service_name,
            "service_url": layer.service_url,
            "layer_name": layer.layer_name,
            "layer_title": layer.layer_title,
            "crs": layer.crs
        }
        
        # 解析样式配置和计算地图中心点
        style_options = parse_style_config(style_config)
        center_lat, center_lng = calculate_map_center(geojson_data, layer_info)
        
        # 生成交互式地图HTML
        html_content = generate_geojson_map_html(
            layer_name, layer_info, geojson_data, stats, style_options,
            center_lat, center_lng, width, height, initial_zoom
        )
        
        # 保存HTML文件
        html_path = save_geojson_map_file(layer_name, html_content)
        
        result = {
            "layer_info": layer_info,
            "geojson_statistics": stats,
            "map_config": {
                "center": [center_lat, center_lng],
                "zoom": initial_zoom,
                "width": width,
                "height": height,
                "style": style_options
            },
            "html_file": html_path,
            "html_content": html_content,
            "file_size_kb": len(html_content) // 1024
        }
        
        if ctx:
            await ctx.info(f"GeoJSON交互式地图创建成功: {layer_name}，要素数量: {stats['feature_count']}")
        
        logger.info(f"GeoJSON交互式地图创建成功: {layer_name}，要素数量: {stats['feature_count']}")
        return result
        
    except Exception as e:
        error_msg = f"创建GeoJSON交互式地图失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


def _start_web_server(layer_name: str, map_result: Dict[str, Any], port: int) -> Dict[str, Any]:
    """启动Web服务器
    
    Args:
        layer_name: 图层名称
        map_result: 地图生成结果
        port: 端口号
        
    Returns:
        Web服务信息字典
    """
    import os
    import tempfile
    import threading
    import http.server
    import socketserver
    
    # 创建临时目录作为Web根目录
    web_dir = tempfile.mkdtemp(prefix="ogc_map_")
    
    # 将HTML内容保存到Web目录
    html_filename = f"map_{layer_name.replace(':', '_').replace('/', '_')}.html"
    html_path = os.path.join(web_dir, html_filename)
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(map_result["html_content"])
    
    # 创建索引页面
    index_content = _generate_index_page(layer_name, map_result, html_filename)
    index_path = os.path.join(web_dir, "index.html")
    
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(index_content)
    
    # 启动HTTP服务器
    class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=web_dir, **kwargs)
        
        def log_message(self, format, *args):
            # 简化日志输出
            pass
    
    def start_server():
        with socketserver.TCPServer(("", port), CustomHTTPRequestHandler) as httpd:
            httpd.serve_forever()
    
    # 在后台线程启动服务器
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # 构建访问URL
    base_url = f"http://localhost:{port}"
    map_url = f"{base_url}/{html_filename}"
    
    return {
        "web_dir": web_dir,
        "base_url": base_url,
        "map_url": map_url,
        "index_url": f"{base_url}/index.html",
        "files": {
            "map_html": html_path,
            "index_html": index_path
        }
    }


def _start_geojson_web_server(layer_name: str, map_result: Dict[str, Any], port: int) -> Dict[str, Any]:
    """启动GeoJSON地图Web服务器
    
    Args:
        layer_name: 图层名称
        map_result: 地图生成结果
        port: 端口号
        
    Returns:
        Web服务信息字典
    """
    import os
    import tempfile
    import threading
    import http.server
    import socketserver
    
    # 创建临时目录作为Web根目录
    web_dir = tempfile.mkdtemp(prefix="geojson_map_")
    
    # 将HTML内容保存到Web目录
    html_filename = f"geojson_{layer_name.replace(':', '_').replace('/', '_')}.html"
    html_path = os.path.join(web_dir, html_filename)
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(map_result["html_content"])
    
    # 创建GeoJSON专用索引页面
    index_content = _generate_geojson_index_page(layer_name, map_result, html_filename)
    index_path = os.path.join(web_dir, "index.html")
    
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(index_content)
    
    # 启动HTTP服务器
    class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=web_dir, **kwargs)
        
        def log_message(self, format, *args):
            # 简化日志输出
            pass
    
    def start_server():
        with socketserver.TCPServer(("", port), CustomHTTPRequestHandler) as httpd:
            httpd.serve_forever()
    
    # 在后台线程启动服务器
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # 构建访问URL
    base_url = f"http://localhost:{port}"
    map_url = f"{base_url}/{html_filename}"
    
    return {
        "web_dir": web_dir,
        "base_url": base_url,
        "map_url": map_url,
        "index_url": f"{base_url}/index.html",
        "files": {
            "map_html": html_path,
            "index_html": index_path
        }
    }


def _generate_index_page(layer_name: str, map_result: Dict[str, Any], html_filename: str) -> str:
    """生成索引页面HTML内容
    
    Args:
        layer_name: 图层名称
        map_result: 地图生成结果
        html_filename: HTML文件名
        
    Returns:
        索引页面HTML内容
    """
    layer_info = map_result.get("layer_info", {})
    map_config = map_result.get("map_config", {})
    
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OGC地图服务 - {layer_name}</title>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background-color: #f5f5f5; 
        }}
        .container {{ 
            max-width: 800px; 
            margin: 0 auto; 
            background: white; 
            padding: 30px; 
            border-radius: 8px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
        }}
        h1 {{ color: #333; margin-bottom: 20px; }}
        .info-grid {{ 
            display: grid; 
            grid-template-columns: 1fr 1fr; 
            gap: 15px; 
            margin: 20px 0; 
        }}
        .info-item {{ 
            background: #f8f9fa; 
            padding: 15px; 
            border-radius: 4px; 
            border-left: 4px solid #007bff; 
        }}
        .info-label {{ 
            font-weight: bold; 
            color: #555; 
            margin-bottom: 5px; 
        }}
        .info-value {{ color: #777; }}
        .map-link {{ 
            display: inline-block; 
            background: #007bff; 
            color: white; 
            padding: 12px 24px; 
            text-decoration: none; 
            border-radius: 4px; 
            margin: 20px 0; 
            transition: background 0.3s; 
        }}
        .map-link:hover {{ background: #0056b3; }}
        .features {{ 
            background: #e9ecef; 
            padding: 15px; 
            border-radius: 4px; 
            margin: 20px 0; 
        }}
        .features h3 {{ margin-top: 0; color: #495057; }}
        .features ul {{ margin: 10px 0; padding-left: 20px; }}
        .features li {{ margin: 5px 0; color: #6c757d; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>OGC交互式地图服务</h1>
        
        <div class="info-grid">
            <div class="info-item">
                <div class="info-label">图层名称</div>
                <div class="info-value">{layer_info.get('layer_title', layer_name)}</div>
            </div>
            <div class="info-item">
                <div class="info-label">服务名称</div>
                <div class="info-value">{layer_info.get('service_name', 'N/A')}</div>
            </div>
            <div class="info-item">
                <div class="info-label">坐标系</div>
                <div class="info-value">{layer_info.get('crs', 'EPSG:4326')}</div>
            </div>
            <div class="info-item">
                <div class="info-label">地图尺寸</div>
                <div class="info-value">{map_config.get('width', 1000)} × {map_config.get('height', 700)}</div>
            </div>
        </div>
        
        <a href="{html_filename}" class="map-link">🗺️ 查看交互式地图</a>
        
        <div class="features">
            <h3>功能特性</h3>
            <ul>
                <li>交互式地图浏览和导航</li>
                <li>图层切换和控制</li>
                <li>缩放和平移操作</li>
                <li>坐标显示和测量</li>
                <li>比例尺显示</li>
            </ul>
        </div>
    </div>
</body>
</html>"""


def _generate_geojson_index_page(layer_name: str, map_result: Dict[str, Any], html_filename: str) -> str:
    """生成GeoJSON专用索引页面HTML内容
    
    Args:
        layer_name: 图层名称
        map_result: 地图生成结果
        html_filename: HTML文件名
        
    Returns:
        索引页面HTML内容
    """
    layer_info = map_result.get("layer_info", {})
    stats = map_result.get("geojson_statistics", {})
    map_config = map_result.get("map_config", {})
    
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WFS GeoJSON地图服务 - {layer_name}</title>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background-color: #f5f5f5; 
        }}
        .container {{ 
            max-width: 800px; 
            margin: 0 auto; 
            background: white; 
            padding: 30px; 
            border-radius: 8px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
        }}
        h1 {{ color: #333; margin-bottom: 20px; }}
        .info-grid {{ 
            display: grid; 
            grid-template-columns: 1fr 1fr; 
            gap: 15px; 
            margin: 20px 0; 
        }}
        .info-item {{ 
            background: #f8f9fa; 
            padding: 15px; 
            border-radius: 4px; 
            border-left: 4px solid #28a745; 
        }}
        .info-label {{ 
            font-weight: bold; 
            color: #555; 
            margin-bottom: 5px; 
        }}
        .info-value {{ color: #777; }}
        .map-link {{ 
            display: inline-block; 
            background: #28a745; 
            color: white; 
            padding: 12px 24px; 
            text-decoration: none; 
            border-radius: 4px; 
            margin: 20px 0; 
            transition: background 0.3s; 
        }}
        .map-link:hover {{ background: #1e7e34; }}
        .features {{ 
            background: #e9ecef; 
            padding: 15px; 
            border-radius: 4px; 
            margin: 20px 0; 
        }}
        .features h3 {{ margin-top: 0; color: #495057; }}
        .features ul {{ margin: 10px 0; padding-left: 20px; }}
        .features li {{ margin: 5px 0; color: #6c757d; }}
        .stats {{ 
            background: #fff3cd; 
            padding: 15px; 
            border-radius: 4px; 
            margin: 20px 0; 
            border-left: 4px solid #ffc107; 
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>WFS GeoJSON交互式地图</h1>
        
        <div class="info-grid">
            <div class="info-item">
                <div class="info-label">图层名称</div>
                <div class="info-value">{layer_info.get('layer_title', layer_name)}</div>
            </div>
            <div class="info-item">
                <div class="info-label">服务名称</div>
                <div class="info-value">{layer_info.get('service_name', 'N/A')}</div>
            </div>
            <div class="info-item">
                <div class="info-label">要素数量</div>
                <div class="info-value">{stats.get('feature_count', 0)}</div>
            </div>
            <div class="info-item">
                <div class="info-label">几何类型</div>
                <div class="info-value">{', '.join(stats.get('geometry_types', []))}</div>
            </div>
        </div>
        
        <div class="stats">
            <h3>数据统计</h3>
            <p><strong>要素总数:</strong> {stats.get('feature_count', 0)}</p>
            <p><strong>属性字段:</strong> {len(stats.get('properties', []))}</p>
            <p><strong>几何类型:</strong> {', '.join(stats.get('geometry_types', []))}</p>
        </div>
        
        <a href="{html_filename}" class="map-link">🗺️ 查看GeoJSON交互式地图</a>
        
        <div class="features">
            <h3>功能特性</h3>
            <ul>
                <li>GeoJSON要素渲染和可视化</li>
                <li>要素点击显示属性信息</li>
                <li>支持缩放和平移操作</li>
                <li>图层控制和样式切换</li>
                <li>要素高亮和选择</li>
                <li>坐标显示和测量工具</li>
            </ul>
        </div>
    </div>
</body>
</html>"""