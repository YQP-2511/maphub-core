"""WFS工具模块

提供WFS相关的工具函数，统一使用Web服务器提供可视化
"""

import logging
from typing import Dict, Any, Optional
from fastmcp import FastMCP, Context
from pydantic import Field
from typing_extensions import Annotated

from ..database import get_layer_repository, LayerResourceQuery
from ..utils.ogc_parser import get_ogc_parser
from ..services.web_server.server import get_web_server

logger = logging.getLogger(__name__)

# 创建WFS工具子服务器
wfs_server = FastMCP(name="WFS工具服务")


@wfs_server.tool
async def get_wfs_features(
    layer_name: Annotated[str, Field(description="WFS图层（要素类型）名称")],
    max_features: Annotated[int, Field(description="最大要素数量", ge=1, le=1000)] = 100,
    output_format: Annotated[str, Field(description="输出格式")] = "application/json",
    ctx: Context = None
) -> Dict[str, Any]:
    """获取WFS图层要素
    
    根据图层名称生成WFS GetFeature请求URL，返回要素数据的访问链接。
    """
    if ctx:
        await ctx.info(f"正在生成WFS要素访问链接: {layer_name}")
    
    try:
        repository = await get_layer_repository()
        query = LayerResourceQuery(layer_name=layer_name, service_type="WFS", limit=1)
        layers = await repository.list_resources(query)
        
        if not layers:
            raise ValueError(f"未找到WFS图层: {layer_name}")
        
        layer = layers[0]
        parser = await get_ogc_parser()
        feature_url = parser.get_wfs_feature_url(
            base_url=layer.service_url,
            type_name=layer.layer_name,
            max_features=max_features,
            output_format=output_format
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
            "feature_url": feature_url,
            "parameters": {
                "max_features": max_features,
                "output_format": output_format
            }
        }
        
        if ctx:
            await ctx.info(f"WFS要素URL生成成功: {layer_name}")
        
        logger.info(f"WFS要素URL生成成功: {layer_name}")
        return result
        
    except Exception as e:
        error_msg = f"生成WFS要素URL失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


@wfs_server.tool
async def get_wfs_geojson_data(
    layer_name: Annotated[str, Field(description="WFS图层名称")],
    max_features: Annotated[int, Field(description="最大要素数量", ge=1, le=1000)] = 100,
    bbox: Annotated[Optional[str], Field(description="边界框过滤，格式：min_x,min_y,max_x,max_y")] = None,
    cql_filter: Annotated[Optional[str], Field(description="CQL过滤条件")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """获取WFS图层的GeoJSON数据
    
    直接获取WFS图层的GeoJSON格式数据，支持空间和属性过滤。
    返回数据统计信息和示例要素，完整数据通过Web可视化查看。
    """
    if ctx:
        await ctx.info(f"正在获取WFS图层GeoJSON数据: {layer_name}")
    
    try:
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
        if cql_filter:
            params["cql_filter"] = cql_filter
        
        # 获取GeoJSON数据
        geojson_data = await _fetch_geojson_data(layer.service_url, params, ctx)
        stats = _analyze_geojson_data(geojson_data)
        
        # 提取前几个要素作为示例（避免返回完整数据）
        sample_features = []
        if geojson_data.get("features"):
            sample_count = min(3, len(geojson_data["features"]))
            sample_features = geojson_data["features"][:sample_count]
        
        result = {
            "layer_info": {
                "resource_id": layer.resource_id,
                "service_name": layer.service_name,
                "service_url": layer.service_url,
                "layer_name": layer.layer_name,
                "layer_title": layer.layer_title,
                "crs": layer.crs
            },
            "statistics": stats,
            "sample_features": sample_features,  # 只返回前几个要素作为示例
            "parameters": {
                "max_features": max_features,
                "bbox": bbox,
                "cql_filter": cql_filter
            },
            "data_info": {
                "total_features": stats["feature_count"],
                "sample_count": len(sample_features),
                "note": "此处仅显示前几个要素作为示例，完整数据请使用Web可视化功能查看"
            },
            "instructions": {
                "visualization": "使用 create_geojson_visualization 工具创建完整的Web可视化",
                "features": [
                    "完整的GeoJSON要素数据展示",
                    "交互式地图浏览",
                    "要素属性查看",
                    "空间分析功能"
                ]
            }
        }
        
        if ctx:
            await ctx.info(f"GeoJSON数据获取成功: {layer_name}，共 {stats['feature_count']} 个要素")
        
        logger.info(f"GeoJSON数据获取成功: {layer_name}，要素数量: {stats['feature_count']}")
        return result
        
    except Exception as e:
        error_msg = f"获取GeoJSON数据失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


@wfs_server.tool
async def create_geojson_visualization(
    layer_name: Annotated[str, Field(description="WFS图层名称")],
    max_features: Annotated[int, Field(description="最大要素数量", ge=1, le=1000)] = 100,
    width: Annotated[int, Field(description="地图容器宽度", ge=300, le=2000)] = 1000,
    height: Annotated[int, Field(description="地图容器高度", ge=300, le=2000)] = 700,
    initial_zoom: Annotated[int, Field(description="初始缩放级别", ge=1, le=18)] = 10,
    style_config: Annotated[Optional[str], Field(description="样式配置JSON字符串")] = None,
    bbox: Annotated[Optional[str], Field(description="边界框过滤，格式：min_x,min_y,max_x,max_y")] = None,
    cql_filter: Annotated[Optional[str], Field(description="CQL过滤条件")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """创建WFS GeoJSON Web可视化
    
    在统一Web服务器中创建WFS图层的GeoJSON交互式地图可视化。
    支持CQL过滤条件和边界框过滤，提供完整的交互式地图功能。
    """
    if ctx:
        await ctx.info(f"正在创建WFS GeoJSON可视化: {layer_name}")
    
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
        
        # 添加过滤条件
        if bbox:
            params["bbox"] = bbox
        if cql_filter:
            params["cql_filter"] = cql_filter
        
        # 获取GeoJSON数据
        geojson_data = await _fetch_geojson_data(layer.service_url, params, ctx)
        stats = _analyze_geojson_data(geojson_data)
        
        # 构建图层信息
        layer_info = {
            "resource_id": layer.resource_id,
            "service_name": layer.service_name,
            "service_url": layer.service_url,
            "layer_name": layer.layer_name,
            "layer_title": layer.layer_title,
            "crs": layer.crs
        }
        
        # 解析样式配置
        style_options = _parse_style_config(style_config)
        
        # 构建地图配置
        map_config = {
            "center": [39.9042, 116.4074],  # 默认中心点，Web服务器会自动计算
            "zoom": initial_zoom,
            "width": width,
            "height": height,
            "style": style_options
        }
        
        # 获取Web服务器并添加可视化
        web_server = await get_web_server()
        visualization_url = await web_server.add_geojson_visualization(
            layer_name, layer_info, geojson_data, stats, map_config
        )
        
        result = {
            "visualization_info": {
                "type": "geojson",
                "layer_name": layer_name,
                "url": visualization_url,
                "web_server": web_server._get_base_url()
            },
            "layer_info": layer_info,
            "geojson_statistics": stats,
            "map_config": map_config,
            "filter_info": {
                "bbox": bbox,
                "cql_filter": cql_filter,
                "max_features": max_features
            },
            "instructions": {
                "access": f"在浏览器中访问: {visualization_url}",
                "web_server": f"Web服务器首页: {web_server._get_base_url()}",
                "features": [
                    "WFS GeoJSON要素可视化",
                    "要素属性弹窗查看",
                    "交互式地图操作",
                    "样式自定义和图层控制",
                    "坐标显示和测量工具",
                    "支持CQL过滤和空间过滤"
                ]
            }
        }
        
        if ctx:
            filter_info = []
            if cql_filter:
                filter_info.append(f"CQL过滤: {cql_filter}")
            if bbox:
                filter_info.append(f"边界框: {bbox}")
            filter_text = f" (过滤条件: {', '.join(filter_info)})" if filter_info else ""
            await ctx.info(f"GeoJSON可视化创建成功，要素数量: {stats['feature_count']}{filter_text}，访问地址: {visualization_url}")
        
        logger.info(f"GeoJSON可视化创建成功: {layer_name}，要素数量: {stats['feature_count']}")
        return result
        
    except Exception as e:
        error_msg = f"创建GeoJSON可视化失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


# 内部辅助函数（简化版，主要逻辑移到Web服务器）
async def _fetch_geojson_data(base_url: str, params: Dict[str, Any], ctx: Context = None) -> Dict[str, Any]:
    """获取GeoJSON数据"""
    import httpx
    import json
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(base_url, params=params)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if 'json' in content_type:
                    return response.json()
                else:
                    text_content = response.text
                    return json.loads(text_content)
            else:
                raise Exception(f"HTTP请求失败: {response.status_code}")
    except Exception as e:
        logger.error(f"获取GeoJSON数据失败: {e}")
        raise


def _analyze_geojson_data(geojson_data: Dict[str, Any]) -> Dict[str, Any]:
    """分析GeoJSON数据统计信息"""
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


def _parse_style_config(style_config: Optional[str]) -> Dict[str, Any]:
    """解析样式配置"""
    import json
    
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