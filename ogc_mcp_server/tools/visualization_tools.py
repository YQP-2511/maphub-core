"""多图层可视化工具模块

基于FastMCP最佳实践设计的多图层可视化工具
让AI自主选择WMS或WFS图层，支持灵活的图层组合和可视化
移除自动判断逻辑，由AI根据数据特性和需求决定服务类型

工具设计：
- add_wms_layer: 添加WMS图层到可视化
- add_wfs_layer: 添加WFS图层到可视化  
- create_composite_visualization: 创建多图层复合可视化
- clear_visualization_layers: 清空当前图层列表
"""

import json
import logging
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP, Context
from pydantic import Field
from typing_extensions import Annotated

from ..services.web_server.server import get_web_server
from ..utils.ogc_parser import get_ogc_parser

logger = logging.getLogger(__name__)

# 创建多图层可视化工具服务器
visualization_server = FastMCP(name="多图层可视化工具")

# 全局图层存储（在实际应用中可以考虑使用更持久的存储）
_current_layers: List[Dict[str, Any]] = []


@visualization_server.tool
async def add_wms_layer(
    layer_name: Annotated[str, Field(description="WMS图层名称")],
    layer_title: Annotated[str, Field(description="图层显示标题")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """添加WMS图层到可视化列表
    
    专门用于添加WMS（地图图像）图层，适合：
    - 底图和背景图层
    - 栅格数据可视化
    - 大范围地理数据展示
    
    Args:
        layer_name: WMS图层名称
        layer_title: 图层显示标题（可选，默认使用图层名称）
        ctx: MCP上下文对象
        
    Returns:
        添加结果和当前图层列表状态
    """
    try:
        if ctx:
            await ctx.info(f"正在添加WMS图层: {layer_name}")
        
        # 获取图层信息
        layer_info = await _get_layer_from_resource(layer_name, ctx)
        
        # 验证图层支持WMS
        if not layer_info["access_parameters"].get("wms"):
            raise ValueError(f"图层 {layer_name} 不支持WMS服务")
        
        # 创建WMS图层对象
        wms_layer = await _create_wms_layer(layer_info, layer_title or layer_name, ctx)
        
        # 添加到图层列表
        _current_layers.append(wms_layer)
        
        if ctx:
            await ctx.info(f"✅ WMS图层 {layer_name} 添加成功，当前共 {len(_current_layers)} 个图层")
        
        return {
            "success": True,
            "layer_added": {
                "name": layer_name,
                "title": wms_layer["title"],
                "type": "wms"
            },
            "current_layer_count": len(_current_layers),
            "message": f"WMS图层 {layer_name} 已添加到可视化列表"
        }
        
    except Exception as e:
        error_msg = f"添加WMS图层失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


@visualization_server.tool
async def add_wfs_layer(
    layer_name: Annotated[str, Field(description="WFS图层名称")],
    layer_title: Annotated[str, Field(description="图层显示标题")] = None,
    max_features: Annotated[int, Field(description="最大要素数量")] = 100,
    ctx: Context = None
) -> Dict[str, Any]:
    """添加WFS图层到可视化列表
    
    专门用于添加WFS（要素数据）图层，适合：
    - 矢量数据可视化
    - 属性数据展示
    - 交互式要素查询
    
    Args:
        layer_name: WFS图层名称
        layer_title: 图层显示标题（可选，默认使用图层名称）
        max_features: 最大要素数量（默认100，避免数据过载）
        ctx: MCP上下文对象
        
    Returns:
        添加结果和当前图层列表状态
    """
    try:
        if ctx:
            await ctx.info(f"正在添加WFS图层: {layer_name}，最大要素数: {max_features}")
        
        # 获取图层信息
        layer_info = await _get_layer_from_resource(layer_name, ctx)
        
        # 验证图层支持WFS
        if not layer_info["access_parameters"].get("wfs"):
            raise ValueError(f"图层 {layer_name} 不支持WFS服务")
        
        # 创建WFS图层对象
        wfs_layer = await _create_wfs_layer(layer_info, layer_title or layer_name, max_features, ctx)
        
        # 添加到图层列表
        _current_layers.append(wfs_layer)
        
        feature_count = len(wfs_layer.get("geojson_data", {}).get("features", []))
        if ctx:
            await ctx.info(f"✅ WFS图层 {layer_name} 添加成功，包含 {feature_count} 个要素，当前共 {len(_current_layers)} 个图层")
        
        return {
            "success": True,
            "layer_added": {
                "name": layer_name,
                "title": wfs_layer["title"],
                "type": "wfs",
                "feature_count": feature_count
            },
            "current_layer_count": len(_current_layers),
            "message": f"WFS图层 {layer_name} 已添加到可视化列表，包含 {feature_count} 个要素"
        }
        
    except Exception as e:
        error_msg = f"添加WFS图层失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


@visualization_server.tool
async def create_composite_visualization(
    title: Annotated[str, Field(description="可视化标题")] = "多图层复合可视化",
    visualization_type: Annotated[str, Field(description="可视化类型: overlay(叠加显示), comparison(对比显示)")] = "overlay",
    ctx: Context = None
) -> Dict[str, Any]:
    """创建多图层复合可视化
    
    将当前添加的所有图层组合成一个可视化页面
    支持叠加显示和对比显示两种模式
    
    Args:
        title: 可视化标题
        visualization_type: 可视化类型（overlay叠加 或 comparison对比）
        ctx: MCP上下文对象
        
    Returns:
        可视化结果，包含访问链接和图层信息
    """
    try:
        if not _current_layers:
            raise ValueError("没有可用的图层，请先使用 add_wms_layer 或 add_wfs_layer 添加图层")
        
        if ctx:
            await ctx.info(f"正在创建 {visualization_type} 类型的复合可视化，包含 {len(_current_layers)} 个图层")
        
        # 获取Web服务器
        web_server = await get_web_server()
        
        # 配置地图设置
        map_config = _configure_map_settings(_current_layers)
        
        # 根据可视化类型创建结果
        if visualization_type == "comparison":
            result = await _create_comparison_visualization(web_server, _current_layers, title, map_config, ctx)
        else:
            result = await _create_overlay_visualization(web_server, _current_layers, title, map_config, ctx)
        
        if ctx:
            await ctx.info(f"✅ 复合可视化创建成功: {title}")
        
        return result
        
    except Exception as e:
        error_msg = f"创建复合可视化失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


@visualization_server.tool
async def clear_visualization_layers(
    ctx: Context = None
) -> Dict[str, Any]:
    """清空当前图层列表
    
    清除所有已添加的图层，为新的可视化做准备
    
    Args:
        ctx: MCP上下文对象
        
    Returns:
        清空操作结果
    """
    global _current_layers
    
    layer_count = len(_current_layers)
    _current_layers.clear()
    
    if ctx:
        await ctx.info(f"已清空 {layer_count} 个图层，可以开始新的可视化")
    
    return {
        "success": True,
        "cleared_layer_count": layer_count,
        "current_layer_count": 0,
        "message": f"已清空 {layer_count} 个图层，图层列表已重置"
    }


@visualization_server.tool
async def list_current_layers(
    ctx: Context = None
) -> Dict[str, Any]:
    """列出当前已添加的图层
    
    显示当前图层列表的状态，包括图层类型和基本信息
    
    Args:
        ctx: MCP上下文对象
        
    Returns:
        当前图层列表信息
    """
    if not _current_layers:
        return {
            "success": True,
            "layer_count": 0,
            "layers": [],
            "message": "当前没有图层，请使用 add_wms_layer 或 add_wfs_layer 添加图层"
        }
    
    layer_summaries = []
    for layer in _current_layers:
        summary = {
            "name": layer["name"],
            "title": layer["title"],
            "type": layer["type"],
            "service_type": layer.get("service_type", "unknown")
        }
        
        if layer["type"] == "wfs":
            feature_count = len(layer.get("geojson_data", {}).get("features", []))
            summary["feature_count"] = feature_count
        
        layer_summaries.append(summary)
    
    if ctx:
        await ctx.info(f"当前有 {len(_current_layers)} 个图层待可视化")
    
    return {
        "success": True,
        "layer_count": len(_current_layers),
        "layers": layer_summaries,
        "message": f"当前有 {len(_current_layers)} 个图层待可视化"
    }


# 核心处理函数

async def _create_wms_layer(
    layer_info: Dict[str, Any], 
    title: str, 
    ctx: Context
) -> Dict[str, Any]:
    """创建WMS图层对象"""
    basic_info = layer_info["basic_info"]
    wms_params = layer_info["access_parameters"]["wms"]
    
    return {
        "name": basic_info["layer_name"],
        "title": title,
        "type": "wms",
        "service_type": basic_info["service_type"],
        "layer_info": basic_info,
        "wms_url": wms_params.get("base_url", ""),
        "wms_params": wms_params.get("params", {})
    }


async def _create_wfs_layer(
    layer_info: Dict[str, Any], 
    title: str, 
    max_features: int, 
    ctx: Context
) -> Dict[str, Any]:
    """创建WFS图层对象"""
    basic_info = layer_info["basic_info"]
    wfs_params = layer_info["access_parameters"]["wfs"]
    
    # 获取WFS数据
    geojson_data = await _fetch_wfs_data(layer_info, max_features, ctx)
    
    return {
        "name": basic_info["layer_name"],
        "title": title,
        "type": "wfs",
        "service_type": basic_info["service_type"],
        "layer_info": basic_info,
        "geojson_data": geojson_data,
        "stats": _calculate_geojson_stats(geojson_data),
        "style": _get_default_geojson_style()
    }


async def _fetch_wfs_data(
    layer_info: Dict[str, Any], 
    max_features: int, 
    ctx: Context
) -> Dict[str, Any]:
    """获取WFS数据"""
    basic_info = layer_info["basic_info"]
    wfs_params = layer_info["access_parameters"]["wfs"]
    
    # 构建请求参数
    params = {
        "service": "WFS",
        "version": wfs_params["version"],
        "request": "GetFeature",
        "typeNames": wfs_params["typeNames"],
        "maxFeatures": str(max_features),
        "outputFormat": "application/json"
    }
    
    if ctx:
        await ctx.info(f"正在获取WFS数据，最大要素数: {max_features}")
    
    # 发送请求
    parser = await get_ogc_parser()
    response = await parser.http_client.get(basic_info["service_url"], params=params)
    
    if response.status_code != 200:
        raise RuntimeError(f"WFS请求失败: {response.status_code}")
    
    geojson_data = response.json()
    
    # 记录获取结果
    feature_count = len(geojson_data.get("features", []))
    if ctx:
        await ctx.info(f"成功获取 {feature_count} 个要素")
    
    return geojson_data


async def _create_overlay_visualization(
    web_server, 
    layers: List[Dict[str, Any]], 
    title: str, 
    map_config: Dict[str, Any], 
    ctx: Context
) -> Dict[str, Any]:
    """创建叠加可视化"""
    visualization_url = await web_server.add_composite_visualization(
        title=title,
        layers=layers,
        map_config=map_config
    )
    
    layer_summaries = [_create_layer_summary(layer) for layer in layers]
    
    return {
        "success": True,
        "visualization_url": visualization_url,
        "title": title,
        "type": "overlay",
        "layer_count": len(layers),
        "layer_summaries": layer_summaries,
        "web_server_url": web_server._get_base_url(),
        "instructions": f"在浏览器中访问: {visualization_url}"
    }


async def _create_comparison_visualization(
    web_server, 
    layers: List[Dict[str, Any]], 
    title: str, 
    map_config: Dict[str, Any], 
    ctx: Context
) -> Dict[str, Any]:
    """创建对比可视化"""
    visualization_urls = []
    
    for layer in layers:
        layer_title = f"{title} - {layer['title']}"
        
        if layer["type"] == "wms":
            url = await web_server.add_wms_visualization(
                layer_name=layer_title,
                layer_info=layer["layer_info"],
                map_config=map_config
            )
        else:
            url = await web_server.add_geojson_visualization(
                layer_name=layer_title,
                layer_info=layer["layer_info"],
                geojson_data=layer["geojson_data"],
                stats=layer.get("stats", {}),
                map_config=map_config
            )
        
        visualization_urls.append({
            "layer_name": layer["name"],
            "layer_title": layer["title"],
            "url": url
        })
    
    layer_summaries = [_create_layer_summary(layer) for layer in layers]
    
    return {
        "success": True,
        "type": "comparison",
        "title": title,
        "visualization_urls": visualization_urls,
        "layer_summaries": layer_summaries,
        "web_server_url": web_server._get_base_url(),
        "instructions": "每个图层都有独立的可视化链接，可以分别查看对比"
    }


# 资源和工具函数

async def _get_layer_from_resource(layer_name: str, ctx: Context) -> Dict[str, Any]:
    """通过资源获取图层信息"""
    try:
        layer_resource = await ctx.read_resource(f"ogc://layer/{layer_name}")
        
        if not layer_resource or not layer_resource[0].content:
            raise ValueError(f"未找到图层资源: {layer_name}")
        
        layer_data = layer_resource[0].content
        
        # 解析JSON数据
        if isinstance(layer_data, str):
            layer_data = json.loads(layer_data)
        
        # 检查错误信息
        if isinstance(layer_data, dict) and "error" in layer_data:
            raise ValueError(f"图层资源错误: {layer_data['error']}")
        
        return layer_data
        
    except json.JSONDecodeError as e:
        raise ValueError(f"图层资源JSON解析失败: {e}")
    except Exception as e:
        raise ValueError(f"获取图层资源失败: {e}")


def _create_layer_summary(layer: Dict[str, Any]) -> Dict[str, Any]:
    """创建图层摘要信息"""
    summary = {
        "name": layer["name"],
        "title": layer["title"],
        "type": layer["type"],
        "service_type": layer.get("service_type", "unknown")
    }
    
    if layer["type"] == "wfs":
        feature_count = len(layer.get("geojson_data", {}).get("features", []))
        summary["feature_count"] = feature_count
        summary["geometry_types"] = layer.get("stats", {}).get("geometry_types", [])
    
    return summary


def _configure_map_settings(layers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """配置地图设置"""
    return {
        "center": [39.9042, 116.4074],  # 默认北京
        "zoom": 10,
        "width": 1200,
        "height": 800
    }


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
        "fillOpacity": 0.2
    }