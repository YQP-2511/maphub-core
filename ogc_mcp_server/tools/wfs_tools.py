"""WFS工具模块

提供WFS相关的工具函数，包括要素数据获取和GeoJSON可视化
"""

import logging
from typing import Dict, Any, Optional
from fastmcp import FastMCP, Context
from pydantic import Field
from typing_extensions import Annotated

from ..database import get_layer_repository, LayerResourceQuery
from ..utils.ogc_parser import get_ogc_parser
from ..utils.geojson_utils import (
    fetch_geojson_data, analyze_geojson_data, parse_style_config,
    calculate_map_center, save_geojson_map_file
)
from ..utils.html_templates import generate_geojson_map_html

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
    save_to_file: Annotated[bool, Field(description="是否保存GeoJSON数据到文件")] = True,
    ctx: Context = None
) -> Dict[str, Any]:
    """获取WFS图层的GeoJSON数据
    
    直接获取WFS图层的GeoJSON格式数据，支持空间和属性过滤。
    为避免上下文长度超限，默认将GeoJSON数据保存到文件而不在响应中返回完整数据。
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
        geojson_data = await fetch_geojson_data(layer.service_url, params, ctx)
        stats = analyze_geojson_data(geojson_data)
        
        # 保存GeoJSON数据到文件（如果需要）
        geojson_file_path = None
        if save_to_file:
            geojson_file_path = await _save_geojson_to_file(layer_name, geojson_data)
        
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
            "geojson_file": geojson_file_path,   # 完整数据文件路径
            "parameters": {
                "max_features": max_features,
                "bbox": bbox,
                "cql_filter": cql_filter
            },
            "data_info": {
                "total_features": stats["feature_count"],
                "sample_count": len(sample_features),
                "note": "完整GeoJSON数据已保存到文件，此处仅显示前几个要素作为示例"
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
async def create_geojson_map(
    layer_name: Annotated[str, Field(description="WFS图层名称")],
    max_features: Annotated[int, Field(description="最大要素数量", ge=1, le=1000)] = 100,
    width: Annotated[int, Field(description="地图容器宽度", ge=300, le=2000)] = 1000,
    height: Annotated[int, Field(description="地图容器高度", ge=300, le=2000)] = 700,
    initial_zoom: Annotated[int, Field(description="初始缩放级别", ge=1, le=18)] = 10,
    style_config: Annotated[Optional[str], Field(description="样式配置JSON字符串")] = None,
    bbox: Annotated[Optional[str], Field(description="边界框过滤，格式：min_x,min_y,max_x,max_y")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """创建WFS GeoJSON交互式地图
    
    获取WFS图层数据并创建包含GeoJSON要素渲染的交互式地图。
    支持要素样式自定义、属性弹窗、图层控制等功能。
    为避免上下文长度超限，不在响应中返回完整的HTML内容和GeoJSON数据。
    """
    if ctx:
        await ctx.info(f"正在创建WFS GeoJSON交互式地图: {layer_name}")
    
    try:
        # 获取GeoJSON数据（内部处理，不返回完整数据）
        geojson_result = await _get_geojson_data_internal(
            layer_name, max_features, bbox, None, ctx
        )
        
        geojson_data = geojson_result["geojson"]
        layer_info = geojson_result["layer_info"]
        stats = geojson_result["statistics"]
        
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
            "file_size_kb": len(html_content) // 1024,  # 文件大小（KB）
            "instructions": {
                "usage": "在浏览器中打开生成的HTML文件即可查看GeoJSON交互式地图",
                "file_location": html_path,
                "features": [
                    "GeoJSON要素渲染和可视化",
                    "要素点击显示属性信息",
                    "支持缩放和平移操作",
                    "图层控制和样式切换",
                    "要素高亮和选择",
                    "坐标显示和测量工具"
                ],
                "note": "HTML内容已保存到文件，此处不显示完整内容以避免上下文长度超限"
            }
        }
        
        if ctx:
            await ctx.info(f"GeoJSON交互式地图创建成功: {layer_name}，HTML文件: {html_path}")
        
        logger.info(f"GeoJSON交互式地图创建成功: {layer_name}，要素数量: {stats['feature_count']}")
        return result
        
    except Exception as e:
        error_msg = f"创建GeoJSON交互式地图失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


# 内部辅助函数
async def _get_geojson_data_internal(
    layer_name: str, max_features: int, bbox: Optional[str], 
    cql_filter: Optional[str], ctx: Context = None
) -> Dict[str, Any]:
    """内部获取GeoJSON数据函数，返回完整数据用于地图生成"""
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
    geojson_data = await fetch_geojson_data(layer.service_url, params, ctx)
    stats = analyze_geojson_data(geojson_data)
    
    return {
        "layer_info": {
            "resource_id": layer.resource_id,
            "service_name": layer.service_name,
            "service_url": layer.service_url,
            "layer_name": layer.layer_name,
            "layer_title": layer.layer_title,
            "crs": layer.crs
        },
        "geojson": geojson_data,
        "statistics": stats
    }


async def _save_geojson_to_file(layer_name: str, geojson_data: Dict[str, Any]) -> str:
    """保存GeoJSON数据到文件"""
    import os
    import tempfile
    import json
    
    # 创建临时GeoJSON文件
    temp_dir = tempfile.gettempdir()
    geojson_filename = f"geojson_data_{layer_name.replace(':', '_').replace('/', '_')}.json"
    geojson_path = os.path.join(temp_dir, geojson_filename)
    
    with open(geojson_path, 'w', encoding='utf-8') as f:
        json.dump(geojson_data, f, ensure_ascii=False, indent=2)
    
    return geojson_path