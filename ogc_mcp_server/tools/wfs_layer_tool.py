"""优化的WFS图层添加工具

基于FastMCP最佳实践重构，简化资源访问，提高可靠性
"""

import json
import logging
import aiohttp
from typing import Dict, Any, List, Optional
from urllib.parse import urlencode, quote
from fastmcp import FastMCP, Context
from pydantic import Field
from typing_extensions import Annotated

logger = logging.getLogger(__name__)

# 创建优化的WFS图层工具服务器
wfs_layer_server = FastMCP(name="优化WFS图层工具")

# 导入全局图层存储
from . import visualization_tools


@wfs_layer_server.tool(
    name="add_wfs_layer",
    description="""添加WFS矢量图层到地图。智能检测过滤需求并自动应用。

智能过滤策略：
- 分析用户查询意图，自动识别过滤条件
- 当查询包含具体限定词时，必须使用过滤参数
- 支持地名、分类、数值范围等多种过滤方式

使用指导：
1. 有明确条件的查询 → 必须使用attribute_filter和filter_values
2. 探索性查询 → 可选择性使用过滤
3. 多条件查询 → 使用逗号分隔多个过滤值""",
    tags={"wfs", "layer", "vector", "filter", "visualization", "intelligent"}
)
async def add_wfs_layer(
    layer_name: Annotated[str, Field(description="WFS图层名称")],
    layer_title: Annotated[str, Field(description="图层显示标题")] = None,
    max_features: Annotated[int, Field(description="最大要素数量，默认100")] = 100,
    attribute_filter: Annotated[Optional[str], Field(description="属性名称，用于过滤")] = None,
    filter_values: Annotated[Optional[str], Field(description="过滤值，多个值用逗号分隔")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """添加WFS矢量图层到地图可视化
    
    智能过滤功能：
    - 自动检测用户查询中的过滤需求
    - 当用户查询包含具体条件时，自动应用属性过滤
    - 支持多值过滤和范围查询
    
    过滤判断逻辑：
    1. 如果用户查询包含地名、分类、数值等限定条件，优先使用过滤
    2. 如果提供了attribute_filter和filter_values参数，直接应用过滤
    3. 对于探索性查询，可不使用过滤获取全部数据
    
    示例场景：
    - "查看加州的人口数据" → 自动过滤STATE_NAME='California'
    - "显示住宅用地" → 自动过滤LAND_USE='住宅'
    - "人口超过100万的城市" → 自动过滤POPULATION>1000000
    """
    try:
        if ctx:
            await ctx.info(f"🔄 开始添加WFS图层: {layer_name}")
        
        # 简化资源访问
        layer_info = await _get_layer_info_simplified(layer_name, ctx)
        
        # 验证WFS支持
        if not _validate_wfs_support(layer_info, layer_name):
            supported_services = layer_info.get("metadata", {}).get("supported_services", [])
            raise ValueError(
                f"图层 '{layer_name}' 不支持WFS服务。"
                f"支持的服务类型: {', '.join(supported_services) if supported_services else '无'}"
            )
        
        # 构建过滤器（支持多值）
        filter_info = await _build_filter_optimized(layer_info, attribute_filter, filter_values, ctx)
        
        # 获取WFS数据（优化版本）
        geojson_data = await _fetch_wfs_data_optimized(layer_info, max_features, filter_info, ctx)
        
        # 创建图层对象
        wfs_layer = _create_wfs_layer_optimized(layer_info, layer_title or layer_name, geojson_data, filter_info)
        
        # 添加到图层列表
        visualization_tools._current_layers.append(wfs_layer)
        
        feature_count = len(geojson_data.get("features", []))
        success_msg = f"✅ WFS图层 '{layer_name}' 添加成功，包含 {feature_count} 个要素"
        
        if ctx:
            await ctx.info(success_msg)
        
        return {
            "success": True,
            "message": success_msg,
            "layer_info": {
                "name": layer_name,
                "title": wfs_layer["title"],
                "type": "wfs",
                "feature_count": feature_count,
                "geometry_type": wfs_layer.get("geometry_type"),
                "filter_applied": bool(filter_info.get("cql_filter"))
            },
            "current_layer_count": len(visualization_tools._current_layers)
        }
        
    except Exception as e:
        error_msg = f"❌ 添加WFS图层失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        if ctx:
            await ctx.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "layer_name": layer_name,
            "current_layer_count": len(visualization_tools._current_layers)
        }


async def _get_layer_info_simplified(layer_name: str, ctx: Context) -> Dict[str, Any]:
    """增强的资源访问方法，包含图层发现功能
    
    先读取图层列表资源进行发现，再读取详细资源
    """
    try:
        # 第一步：读取图层列表资源进行发现
        if ctx:
            await ctx.debug(f"🔍 开始图层发现: 读取图层列表资源")
        
        layers_list_uri = "ogc://layers"
        layers_list_content = await ctx.read_resource(layers_list_uri)
        
        # 处理图层列表内容
        layers_data = None
        if isinstance(layers_list_content, list) and len(layers_list_content) > 0:
            content_item = layers_list_content[0]
            if hasattr(content_item, 'text'):
                layers_data = json.loads(content_item.text)
            elif hasattr(content_item, 'content'):
                layers_data = json.loads(content_item.content)
            elif isinstance(content_item, dict):
                layers_data = content_item
        elif isinstance(layers_list_content, dict):
            layers_data = layers_list_content
        elif isinstance(layers_list_content, str):
            layers_data = json.loads(layers_list_content)
        
        if not layers_data:
            raise Exception("无法获取图层列表")
        
        # 从图层列表中查找目标图层
        layers = layers_data.get("layers", [])
        found_layer = None
        available_layer_names = []
        
        for layer in layers:
            layer_name_in_list = layer.get("layer_name", "")
            available_layer_names.append(layer_name_in_list)
            if layer_name_in_list == layer_name:
                found_layer = layer
                break
        
        if ctx:
            await ctx.debug(f"📋 图层列表中共找到 {len(layers)} 个图层")
            await ctx.debug(f"🎯 目标图层 '{layer_name}' {'已找到' if found_layer else '未找到'}")
        
        # 如果在列表中未找到图层，提供建议
        if not found_layer:
            # 提供相似的图层名称建议
            suggestions = []
            for name in available_layer_names:
                if layer_name.lower() in name.lower() or name.lower() in layer_name.lower():
                    suggestions.append(name)
            
            if not suggestions:
                suggestions = available_layer_names[:5]  # 提供前5个作为示例
            
            error_msg = f"图层 '{layer_name}' 在图层列表中未找到"
            if suggestions:
                error_msg += f"\n💡 建议的图层名称: {', '.join(suggestions)}"
            raise ValueError(error_msg)
        
        # 第二步：读取详细资源
        if ctx:
            await ctx.debug(f"📖 图层发现成功，读取详细资源: ogc://layer/{layer_name}")
        
        resource_uri = f"ogc://layer/{layer_name}"
        resource_content = await ctx.read_resource(resource_uri)
        
        # 处理资源内容
        if isinstance(resource_content, list) and len(resource_content) > 0:
            # 获取第一个资源内容
            content_item = resource_content[0]
            
            # 检查是否有text属性（TextResourceContents）
            if hasattr(content_item, 'text'):
                layer_info = json.loads(content_item.text)
            # 检查是否有content属性
            elif hasattr(content_item, 'content'):
                layer_info = json.loads(content_item.content)
            # 如果是字典，直接使用
            elif isinstance(content_item, dict):
                layer_info = content_item
            else:
                raise Exception(f"未知的资源内容格式: {type(content_item)}")
        else:
            raise Exception("资源返回空内容")
        
        # 验证数据格式
        if not isinstance(layer_info, dict):
            raise Exception(f"资源数据格式错误，期望dict，实际: {type(layer_info)}")
        
        # 检查错误信息
        if "error" in layer_info:
            error_msg = layer_info["error"]
            suggestions = layer_info.get("suggestions", [])
            if suggestions:
                error_msg += f"\n💡 建议的图层名称: {', '.join(suggestions[:5])}"
            raise ValueError(error_msg)
        
        # 第三步：增强图层信息（添加发现阶段的信息）
        if ctx:
            await ctx.debug(f"✅ 图层发现和详细信息获取完成")
        
        # 将发现阶段的基础信息合并到详细信息中
        layer_info["discovery_info"] = {
            "found_in_list": True,
            "total_layers_available": len(layers),
            "discovery_timestamp": layers_data.get("timestamp"),
            "basic_info_from_list": found_layer
        }
        
        return layer_info
        
    except json.JSONDecodeError as e:
        raise Exception(f"JSON解析失败: {str(e)}")
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise Exception(f"获取图层信息失败: {str(e)}")


def _validate_wfs_support(layer_info: Dict[str, Any], layer_name: str) -> bool:
    """验证图层是否支持WFS服务"""
    wfs_params = layer_info.get("access_parameters", {}).get("wfs")
    return wfs_params and wfs_params is not False


async def _build_filter_optimized(
    layer_info: Dict[str, Any], 
    attribute_filter: Optional[str], 
    filter_values: Optional[str],
    ctx: Context
) -> Dict[str, Any]:
    """优化的过滤器构建，基于资源中的真实属性"""
    filter_info = {
        "cql_filter": None,
        "description": "无过滤条件",
        "attribute_name": None,
        "attribute_values": None,
        "filter_type": "none"
    }
    
    if not attribute_filter or not filter_values:
        return filter_info
    
    # 从多个来源获取属性列表
    attributes = []
    
    # 1. 从capabilities获取属性
    capabilities_attrs = layer_info.get("capabilities", {}).get("attributes", [])
    if capabilities_attrs:
        attributes.extend([attr.get("name", "") for attr in capabilities_attrs if attr.get("name")])
    
    # 2. 从detailed_capabilities的WFS部分获取属性
    wfs_details = layer_info.get("detailed_capabilities", {}).get("wfs", {})
    if wfs_details:
        wfs_attrs = wfs_details.get("attributes", [])
        if wfs_attrs:
            attributes.extend([attr.get("name", "") for attr in wfs_attrs if attr.get("name")])
        
        # 3. 从feature_schema获取属性（DescribeFeatureType结果）
        feature_schema = wfs_details.get("feature_schema", {})
        if feature_schema:
            schema_attrs = feature_schema.get("attributes", [])
            if schema_attrs:
                attributes.extend([attr.get("name", "") for attr in schema_attrs if attr.get("name")])
    
    # 去重并过滤空值
    valid_attributes = list(set([attr for attr in attributes if attr]))
    
    if ctx:
        await ctx.debug(f"🔍 从资源获取的属性列表: {valid_attributes}")
    
    # 如果没有找到属性，返回空过滤器而不是抛出错误
    if not valid_attributes:
        if ctx:
            await ctx.warning("⚠️ 未从资源中获取到属性信息，跳过过滤")
        return filter_info
    
    # 如果属性不在列表中，尝试智能匹配或跳过过滤
    if attribute_filter not in valid_attributes:
        # 尝试大小写不敏感匹配
        matched_attr = None
        for attr in valid_attributes:
            if attr.lower() == attribute_filter.lower():
                matched_attr = attr
                break
        
        if matched_attr:
            attribute_filter = matched_attr
            if ctx:
                await ctx.info(f"🔄 属性名大小写匹配: {attribute_filter}")
        else:
            # 如果无法匹配，记录信息但不抛出错误，让AI有机会重新选择
            if ctx:
                await ctx.warning(f"⚠️ 属性 '{attribute_filter}' 不在可用属性中: {', '.join(valid_attributes[:5])}")
            return filter_info
    
    # 解析多个过滤值
    values_list = [value.strip() for value in filter_values.split(',') if value.strip()]
    
    if not values_list:
        if ctx:
            await ctx.warning("⚠️ 过滤值为空，跳过过滤")
        return filter_info
    
    if ctx:
        await ctx.debug(f"🔍 解析的过滤值列表: {values_list}")
    
    # 构建CQL过滤器
    if len(values_list) == 1:
        # 单个值：使用等值过滤
        escaped_value = values_list[0].replace("'", "''")  # 转义单引号
        cql_filter = f"{attribute_filter} = '{escaped_value}'"
        filter_type = "single_value"
        description = f"过滤条件: {attribute_filter} = '{values_list[0]}'"
    else:
        # 多个值：使用IN操作符
        escaped_values = [f"'{value.replace(chr(39), chr(39)+chr(39))}'" for value in values_list]
        cql_filter = f"{attribute_filter} IN ({', '.join(escaped_values)})"
        filter_type = "multiple_values"
        description = f"过滤条件: {attribute_filter} IN ({', '.join(values_list)})"
    
    filter_info.update({
        "cql_filter": cql_filter,
        "description": description,
        "attribute_name": attribute_filter,
        "attribute_values": values_list,
        "filter_type": filter_type,
        "value_count": len(values_list)
    })
    
    if ctx:
        await ctx.info(f"🔍 构建过滤器: {cql_filter}")
        await ctx.info(f" 过滤值数量: {len(values_list)}")
    
    return filter_info


async def _fetch_wfs_data_optimized(
    layer_info: Dict[str, Any], 
    max_features: int,
    filter_info: Dict[str, Any],
    ctx: Context
) -> Dict[str, Any]:
    """优化的WFS数据获取"""
    try:
        basic_info = layer_info.get("basic_info", {})
        wfs_params = layer_info.get("access_parameters", {}).get("wfs", {})
        
        # 获取WFS专用的服务URL
        wfs_url_base = wfs_params.get("service_url") or basic_info.get("service_url", "")
        
        # 确保使用正确的WFS端点
        if "gwc/service/wmts" in wfs_url_base:
            # 如果是WMTS URL，替换为WFS URL
            wfs_url_base = wfs_url_base.replace("gwc/service/wmts", "wfs")
        elif "wmts" in wfs_url_base.lower():
            # 如果包含wmts，替换为wfs
            wfs_url_base = wfs_url_base.replace("wmts", "wfs").replace("WMTS", "wfs")
        elif not wfs_url_base.endswith(("/wfs", "/ows")):
            # 确保URL以正确的服务端点结尾
            if wfs_url_base.endswith("/"):
                wfs_url_base = wfs_url_base + "wfs"
            else:
                wfs_url_base = wfs_url_base + "/wfs"
        
        base_url = wfs_url_base.rstrip('?')
        if not base_url:
            raise Exception("缺少WFS服务URL")
        
        if ctx:
            await ctx.debug(f"🔧 使用WFS服务URL: {base_url}")
        
        # 构建请求参数（确保参数名称和值都正确）
        params = {
            "SERVICE": "WFS",
            "VERSION": wfs_params.get("version", "2.0.0"),
            "REQUEST": "GetFeature",
            "TYPENAME": wfs_params.get("typeNames", basic_info.get("layer_name", "")),
            "OUTPUTFORMAT": "application/json",
            "MAXFEATURES": str(max_features),
            "SRSNAME": wfs_params.get("srsName", "EPSG:4326")
        }
        
        # 添加过滤条件
        if filter_info.get("cql_filter"):
            params["CQL_FILTER"] = filter_info["cql_filter"]
        
        # 使用标准的URL编码方式
        from urllib.parse import urlencode
        
        # 使用urlencode但保持参数名大写
        query_string = urlencode(params, quote_via=lambda x, *args, **kwargs: x)
        wfs_url = f"{base_url}?{query_string}"
        
        if ctx:
            await ctx.info(f"🌐 WFS请求URL: {wfs_url}")
        
        # 优化HTTP请求配置
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        headers = {
            'User-Agent': 'OGC-MCP-Server/1.0',
            'Accept': 'application/json, application/geo+json, */*',
            'Accept-Encoding': 'gzip, deflate'
        }
        
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            if ctx:
                await ctx.debug("📡 发送HTTP请求...")
            
            async with session.get(wfs_url) as response:
                if ctx:
                    await ctx.debug(f"📥 HTTP响应状态: {response.status}")
                
                if response.status == 200:
                    # 检查响应内容类型
                    content_type = response.headers.get('content-type', '').lower()
                    
                    if 'json' in content_type:
                        geojson_data = await response.json()
                    else:
                        # 尝试解析为JSON
                        text_content = await response.text()
                        if ctx:
                            await ctx.debug(f"📄 响应内容类型: {content_type}")
                            await ctx.debug(f"📄 响应内容前200字符: {text_content[:200]}")
                        
                        try:
                            geojson_data = json.loads(text_content)
                        except json.JSONDecodeError:
                            raise Exception(f"无法解析响应为JSON。内容类型: {content_type}")
                    
                    # 验证GeoJSON格式
                    if not isinstance(geojson_data, dict):
                        raise Exception("响应不是有效的JSON对象")
                    
                    if "features" not in geojson_data:
                        # 检查是否是错误响应
                        if "ExceptionReport" in str(geojson_data) or "ServiceException" in str(geojson_data):
                            raise Exception(f"WFS服务返回错误: {str(geojson_data)[:500]}")
                        else:
                            raise Exception("响应不包含features字段，不是有效的GeoJSON")
                    
                    if ctx:
                        feature_count = len(geojson_data.get("features", []))
                        await ctx.info(f"✅ 成功获取 {feature_count} 个要素")
                    
                    return geojson_data
                    
                else:
                    error_text = await response.text()
                    if ctx:
                        await ctx.error(f"❌ HTTP错误 {response.status}: {error_text[:500]}")
                    raise Exception(f"WFS请求失败: HTTP {response.status}\n错误详情: {error_text[:500]}")
                    
    except aiohttp.ClientError as e:
        raise Exception(f"网络请求失败: {str(e)}")
    except Exception as e:
        raise Exception(f"获取WFS数据失败: {str(e)}")


def _create_wfs_layer_optimized(
    layer_info: Dict[str, Any], 
    title: str, 
    geojson_data: Dict[str, Any],
    filter_info: Dict[str, Any]
) -> Dict[str, Any]:
    """创建优化的WFS图层对象"""
    basic_info = layer_info.get("basic_info", {})
    wfs_params = layer_info.get("access_parameters", {}).get("wfs", {})
    capabilities = layer_info.get("capabilities", {})
    detailed_capabilities = layer_info.get("detailed_capabilities", {})
    
    # 获取WFS详细信息
    wfs_details = detailed_capabilities.get("wfs", {})
    
    # 分析几何类型
    features = geojson_data.get("features", [])
    geometry_types = set()
    for feature in features:
        geom = feature.get("geometry", {})
        if geom and geom.get("type"):
            geometry_types.add(geom["type"])
    
    return {
        # 基础信息
        "name": basic_info.get("layer_name", ""),
        "title": title,
        "type": "wfs",
        "service_type": "WFS",
        "layer_info": basic_info,
        
        # 数据信息
        "geojson_data": geojson_data,
        "feature_count": len(features),
        
        # 几何和属性信息
        "geometry_type": capabilities.get("geometry_type") or (list(geometry_types)[0] if geometry_types else None),
        "geometry_types": list(geometry_types),
        "attributes": capabilities.get("attributes", []),
        
        # 空间信息
        "bbox": wfs_details.get("bbox") or capabilities.get("bbox", {}),
        "crs_list": wfs_details.get("crs_list") or capabilities.get("crs_list", ["EPSG:4326"]),
        "default_crs": wfs_details.get("default_crs") or capabilities.get("default_crs", "EPSG:4326"),
        
        # 过滤器信息（增强）
        "filter_info": filter_info,
        "has_filter": bool(filter_info.get("cql_filter")),
        "filter_type": filter_info.get("filter_type", "none"),
        "filtered_values": filter_info.get("attribute_values", []),
        
        # WFS参数
        "wfs_params": wfs_params,
        "queryable": True,
        
        # 样式
        "style": _get_default_style(geometry_types),
        
        # 元数据
        "metadata": {
            "source": "optimized_wfs_tool",
            "has_detailed_capabilities": bool(wfs_details),
            "optimization_version": "1.1",
            "supports_multi_value_filter": True
        }
    }


def _get_default_style(geometry_types: set) -> Dict[str, Any]:
    """获取默认样式"""
    if "Point" in geometry_types or "MultiPoint" in geometry_types:
        return {
            "type": "point",
            "color": "#e74c3c",
            "fillColor": "#e74c3c",
            "fillOpacity": 0.7,
            "radius": 8,
            "weight": 2
        }
    elif any(geom in geometry_types for geom in ["LineString", "MultiLineString"]):
        return {
            "type": "line",
            "color": "#3498db",
            "weight": 3,
            "opacity": 0.8
        }
    elif any(geom in geometry_types for geom in ["Polygon", "MultiPolygon"]):
        return {
            "type": "polygon",
            "color": "#2ecc71",
            "fillColor": "#2ecc71",
            "fillOpacity": 0.3,
            "weight": 2,
            "opacity": 0.8
        }
    else:
        return {
            "type": "default",
            "color": "#9b59b6",
            "fillColor": "#9b59b6",
            "fillOpacity": 0.4,
            "weight": 2,
            "opacity": 0.8
        }