"""统一可视化工具模块

基于资源驱动设计的统一可视化工具
通过ogc://layer/{layer_name}资源获取图层详细信息，支持WMS、WFS和GeoJSON的统一可视化
"""

import json
import logging
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP, Context
from pydantic import Field
from typing_extensions import Annotated

from ..services.web_server.server import get_web_server

logger = logging.getLogger(__name__)

# 创建统一可视化工具服务器
visualization_server = FastMCP(name="统一可视化工具")


@visualization_server.tool
async def create_visualization(
    layer_names: Annotated[List[str], Field(description="图层名称列表")],
    visualization_type: Annotated[str, Field(description="可视化类型: single, layered, comparison")] = "layered",
    title: Annotated[str, Field(description="可视化标题")] = "地图可视化",
    map_config: Annotated[Optional[Dict[str, Any]], Field(description="地图配置")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """创建统一的地图可视化
    
    基于资源驱动设计，通过图层名称自动获取图层详细信息并创建可视化。
    支持WMS、WFS图层的自动识别和处理。
    
    Args:
        layer_names: 图层名称列表
        visualization_type: 可视化类型
            - single: 单图层显示
            - layered: 多图层叠加显示
            - comparison: 并排对比显示
        title: 可视化标题
        map_config: 地图配置（中心点、缩放级别等）
        ctx: MCP上下文对象
        
    Returns:
        可视化结果信息，包含访问URL和图层详情
    """
    if ctx:
        await ctx.info(f"正在创建{visualization_type}可视化: {title}")
    
    try:
        if not layer_names:
            raise ValueError("至少需要提供一个图层名称")
        
        # 通过资源获取所有图层的详细信息
        processed_layers = []
        for layer_name in layer_names:
            if ctx:
                await ctx.info(f"正在处理图层: {layer_name}")
            
            layer_info = await _get_layer_from_resource(layer_name, ctx)
            processed_layer = await _process_layer_for_visualization(layer_info, ctx)
            processed_layers.append(processed_layer)
        
        # 配置地图参数
        final_map_config = _configure_map_settings(processed_layers, map_config)
        
        # 创建可视化
        web_server = await get_web_server()
        
        if visualization_type == "single":
            # 单图层显示
            layer = processed_layers[0]
            visualization_url = await _create_single_visualization(
                web_server, layer, title, final_map_config
            )
        elif visualization_type == "comparison":
            # 对比显示
            visualization_urls = []
            for i, layer in enumerate(processed_layers):
                layer_title = f"{title} - {layer['name']}"
                url = await _create_single_visualization(
                    web_server, layer, layer_title, final_map_config
                )
                visualization_urls.append(url)
            visualization_url = visualization_urls[0]
        else:
            # 分层叠加显示（默认）
            visualization_url = await web_server.add_composite_visualization(
                title=title,
                layers=processed_layers,
                map_config=final_map_config
            )
        
        # 构建结果
        result = {
            "visualization_info": {
                "type": visualization_type,
                "title": title,
                "url": visualization_url,
                "web_server": web_server._get_base_url()
            },
            "layer_summary": {
                "total_layers": len(processed_layers),
                "layer_details": [
                    {
                        "name": layer["name"],
                        "service_type": layer["service_type"],
                        "feature_count": layer.get("stats", {}).get("feature_count", 0)
                    }
                    for layer in processed_layers
                ]
            },
            "map_config": final_map_config,
            "instructions": {
                "access": f"在浏览器中访问: {visualization_url}",
                "web_server": f"Web服务器首页: {web_server._get_base_url()}"
            }
        }
        
        # 对比模式添加所有URL
        if visualization_type == "comparison" and 'visualization_urls' in locals():
            result["comparison_urls"] = visualization_urls
        
        if ctx:
            await ctx.info(f"可视化创建成功！共{len(processed_layers)}个图层")
            await ctx.info(f"访问地址: {visualization_url}")
        
        logger.info(f"可视化创建成功: {title}，图层数: {len(processed_layers)}")
        return result
        
    except Exception as e:
        error_msg = f"创建可视化失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


@visualization_server.tool
async def get_layer_visualization_info(
    layer_name: Annotated[str, Field(description="图层名称")],
    ctx: Context = None
) -> Dict[str, Any]:
    """获取图层的可视化信息
    
    通过资源获取图层详细信息，包括可视化所需的所有参数。
    
    Args:
        layer_name: 图层名称
        ctx: MCP上下文对象
        
    Returns:
        图层的可视化信息
    """
    if ctx:
        await ctx.info(f"正在获取图层可视化信息: {layer_name}")
    
    try:
        # 通过资源获取图层信息
        layer_info = await _get_layer_from_resource(layer_name, ctx)
        
        # 提取可视化相关信息
        result = {
            "layer_name": layer_name,
            "basic_info": layer_info["basic_info"],
            "visualization_capabilities": {
                "service_type": layer_info["basic_info"]["service_type"],
                "supports_wms": layer_info["access_parameters"].get("wms") is not None,
                "supports_wfs": layer_info["access_parameters"].get("wfs") is not None,
                "bbox": layer_info["capabilities"]["bbox"],
                "crs_list": layer_info["capabilities"]["crs_list"],
                "default_crs": layer_info["capabilities"]["default_crs"]
            },
            "access_parameters": layer_info["access_parameters"],
            "recommended_config": {
                "center": _calculate_center_from_bbox(layer_info["capabilities"]["bbox"]),
                "zoom": _calculate_optimal_zoom(layer_info["capabilities"]["bbox"]),
                "crs": layer_info["capabilities"]["default_crs"]
            }
        }
        
        if ctx:
            await ctx.info(f"成功获取图层可视化信息: {layer_name}")
        
        return result
        
    except Exception as e:
        error_msg = f"获取图层可视化信息失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


# 辅助函数

async def _get_layer_from_resource(layer_name: str, ctx: Context) -> Dict[str, Any]:
    """通过资源获取图层信息"""
    layer_resource = await ctx.read_resource(f"ogc://layer/{layer_name}")
    
    if not layer_resource or not layer_resource[0].content:
        raise ValueError(f"未找到图层资源: {layer_name}")
    
    layer_data = layer_resource[0].content
    
    # 如果content是字符串，需要解析为JSON
    if isinstance(layer_data, str):
        try:
            layer_data = json.loads(layer_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"图层资源JSON解析失败: {e}")
    
    # 检查是否包含错误信息
    if isinstance(layer_data, dict) and "error" in layer_data:
        raise ValueError(f"图层资源错误: {layer_data['error']}")
    
    return layer_data


async def _process_layer_for_visualization(
    layer_info: Dict[str, Any], 
    ctx: Context
) -> Dict[str, Any]:
    """处理图层信息用于可视化"""
    basic_info = layer_info["basic_info"]
    service_type = basic_info["service_type"].upper()
    
    processed_layer = {
        "name": basic_info["layer_name"],  # 修复：使用layer_name而不是name
        "title": basic_info["layer_title"],  # 修复：使用layer_title而不是title
        "service_type": service_type,
        "layer_info": basic_info
    }
    
    if service_type == "WFS":
        # WFS图层转换为GeoJSON进行可视化
        processed_layer["type"] = "geojson"
        processed_layer["geojson_data"] = await _fetch_wfs_data_for_visualization(
            layer_info, ctx
        )
        processed_layer["stats"] = _calculate_geojson_stats(processed_layer["geojson_data"])
        processed_layer["style"] = _get_default_geojson_style()
    else:
        # WMS图层直接使用
        processed_layer["type"] = "wms"
    
    return processed_layer


async def _fetch_wfs_data_for_visualization(
    layer_info: Dict[str, Any], 
    ctx: Context
) -> Dict[str, Any]:
    """获取WFS数据用于可视化"""
    from ..utils.ogc_parser import get_ogc_parser
    
    basic_info = layer_info["basic_info"]
    wfs_params = layer_info["access_parameters"]["wfs"]
    
    parser = await get_ogc_parser()
    
    # 构建WFS请求参数
    params = {
        "service": "WFS",
        "version": wfs_params["version"],
        "request": "GetFeature",
        "typeNames": wfs_params["typeNames"],
        "maxFeatures": min(wfs_params.get("maxFeatures", 100), 100),  # 限制数量
        "outputFormat": "application/json"
    }
    
    # 发送请求 - 修复：使用service_url而不是url
    response = await parser.http_client.get(basic_info["service_url"], params=params)
    
    if response.status_code != 200:
        raise RuntimeError(f"WFS请求失败: {response.status_code}")
    
    return response.json()


async def _create_single_visualization(
    web_server, 
    layer: Dict[str, Any], 
    title: str, 
    map_config: Dict[str, Any]
) -> str:
    """创建单个图层的可视化"""
    if layer["type"] == "wms":
        return await web_server.add_wms_visualization(
            layer_name=title,
            layer_info=layer["layer_info"],
            map_config=map_config
        )
    else:
        return await web_server.add_geojson_visualization(
            layer_name=title,
            layer_info=layer["layer_info"],
            geojson_data=layer["geojson_data"],
            stats=layer.get("stats", {}),
            map_config=map_config
        )


def _configure_map_settings(
    processed_layers: List[Dict[str, Any]], 
    user_config: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """配置地图设置"""
    default_config = {
        "center": [39.9042, 116.4074],  # 默认北京
        "zoom": 10,
        "width": 1200,
        "height": 800
    }
    
    if user_config:
        default_config.update(user_config)
    
    return default_config


def _calculate_center_from_bbox(bbox_info: Dict[str, Any]) -> List[float]:
    """从边界框计算中心点"""
    if bbox_info and "wgs84" in bbox_info:
        bbox = bbox_info["wgs84"]
        center_lon = (bbox[0] + bbox[2]) / 2
        center_lat = (bbox[1] + bbox[3]) / 2
        return [center_lat, center_lon]
    return [39.9042, 116.4074]  # 默认北京


def _calculate_optimal_zoom(bbox_info: Dict[str, Any]) -> int:
    """计算最佳缩放级别"""
    if bbox_info and "wgs84" in bbox_info:
        bbox = bbox_info["wgs84"]
        width = abs(bbox[2] - bbox[0])
        height = abs(bbox[3] - bbox[1])
        max_extent = max(width, height)
        
        if max_extent > 10:
            return 5
        elif max_extent > 1:
            return 8
        elif max_extent > 0.1:
            return 10
        else:
            return 12
    return 10


def _calculate_geojson_stats(geojson_data: Dict[str, Any]) -> Dict[str, Any]:
    """计算GeoJSON统计信息"""
    features = geojson_data.get("features", [])
    return {
        "feature_count": len(features),
        "geometry_types": list(set(
            feature.get("geometry", {}).get("type", "Unknown") 
            for feature in features
        ))
    }


def _get_default_geojson_style() -> Dict[str, Any]:
    """获取默认GeoJSON样式"""
    return {
        "color": "#3388ff",
        "weight": 2,
        "opacity": 0.8,
        "fillColor": "#3388ff",
        "fillOpacity": 0.3,
        "radius": 6
    }