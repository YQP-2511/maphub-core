"""GeoJSON工具模块

提供GeoJSON数据处理、分析和可视化相关的工具函数
"""

import json
import logging
import httpx
from typing import Dict, Any, Optional, List, Tuple
from fastmcp import Context

logger = logging.getLogger(__name__)


async def fetch_geojson_data(base_url: str, params: Dict[str, Any], ctx: Context = None) -> Dict[str, Any]:
    """获取GeoJSON数据
    
    Args:
        base_url: WFS服务基础URL
        params: 请求参数
        ctx: MCP上下文对象
        
    Returns:
        GeoJSON数据字典
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(base_url, params=params)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if 'json' in content_type:
                    return response.json()
                else:
                    # 尝试解析文本内容为JSON
                    text_content = response.text
                    return json.loads(text_content)
            else:
                raise Exception(f"HTTP请求失败: {response.status_code}")
    except Exception as e:
        logger.error(f"获取GeoJSON数据失败: {e}")
        raise


def analyze_geojson_data(geojson_data: Dict[str, Any]) -> Dict[str, Any]:
    """分析GeoJSON数据统计信息
    
    Args:
        geojson_data: GeoJSON数据
        
    Returns:
        统计信息字典
    """
    if not geojson_data or geojson_data.get("type") != "FeatureCollection":
        return {"feature_count": 0, "geometry_types": [], "properties": []}
    
    features = geojson_data.get("features", [])
    geometry_types = set()
    property_names = set()
    
    for feature in features:
        # 统计几何类型
        geometry = feature.get("geometry", {})
        if geometry:
            geometry_types.add(geometry.get("type", "Unknown"))
        
        # 统计属性字段
        properties = feature.get("properties", {})
        if properties:
            property_names.update(properties.keys())
    
    return {
        "feature_count": len(features),
        "geometry_types": list(geometry_types),
        "properties": list(property_names),
        "has_geometry": len(geometry_types) > 0,
        "has_properties": len(property_names) > 0
    }


def parse_style_config(style_config: Optional[str]) -> Dict[str, Any]:
    """解析样式配置
    
    Args:
        style_config: 样式配置JSON字符串
        
    Returns:
        样式配置字典
    """
    default_style = {
        "color": "#3388ff",
        "weight": 3,
        "opacity": 0.8,
        "fillColor": "#3388ff",
        "fillOpacity": 0.2,
        "radius": 6
    }
    
    if not style_config:
        return default_style
    
    try:
        custom_style = json.loads(style_config)
        default_style.update(custom_style)
        return default_style
    except json.JSONDecodeError:
        logger.warning("样式配置JSON解析失败，使用默认样式")
        return default_style


def calculate_map_center(geojson_data: Dict[str, Any], layer_info: Dict[str, Any]) -> Tuple[float, float]:
    """计算地图中心点
    
    Args:
        geojson_data: GeoJSON数据
        layer_info: 图层信息
        
    Returns:
        (纬度, 经度) 元组
    """
    # 默认中心点（北京）
    default_center = (39.9042, 116.4074)
    
    try:
        features = geojson_data.get("features", [])
        if not features:
            return default_center
        
        # 计算所有要素的边界框
        min_lat = min_lng = float('inf')
        max_lat = max_lng = float('-inf')
        
        for feature in features:
            geometry = feature.get("geometry", {})
            if not geometry:
                continue
            
            coords = extract_coordinates(geometry)
            for coord in coords:
                lng, lat = coord[0], coord[1]
                min_lat = min(min_lat, lat)
                max_lat = max(max_lat, lat)
                min_lng = min(min_lng, lng)
                max_lng = max(max_lng, lng)
        
        if min_lat != float('inf'):
            center_lat = (min_lat + max_lat) / 2
            center_lng = (min_lng + max_lng) / 2
            return (center_lat, center_lng)
        
    except Exception as e:
        logger.warning(f"计算地图中心点失败: {e}")
    
    return default_center


def extract_coordinates(geometry: Dict[str, Any]) -> List[List[float]]:
    """提取几何对象的坐标
    
    Args:
        geometry: GeoJSON几何对象
        
    Returns:
        坐标列表
    """
    coords = []
    geometry_type = geometry.get("type", "")
    coordinates = geometry.get("coordinates", [])
    
    if geometry_type == "Point":
        coords.append(coordinates)
    elif geometry_type in ["LineString", "MultiPoint"]:
        coords.extend(coordinates)
    elif geometry_type in ["Polygon", "MultiLineString"]:
        for ring in coordinates:
            coords.extend(ring)
    elif geometry_type == "MultiPolygon":
        for polygon in coordinates:
            for ring in polygon:
                coords.extend(ring)
    
    return coords


def save_geojson_map_file(layer_name: str, html_content: str) -> str:
    """保存GeoJSON地图HTML文件
    
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
    html_filename = f"geojson_map_{layer_name.replace(':', '_').replace('/', '_')}.html"
    html_path = os.path.join(temp_dir, html_filename)
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return html_path