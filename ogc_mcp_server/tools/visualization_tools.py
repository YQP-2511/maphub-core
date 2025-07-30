"""多图层可视化工具模块

基于FastMCP最佳实践设计的多图层可视化工具
充分利用layer_registry资源提供的增强信息，避免重复处理
支持动态边界框、要素模式等高级功能

工具设计：
- add_wms_layer: 添加WMS图层到可视化
- add_wfs_layer: 添加WFS图层到可视化（支持属性过滤）
- add_wmts_layer: 添加WMTS图层到可视化（支持瓦片矩阵集选择）
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
from ..services.ogc_parser import get_ogc_parser

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
        
        # 获取图层信息（利用layer_registry资源）
        layer_info = await _get_layer_from_resource(layer_name, ctx)
        
        # 验证图层支持WMS
        if not layer_info["access_parameters"].get("wms"):
            raise ValueError(f"图层 {layer_name} 不支持WMS服务")
        
        # 创建WMS图层对象（利用资源中的增强信息）
        wms_layer = _create_wms_layer_from_resource(layer_info, layer_title or layer_name)
        
        # 添加到图层列表
        _current_layers.append(wms_layer)
        
        if ctx:
            await ctx.info(f"✅ WMS图层 {layer_name} 添加成功，当前共 {len(_current_layers)} 个图层")
        
        return {
            "success": True,
            "layer_added": {
                "name": layer_name,
                "title": wms_layer["title"],
                "type": "wms",
                "has_dynamic_bbox": bool(wms_layer.get("dynamic_bbox")),
                "bbox_source": wms_layer.get("bbox_source", "static")
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
    use_enhanced_data: Annotated[bool, Field(description="是否使用增强的要素模式信息")] = True,
    property_filters: Annotated[Optional[List[Dict[str, Any]]], Field(description="属性过滤条件列表，格式：[{'property': 'name', 'value': 'value', 'operator': '='}]")] = None,
    cql_filter: Annotated[Optional[str], Field(description="自定义CQL过滤器字符串（优先级高于property_filters）")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """添加WFS图层到可视化列表
    
    专门用于添加WFS（要素数据）图层，适合：
    - 矢量数据可视化
    - 属性数据展示
    - 交互式要素查询
    
    支持属性过滤功能：
    - property_filters: 简单属性过滤条件列表
    - cql_filter: 自定义CQL过滤器字符串
    
    Args:
        layer_name: WFS图层名称
        layer_title: 图层显示标题（可选，默认使用图层名称）
        max_features: 最大要素数量（默认100，避免数据过载）
        use_enhanced_data: 是否使用增强的要素模式信息
        property_filters: 属性过滤条件列表
        cql_filter: 自定义CQL过滤器字符串
        ctx: MCP上下文对象
        
    Returns:
        添加结果和当前图层列表状态
    """
    try:
        if ctx:
            await ctx.info(f"正在添加WFS图层: {layer_name}，最大要素数: {max_features}")
        
        # 获取图层信息（利用layer_registry资源）
        layer_info = await _get_layer_from_resource(layer_name, ctx)
        
        # 验证图层支持WFS
        if not layer_info["access_parameters"].get("wfs"):
            raise ValueError(f"图层 {layer_name} 不支持WFS服务")
        
        # 构建过滤器
        filter_info = await _build_wfs_filters(
            layer_info, property_filters, cql_filter, ctx
        )
        
        # 创建WFS图层对象（利用资源中的增强信息）
        wfs_layer = await _create_wfs_layer_from_resource(
            layer_info, 
            layer_title or layer_name, 
            max_features, 
            use_enhanced_data,
            filter_info,
            ctx
        )
        
        # 添加到图层列表
        _current_layers.append(wfs_layer)
        
        feature_count = len(wfs_layer.get("geojson_data", {}).get("features", []))
        if ctx:
            filter_msg = f"，应用了过滤器" if filter_info.get("cql_filter") else ""
            await ctx.info(f"✅ WFS图层 {layer_name} 添加成功，包含 {feature_count} 个要素{filter_msg}，当前共 {len(_current_layers)} 个图层")
        
        return {
            "success": True,
            "layer_added": {
                "name": layer_name,
                "title": wfs_layer["title"],
                "type": "wfs",
                "feature_count": feature_count,
                "has_feature_schema": bool(wfs_layer.get("feature_schema")),
                "has_dynamic_bbox": bool(wfs_layer.get("dynamic_bbox")),
                "geometry_types": wfs_layer.get("stats", {}).get("geometry_types", []),
                "filter_applied": bool(filter_info.get("cql_filter")),
                "filter_summary": filter_info.get("summary", {})
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
    auto_fit_bounds: Annotated[bool, Field(description="是否自动适配边界框")] = True,
    ctx: Context = None
) -> Dict[str, Any]:
    """创建多图层复合可视化
    
    将当前添加的所有图层组合成一个可视化页面
    支持叠加显示和对比显示两种模式
    自动利用动态边界框信息优化地图显示
    
    Args:
        title: 可视化标题
        visualization_type: 可视化类型（overlay叠加 或 comparison对比）
        auto_fit_bounds: 是否自动适配边界框
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
        
        # 配置地图设置（利用动态边界框信息）
        map_config = _configure_enhanced_map_settings(_current_layers, auto_fit_bounds)
        
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
    
    显示当前图层列表的状态，包括图层类型和增强信息
    
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
        summary = _create_enhanced_layer_summary(layer)
        layer_summaries.append(summary)
    
    if ctx:
        await ctx.info(f"当前有 {len(_current_layers)} 个图层待可视化")
    
    return {
        "success": True,
        "layer_count": len(_current_layers),
        "layers": layer_summaries,
        "enhanced_features": {
            "dynamic_bbox_count": sum(1 for layer in _current_layers if layer.get("dynamic_bbox")),
            "feature_schema_count": sum(1 for layer in _current_layers if layer.get("feature_schema")),
            "total_features": sum(len(layer.get("geojson_data", {}).get("features", [])) for layer in _current_layers if layer.get("type") == "wfs")
        },
        "message": f"当前有 {len(_current_layers)} 个图层待可视化"
    }


# 核心处理函数 - 优化版本，充分利用资源信息

async def _build_wfs_filters(
    layer_info: Dict[str, Any],
    property_filters: Optional[List[Dict[str, Any]]],
    cql_filter: Optional[str],
    ctx: Context
) -> Dict[str, Any]:
    """构建WFS过滤器信息
    
    Args:
        layer_info: 图层信息
        property_filters: 属性过滤条件列表
        cql_filter: 自定义CQL过滤器
        ctx: MCP上下文对象
        
    Returns:
        过滤器信息字典
    """
    filter_info = {
        "cql_filter": None,
        "summary": {},
        "applied_filters": []
    }
    
    # 如果提供了自定义CQL过滤器，优先使用
    if cql_filter:
        filter_info["cql_filter"] = cql_filter
        filter_info["summary"] = {"type": "custom_cql", "filter": cql_filter}
        filter_info["applied_filters"] = ["custom_cql"]
        
        if ctx:
            await ctx.info(f"使用自定义CQL过滤器: {cql_filter}")
        
        return filter_info
    
    # 如果提供了属性过滤条件，构建CQL过滤器
    if property_filters:
        try:
            parser = await get_ogc_parser()
            builder = parser.create_filter_builder()
            
            for filter_condition in property_filters:
                property_name = filter_condition.get("property")
                value = filter_condition.get("value")
                operator = filter_condition.get("operator", "=")
                
                # 映射操作符
                operator_map = {
                    "=": "PropertyIsEqualTo",
                    "!=": "PropertyIsNotEqualTo",
                    ">": "PropertyIsGreaterThan",
                    ">=": "PropertyIsGreaterThanOrEqualTo",
                    "<": "PropertyIsLessThan",
                    "<=": "PropertyIsLessThanOrEqualTo",
                    "LIKE": "PropertyIsLike"
                }
                
                ogc_operator = operator_map.get(operator, "PropertyIsEqualTo")
                
                if operator == "LIKE":
                    builder.add_like_filter(property_name, value)
                else:
                    builder.add_property_filter(property_name, value, ogc_operator)
                
                filter_info["applied_filters"].append({
                    "property": property_name,
                    "value": value,
                    "operator": operator
                })
            
            # 构建CQL过滤器
            cql_filter = builder.build_cql_filter()
            if cql_filter:
                filter_info["cql_filter"] = cql_filter
                filter_info["summary"] = builder.get_filter_summary()
                
                if ctx:
                    await ctx.info(f"构建属性过滤器: {cql_filter}")
            
        except Exception as e:
            logger.warning(f"构建属性过滤器失败: {e}")
            if ctx:
                await ctx.warning(f"构建属性过滤器失败，将不使用过滤器: {e}")
    
    return filter_info


def _create_wms_layer_from_resource(
    layer_info: Dict[str, Any], 
    title: str
) -> Dict[str, Any]:
    """从资源信息创建WMS图层对象
    
    充分利用layer_registry提供的增强信息
    """
    basic_info = layer_info["basic_info"]
    wms_params = layer_info["access_parameters"]["wms"]
    enhanced_details = layer_info.get("enhanced_details", {})
    capabilities = layer_info.get("capabilities", {})
    
    # 构建增强的WMS图层对象
    wms_layer = {
        "name": basic_info["layer_name"],
        "title": title,
        "type": "wms",
        "service_type": basic_info["service_type"],
        "layer_info": basic_info,
        "wms_url": basic_info["service_url"],
        "wms_params": wms_params,
        # 增强信息
        "bbox": capabilities.get("bbox"),
        "dynamic_bbox": enhanced_details.get("dynamic_bbox"),
        "bbox_source": "dynamic" if enhanced_details.get("dynamic_bbox") else "static",
        "crs_list": capabilities.get("crs_list", ["EPSG:4326"]),
        "styles": enhanced_details.get("styles_detailed", []),
        "wms_specific": enhanced_details.get("wms_specific", {})
    }
    
    return wms_layer


async def _create_wfs_layer_from_resource(
    layer_info: Dict[str, Any], 
    title: str, 
    max_features: int,
    use_enhanced_data: bool,
    filter_info: Dict[str, Any],
    ctx: Context
) -> Dict[str, Any]:
    """从资源信息创建WFS图层对象
    
    充分利用layer_registry提供的增强信息，避免重复请求
    """
    basic_info = layer_info["basic_info"]
    wfs_params = layer_info["access_parameters"]["wfs"]
    enhanced_details = layer_info.get("enhanced_details", {})
    capabilities = layer_info.get("capabilities", {})
    
    # 获取WFS数据（仍需要实际数据用于可视化）
    geojson_data = await _fetch_optimized_wfs_data(layer_info, max_features, filter_info, ctx)
    
    # 构建增强的WFS图层对象
    wfs_layer = {
        "name": basic_info["layer_name"],
        "title": title,
        "type": "wfs",
        "service_type": basic_info["service_type"],
        "layer_info": basic_info,
        "geojson_data": geojson_data,
        "stats": _calculate_enhanced_geojson_stats(geojson_data, capabilities),
        "style": _get_enhanced_geojson_style(enhanced_details),
        # 增强信息
        "bbox": capabilities.get("bbox"),
        "dynamic_bbox": enhanced_details.get("dynamic_bbox"),
        "bbox_source": "dynamic" if enhanced_details.get("dynamic_bbox") else "static",
        "feature_schema": enhanced_details.get("feature_schema") if use_enhanced_data else None,
        "attributes": capabilities.get("attributes", []),
        "geometry_type": capabilities.get("geometry_type"),
        "crs_list": capabilities.get("crs_list", ["EPSG:4326"]),
        # 过滤器信息
        "filter_info": filter_info
    }
    
    return wfs_layer


async def _fetch_optimized_wfs_data(
    layer_info: Dict[str, Any], 
    max_features: int,
    filter_info: Dict[str, Any],
    ctx: Context
) -> Dict[str, Any]:
    """优化的WFS数据获取 - 修复URL使用错误
    
    利用资源中的边界框信息和过滤器优化请求
    """
    basic_info = layer_info["basic_info"]
    wfs_params = layer_info["access_parameters"]["wfs"]
    enhanced_details = layer_info.get("enhanced_details", {})
    
    # 修复：使用正确的WFS服务URL
    wfs_service_url = wfs_params.get("service_url") or basic_info.get("wfs_service_url")
    if not wfs_service_url:
        # 如果没有专门的WFS URL，从基础URL构建
        base_url = basic_info["service_url"]
        if "gwc/service/wmts" in base_url:
            # 如果是WMTS URL，替换为WFS URL
            wfs_service_url = base_url.replace("gwc/service/wmts", "ows")
        elif "ows" not in base_url:
            # 确保使用OWS端点
            wfs_service_url = base_url.rstrip('/') + '/ows'
        else:
            wfs_service_url = base_url
    
    # 构建优化的请求参数
    params = {
        "service": "WFS",
        "version": wfs_params["version"],
        "request": "GetFeature",
        "typeNames": wfs_params["typeNames"],
        "maxFeatures": str(max_features),
        "outputFormat": "application/json"
    }
    
    # 添加CQL过滤器
    cql_filter = filter_info.get("cql_filter")
    if cql_filter:
        params["CQL_FILTER"] = cql_filter
        if ctx:
            await ctx.info(f"应用CQL过滤器: {cql_filter}")
    
    # 如果有动态边界框，使用它来限制查询范围
    dynamic_bbox = enhanced_details.get("dynamic_bbox")
    if dynamic_bbox and dynamic_bbox.get("bbox"):
        bbox_str = ",".join(map(str, dynamic_bbox["bbox"]))
        params["bbox"] = bbox_str
        if ctx:
            await ctx.info(f"使用动态边界框优化WFS查询: {bbox_str}")
    
    if ctx:
        await ctx.info(f"正在获取WFS数据，服务URL: {wfs_service_url}")
        await ctx.info(f"请求参数: {params}")
    
    # 发送请求 - 使用正确的WFS URL
    parser = await get_ogc_parser()
    response = await parser.url_utils.http_client.get(wfs_service_url, params=params)
    
    if response.status_code != 200:
        error_msg = f"WFS请求失败: {response.status_code}"
        if ctx:
            await ctx.error(f"{error_msg}, URL: {wfs_service_url}")
            await ctx.error(f"响应内容: {response.text[:500]}")
        raise RuntimeError(error_msg)
    
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
    
    layer_summaries = [_create_enhanced_layer_summary(layer) for layer in layers]
    
    return {
        "success": True,
        "visualization_url": visualization_url,
        "title": title,
        "type": "overlay",
        "layer_count": len(layers),
        "layer_summaries": layer_summaries,
        "map_config": map_config,
        "enhanced_features": _get_visualization_enhanced_features(layers),
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
            "url": url,
            "enhanced_info": {
                "has_dynamic_bbox": bool(layer.get("dynamic_bbox")),
                "has_feature_schema": bool(layer.get("feature_schema")),
                "bbox_source": layer.get("bbox_source", "static")
            }
        })
    
    layer_summaries = [_create_enhanced_layer_summary(layer) for layer in layers]
    
    return {
        "success": True,
        "type": "comparison",
        "title": title,
        "visualization_urls": visualization_urls,
        "layer_summaries": layer_summaries,
        "map_config": map_config,
        "enhanced_features": _get_visualization_enhanced_features(layers),
        "web_server_url": web_server._get_base_url(),
        "instructions": "每个图层都有独立的可视化链接，可以分别查看对比"
    }


# 资源和工具函数

async def _get_layer_from_resource(layer_name: str, ctx: Context) -> Dict[str, Any]:
    """通过资源获取图层信息
    
    这是与layer_registry的核心连接点
    """
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


def _create_enhanced_layer_summary(layer: Dict[str, Any]) -> Dict[str, Any]:
    """创建增强的图层摘要信息"""
    summary = {
        "name": layer["name"],
        "title": layer["title"],
        "type": layer["type"],
        "service_type": layer.get("service_type", "unknown"),
        "bbox_source": layer.get("bbox_source", "static"),
        "has_dynamic_bbox": bool(layer.get("dynamic_bbox")),
        "has_feature_schema": bool(layer.get("feature_schema"))
    }
    
    if layer["type"] == "wfs":
        feature_count = len(layer.get("geojson_data", {}).get("features", []))
        summary.update({
            "feature_count": feature_count,
            "geometry_types": layer.get("stats", {}).get("geometry_types", []),
            "geometry_type": layer.get("geometry_type"),
            "attribute_count": len(layer.get("attributes", []))
        })
    elif layer["type"] == "wms":
        summary.update({
            "styles_count": len(layer.get("styles", [])),
            "crs_count": len(layer.get("crs_list", []))
        })
    elif layer["type"] == "wmts":
        summary.update({
            "tile_matrix_set": layer.get("tile_matrix_set"),
            "style": layer.get("style"),
            "format": layer.get("format"),
            "zoom_level": layer.get("zoom_level"),
            "matrix_sets_count": len(layer.get("available_matrix_sets", [])),
            "styles_count": len(layer.get("available_styles", [])),
            "formats_count": len(layer.get("available_formats", [])),
            "has_dimensions": bool(layer.get("dimensions"))
        })
    
    return summary


def _configure_enhanced_map_settings(layers: List[Dict[str, Any]], auto_fit_bounds: bool = True) -> Dict[str, Any]:
    """配置增强的地图设置
    
    利用动态边界框信息自动优化地图显示
    """
    map_config = {
        "width": 1200,
        "height": 800,
        "zoom": 10,
        "center": [39.9042, 116.4074]  # 默认北京
    }
    
    if auto_fit_bounds and layers:
        # 尝试从动态边界框计算最佳视图
        dynamic_bboxes = []
        static_bboxes = []
        
        for layer in layers:
            dynamic_bbox = layer.get("dynamic_bbox")
            if dynamic_bbox and dynamic_bbox.get("bbox"):
                dynamic_bboxes.append(dynamic_bbox["bbox"])
            elif layer.get("bbox") and layer["bbox"].get("wgs84"):
                static_bboxes.append(layer["bbox"]["wgs84"])
        
        # 优先使用动态边界框
        bboxes_to_use = dynamic_bboxes if dynamic_bboxes else static_bboxes
        
        if bboxes_to_use:
            # 计算合并边界框
            combined_bbox = _calculate_combined_bbox(bboxes_to_use)
            if combined_bbox:
                center_lon = (combined_bbox[0] + combined_bbox[2]) / 2
                center_lat = (combined_bbox[1] + combined_bbox[3]) / 2
                map_config["center"] = [center_lat, center_lon]
                
                # 根据边界框大小调整缩放级别
                bbox_width = abs(combined_bbox[2] - combined_bbox[0])
                bbox_height = abs(combined_bbox[3] - combined_bbox[1])
                max_extent = max(bbox_width, bbox_height)
                
                if max_extent > 10:
                    map_config["zoom"] = 6
                elif max_extent > 1:
                    map_config["zoom"] = 8
                elif max_extent > 0.1:
                    map_config["zoom"] = 10
                else:
                    map_config["zoom"] = 12
    
    return map_config


def _calculate_combined_bbox(bboxes: List[List[float]]) -> Optional[List[float]]:
    """计算多个边界框的合并边界框"""
    if not bboxes:
        return None
    
    min_x = min(bbox[0] for bbox in bboxes)
    min_y = min(bbox[1] for bbox in bboxes)
    max_x = max(bbox[2] for bbox in bboxes)
    max_y = max(bbox[3] for bbox in bboxes)
    
    return [min_x, min_y, max_x, max_y]


def _calculate_enhanced_geojson_stats(geojson_data: Dict[str, Any], capabilities: Dict[str, Any]) -> Dict[str, Any]:
    """计算增强的GeoJSON统计信息"""
    features = geojson_data.get("features", [])
    
    stats = {
        "feature_count": len(features),
        "geometry_types": list(set(
            feature.get("geometry", {}).get("type", "Unknown") 
            for feature in features
        ))
    }
    
    # 添加属性统计
    if features and capabilities.get("attributes"):
        attribute_stats = {}
        for attr in capabilities["attributes"]:
            attr_name = attr.get("name")
            if attr_name:
                values = [
                    feature.get("properties", {}).get(attr_name) 
                    for feature in features 
                    if feature.get("properties", {}).get(attr_name) is not None
                ]
                attribute_stats[attr_name] = {
                    "count": len(values),
                    "type": attr.get("type", "unknown")
                }
        stats["attribute_stats"] = attribute_stats
    
    return stats


def _get_enhanced_geojson_style(enhanced_details: Dict[str, Any]) -> Dict[str, Any]:
    """获取增强的GeoJSON样式"""
    base_style = {
        "color": "#3388ff",
        "weight": 2,
        "opacity": 0.8,
        "fillColor": "#3388ff",
        "fillOpacity": 0.2
    }
    
    # 如果有详细样式信息，可以在这里进行增强
    styles_detailed = enhanced_details.get("styles_detailed", [])
    if styles_detailed:
        # 可以根据样式信息调整默认样式
        pass
    
    return base_style


def _get_visualization_enhanced_features(layers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """获取可视化的增强功能统计"""
    return {
        "total_layers": len(layers),
        "wms_layers": len([l for l in layers if l.get("type") == "wms"]),
        "wfs_layers": len([l for l in layers if l.get("type") == "wfs"]),
        "wmts_layers": len([l for l in layers if l.get("type") == "wmts"]),
        "dynamic_bbox_layers": len([l for l in layers if l.get("dynamic_bbox")]),
        "feature_schema_layers": len([l for l in layers if l.get("feature_schema")]),
        "total_features": sum(
            len(l.get("geojson_data", {}).get("features", [])) 
            for l in layers if l.get("type") == "wfs"
        ),
        "unique_geometry_types": list(set(
            geom_type
            for layer in layers if layer.get("type") == "wfs"
            for geom_type in layer.get("stats", {}).get("geometry_types", [])
        )),
        "unique_tile_matrix_sets": list(set(
            layer.get("tile_matrix_set")
            for layer in layers if layer.get("type") == "wmts" and layer.get("tile_matrix_set")
        ))
    }


@visualization_server.tool
async def add_wmts_layer(
    layer_name: Annotated[str, Field(description="WMTS图层名称")],
    layer_title: Annotated[str, Field(description="图层显示标题")] = None,
    tile_matrix_set: Annotated[str, Field(description="瓦片矩阵集标识符")] = None,
    style: Annotated[str, Field(description="样式标识符")] = None,
    format: Annotated[str, Field(description="图像格式")] = None,
    zoom_level: Annotated[int, Field(description="初始缩放级别")] = 10,
    ctx: Context = None
) -> Dict[str, Any]:
    """添加WMTS图层到可视化列表
    
    专门用于添加WMTS（瓦片地图）图层，适合：
    - 高性能瓦片底图
    - 预渲染的地图数据
    - 多尺度地图可视化
    - 缓存优化的地图服务
    
    Args:
        layer_name: WMTS图层名称
        layer_title: 图层显示标题（可选，默认使用图层名称）
        tile_matrix_set: 瓦片矩阵集标识符（可选，自动选择最佳）
        style: 样式标识符（可选，使用默认样式）
        format: 图像格式（可选，使用默认格式）
        zoom_level: 初始缩放级别（默认10）
        ctx: MCP上下文对象
        
    Returns:
        添加结果和当前图层列表状态
    """
    try:
        if ctx:
            await ctx.info(f"正在添加WMTS图层: {layer_name}")
        
        # 获取图层信息（利用layer_registry资源）
        layer_info = await _get_layer_from_resource(layer_name, ctx)
        
        # 验证图层支持WMTS
        if not layer_info["access_parameters"].get("wmts"):
            raise ValueError(f"图层 {layer_name} 不支持WMTS服务")
        
        # 创建WMTS图层对象（利用资源中的增强信息）
        wmts_layer = _create_wmts_layer_from_resource(
            layer_info, 
            layer_title or layer_name,
            tile_matrix_set,
            style,
            format,
            zoom_level
        )
        
        # 添加到图层列表
        _current_layers.append(wmts_layer)
        
        if ctx:
            await ctx.info(f"✅ WMTS图层 {layer_name} 添加成功，当前共 {len(_current_layers)} 个图层")
        
        return {
            "success": True,
            "layer_added": {
                "name": layer_name,
                "title": wmts_layer["title"],
                "type": "wmts",
                "tile_matrix_set": wmts_layer.get("tile_matrix_set"),
                "style": wmts_layer.get("style"),
                "format": wmts_layer.get("format"),
                "zoom_level": wmts_layer.get("zoom_level"),
                "has_dynamic_bbox": bool(wmts_layer.get("dynamic_bbox")),
                "bbox_source": wmts_layer.get("bbox_source", "static"),
                "available_matrix_sets": len(wmts_layer.get("available_matrix_sets", [])),
                "available_styles": len(wmts_layer.get("available_styles", [])),
                "available_formats": len(wmts_layer.get("available_formats", []))
            },
            "current_layer_count": len(_current_layers),
            "message": f"WMTS图层 {layer_name} 已添加到可视化列表"
        }
        
    except Exception as e:
        error_msg = f"添加WMTS图层失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


def _create_wmts_layer_from_resource(
    layer_info: Dict[str, Any], 
    title: str,
    tile_matrix_set: Optional[str] = None,
    style: Optional[str] = None,
    format: Optional[str] = None,
    zoom_level: int = 10
) -> Dict[str, Any]:
    """从资源信息创建WMTS图层对象
    
    充分利用layer_registry提供的WMTS增强信息
    
    Args:
        layer_info: 图层信息
        title: 图层标题
        tile_matrix_set: 指定的瓦片矩阵集
        style: 指定的样式
        format: 指定的格式
        zoom_level: 缩放级别
        
    Returns:
        WMTS图层对象
    """
    basic_info = layer_info["basic_info"]
    wmts_params = layer_info["access_parameters"]["wmts"]
    detailed_capabilities = layer_info.get("detailed_capabilities", {}).get("wmts", {})
    capabilities = layer_info.get("capabilities", {})
    
    # 获取可用的瓦片矩阵集、样式和格式
    available_matrix_sets = wmts_params.get("tile_matrix_sets", [])
    available_styles = wmts_params.get("styles", [])
    available_formats = wmts_params.get("formats", ["image/png"])
    
    # 智能选择瓦片矩阵集
    selected_matrix_set = tile_matrix_set
    if not selected_matrix_set:
        selected_matrix_set = wmts_params.get("tilematrixset", "")
        if not selected_matrix_set and available_matrix_sets:
            # 优先选择常见的瓦片矩阵集
            for preferred in ["GoogleMapsCompatible", "EPSG:3857", "EPSG:4326"]:
                if preferred in available_matrix_sets:
                    selected_matrix_set = preferred
                    break
            if not selected_matrix_set:
                selected_matrix_set = available_matrix_sets[0]
    
    # 智能选择样式
    selected_style = style
    if not selected_style:
        selected_style = wmts_params.get("default_style", "")
        if not selected_style and available_styles:
            selected_style = available_styles[0]
    
    # 智能选择格式
    selected_format = format
    if not selected_format:
        selected_format = wmts_params.get("default_format", "image/png")
        if selected_format not in available_formats and available_formats:
            selected_format = available_formats[0]
    
    # 构建增强的WMTS图层对象
    wmts_layer = {
        "name": basic_info["layer_name"],
        "title": title,
        "type": "wmts",
        "service_type": basic_info["service_type"],
        "layer_info": basic_info,
        "wmts_url": basic_info["service_url"],
        "wmts_params": wmts_params,
        # WMTS特有参数
        "tile_matrix_set": selected_matrix_set,
        "style": selected_style,
        "format": selected_format,
        "zoom_level": zoom_level,
        # 可用选项
        "available_matrix_sets": available_matrix_sets,
        "available_styles": available_styles,
        "available_formats": available_formats,
        # 增强信息
        "bbox": capabilities.get("bbox"),
        "dynamic_bbox": detailed_capabilities.get("dynamic_bbox"),
        "bbox_source": "dynamic" if detailed_capabilities.get("dynamic_bbox") else "static",
        "crs_list": capabilities.get("crs_list", ["EPSG:4326"]),
        "dimensions": wmts_params.get("dimensions", {}),
        "resource_urls": wmts_params.get("resource_urls", {}),
        "wmts_specific": detailed_capabilities.get("wmts_specific", {})
    }
    
    return wmts_layer