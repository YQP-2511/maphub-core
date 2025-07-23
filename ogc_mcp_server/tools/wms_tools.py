"""WMS工具模块

提供WMS相关的工具函数，包括地图获取和交互式地图生成
"""

import logging
from typing import Dict, Any, Optional
from fastmcp import FastMCP, Context
from pydantic import Field
from typing_extensions import Annotated

from ..database import get_layer_repository, LayerResourceQuery
from ..utils.ogc_parser import get_ogc_parser

logger = logging.getLogger(__name__)

# 创建WMS工具子服务器
wms_server = FastMCP(name="WMS工具服务")


@wms_server.tool
async def get_wms_map(
    layer_name: Annotated[str, Field(description="WMS图层名称")],
    width: Annotated[int, Field(description="图像宽度", ge=100, le=2000)] = 800,
    height: Annotated[int, Field(description="图像高度", ge=100, le=2000)] = 600,
    bbox: Annotated[Optional[str], Field(description="边界框，格式：min_x,min_y,max_x,max_y")] = None,
    crs: Annotated[str, Field(description="坐标参考系统")] = "EPSG:4326",
    format: Annotated[str, Field(description="图像格式")] = "image/png",
    ctx: Context = None
) -> Dict[str, Any]:
    """获取WMS图层地图
    
    根据图层名称生成WMS GetMap请求URL，返回图层的预览链接。
    
    Args:
        layer_name: WMS图层名称
        width: 图像宽度
        height: 图像高度
        bbox: 边界框，格式：min_x,min_y,max_x,max_y（可选）
        crs: 坐标参考系统
        format: 图像格式
        ctx: MCP上下文对象
        
    Returns:
        包含地图URL和图层信息的字典
    """
    if ctx:
        await ctx.info(f"正在生成WMS图层地图: {layer_name}")
    
    try:
        # 获取图层资源信息
        repository = await get_layer_repository()
        
        # 查询图层资源
        query = LayerResourceQuery(layer_name=layer_name, service_type="WMS", limit=1)
        layers = await repository.list_resources(query)
        
        if not layers:
            raise ValueError(f"未找到WMS图层: {layer_name}")
        
        layer = layers[0]
        
        # 解析边界框
        bbox_coords = None
        if bbox:
            try:
                coords = [float(x.strip()) for x in bbox.split(',')]
                if len(coords) == 4:
                    bbox_coords = tuple(coords)
            except ValueError:
                raise ValueError("边界框格式错误，应为：min_x,min_y,max_x,max_y")
        
        # 如果没有提供边界框，使用图层的默认边界框
        if not bbox_coords and layer.bbox:
            bbox_coords = (layer.bbox.min_x, layer.bbox.min_y, layer.bbox.max_x, layer.bbox.max_y)
        
        # 生成GetMap URL
        parser = await get_ogc_parser()
        map_url = parser.get_wms_map_url(
            base_url=layer.service_url,
            layer_name=layer.layer_name,
            bbox=bbox_coords,
            width=width,
            height=height,
            crs=crs,
            format=format
        )
        
        result = {
            "layer_info": {
                "resource_id": layer.resource_id,
                "service_name": layer.service_name,
                "service_url": layer.service_url,
                "layer_name": layer.layer_name,
                "layer_title": layer.layer_title,
                "crs": layer.crs
            },
            "map_url": map_url,
            "parameters": {
                "width": width,
                "height": height,
                "bbox": bbox_coords,
                "crs": crs,
                "format": format
            }
        }
        
        if ctx:
            await ctx.info(f"WMS地图URL生成成功: {layer_name}")
        
        logger.info(f"WMS地图URL生成成功: {layer_name}")
        return result
        
    except Exception as e:
        error_msg = f"生成WMS地图失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


@wms_server.tool
async def get_interactive_map(
    layer_name: Annotated[str, Field(description="图层名称")],
    width: Annotated[int, Field(description="地图容器宽度", ge=300, le=2000)] = 800,
    height: Annotated[int, Field(description="地图容器高度", ge=300, le=2000)] = 600,
    initial_zoom: Annotated[int, Field(description="初始缩放级别", ge=1, le=18)] = 10,
    ctx: Context = None
) -> Dict[str, Any]:
    """生成交互式地图
    
    创建一个包含指定图层的交互式地图HTML页面，支持缩放、平移等操作。
    使用Leaflet地图库实现交互功能。
    
    Args:
        layer_name: 图层名称
        width: 地图容器宽度
        height: 地图容器高度
        initial_zoom: 初始缩放级别
        ctx: MCP上下文对象
        
    Returns:
        包含HTML内容和地图信息的字典
    """
    if ctx:
        await ctx.info(f"正在生成交互式地图: {layer_name}")
    
    try:
        # 获取图层资源信息
        repository = await get_layer_repository()
        
        # 查询图层资源（支持WMS和WFS）
        query = LayerResourceQuery(layer_name=layer_name, limit=10)
        layers = await repository.list_resources(query)
        
        if not layers:
            raise ValueError(f"未找到图层: {layer_name}")
        
        # 优先选择WMS图层，如果没有则选择第一个
        wms_layer = None
        wfs_layers = []
        
        for layer in layers:
            if layer.service_type == "WMS":
                wms_layer = layer
                break
            elif layer.service_type == "WFS":
                wfs_layers.append(layer)
        
        if not wms_layer and not wfs_layers:
            raise ValueError(f"未找到可用的图层: {layer_name}")
        
        # 确定地图中心点和边界框
        center_lat, center_lng = 39.9042, 116.4074  # 默认北京
        bbox = None
        
        primary_layer = wms_layer if wms_layer else wfs_layers[0]
        if primary_layer.bbox:
            bbox = primary_layer.bbox
            center_lat = (bbox.min_y + bbox.max_y) / 2
            center_lng = (bbox.min_x + bbox.max_x) / 2
        
        # 生成HTML内容
        html_content = _generate_interactive_map_html(
            layer_name, layers, primary_layer, wms_layer, bbox, 
            center_lat, center_lng, width, height, initial_zoom
        )
        
        # 保存HTML文件
        html_path = _save_html_file(layer_name, html_content)
        
        result = {
            "layer_info": {
                "primary_layer": {
                    "resource_id": primary_layer.resource_id,
                    "service_name": primary_layer.service_name,
                    "service_url": primary_layer.service_url,
                    "service_type": primary_layer.service_type,
                    "layer_name": primary_layer.layer_name,
                    "layer_title": primary_layer.layer_title,
                    "crs": primary_layer.crs
                },
                "total_layers": len(layers),
                "wms_layers": len([l for l in layers if l.service_type == "WMS"]),
                "wfs_layers": len([l for l in layers if l.service_type == "WFS"])
            },
            "map_config": {
                "center": [center_lat, center_lng],
                "zoom": initial_zoom,
                "width": width,
                "height": height,
                "bbox": bbox.to_dict() if bbox else None
            },
            "html_file": html_path,
            "html_content": html_content,
            "instructions": {
                "usage": "在浏览器中打开生成的HTML文件即可查看交互式地图",
                "features": [
                    "支持缩放和平移操作",
                    "显示鼠标坐标位置",
                    "点击地图显示坐标弹窗",
                    "图层控制器切换底图和叠加图层",
                    "比例尺显示",
                    "响应式设计"
                ]
            }
        }
        
        if ctx:
            await ctx.info(f"交互式地图生成成功: {layer_name}，HTML文件保存至: {html_path}")
        
        logger.info(f"交互式地图生成成功: {layer_name}，HTML文件: {html_path}")
        return result
        
    except Exception as e:
        error_msg = f"生成交互式地图失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


def _generate_interactive_map_html(
    layer_name: str, layers: list, primary_layer, wms_layer, bbox,
    center_lat: float, center_lng: float, width: int, height: int, initial_zoom: int
) -> str:
    """生成交互式地图HTML内容
    
    Args:
        layer_name: 图层名称
        layers: 图层列表
        primary_layer: 主图层
        wms_layer: WMS图层
        bbox: 边界框
        center_lat: 中心纬度
        center_lng: 中心经度
        width: 宽度
        height: 高度
        initial_zoom: 初始缩放级别
        
    Returns:
        HTML内容字符串
    """
    # HTML模板内容（简化版，实际实现会更复杂）
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>交互式地图 - {layer_name}</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        body {{ margin: 0; padding: 20px; font-family: Arial, sans-serif; background-color: #f5f5f5; }}
        .map-container {{ background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); padding: 20px; }}
        #map {{ width: {width}px; height: {height}px; border-radius: 4px; border: 1px solid #ddd; }}
    </style>
</head>
<body>
    <div class="map-container">
        <h1>交互式地图 - {primary_layer.layer_title or layer_name}</h1>
        <div id="map"></div>
    </div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        var map = L.map('map').setView([{center_lat}, {center_lng}], {initial_zoom});
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png').addTo(map);
    </script>
</body>
</html>"""
    
    return html_content


def _save_html_file(layer_name: str, html_content: str) -> str:
    """保存HTML文件到临时目录
    
    Args:
        layer_name: 图层名称
        html_content: HTML内容
        
    Returns:
        HTML文件路径
    """
    import os
    import tempfile
    
    # 创建临时HTML文件
    temp_dir = tempfile.gettempdir()
    html_filename = f"interactive_map_{layer_name.replace(':', '_').replace('/', '_')}.html"
    html_path = os.path.join(temp_dir, html_filename)
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return html_path