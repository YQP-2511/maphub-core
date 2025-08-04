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
    name="add_wfs_layer_full",
    description="""添加完整的WFS矢量图层到地图，获取所有可用数据。

适用场景：
- 探索性数据分析，需要查看图层的全部内容
- 小型数据集的完整展示
- 了解图层的数据结构和属性分布

注意事项：
- 会获取图层的所有要素（受max_features限制）
- 适合数据量较小的图层
- 如需特定条件的数据，请使用add_wfs_layer_filtered工具""",
    tags={"wfs", "layer", "vector", "full_data", "exploration"}
)
async def add_wfs_layer_full(
    layer_name: Annotated[str, Field(description="WFS图层名称")],
    layer_title: Annotated[str, Field(description="图层显示标题")] = None,
    max_features: Annotated[int, Field(description="最大要素数量，默认100")] = 100,
    ctx: Context = None
) -> Dict[str, Any]:
    """添加完整的WFS矢量图层到地图可视化
    
    获取图层的所有可用数据，不应用任何过滤条件。
    适合用于数据探索和完整数据集的展示。
    """
    try:
        if ctx:
            await ctx.info(f"🔄 开始添加完整WFS图层: {layer_name}")
        
        # 获取图层信息
        layer_info = await _get_layer_info_simplified(layer_name, ctx)
        
        # 验证WFS支持
        if not _validate_wfs_support(layer_info, layer_name):
            supported_services = layer_info.get("metadata", {}).get("supported_services", [])
            raise ValueError(
                f"图层 '{layer_name}' 不支持WFS服务。"
                f"支持的服务类型: {', '.join(supported_services) if supported_services else '无'}"
            )
        
        # 获取完整WFS数据（无过滤）
        geojson_data = await _fetch_wfs_data_optimized(layer_info, max_features, {}, ctx)
        
        # 创建图层对象
        wfs_layer = _create_wfs_layer_optimized(
            layer_info, 
            layer_title or layer_name, 
            geojson_data, 
            {"description": "完整数据，无过滤条件"}
        )
        
        # 添加到图层列表
        visualization_tools._current_layers.append(wfs_layer)
        
        feature_count = len(geojson_data.get("features", []))
        success_msg = f"✅ 完整WFS图层 '{layer_name}' 添加成功，包含 {feature_count} 个要素"
        
        if ctx:
            await ctx.info(success_msg)
        
        return {
            "success": True,
            "message": success_msg,
            "layer_info": {
                "name": layer_name,
                "title": wfs_layer["title"],
                "type": "wfs_full",
                "feature_count": feature_count,
                "geometry_type": wfs_layer.get("geometry_type"),
                "filter_applied": False,
                "data_type": "complete"
            },
            "current_layer_count": len(visualization_tools._current_layers)
        }
        
    except Exception as e:
        error_msg = f"❌ 添加完整WFS图层失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        if ctx:
            await ctx.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "layer_name": layer_name,
            "current_layer_count": len(visualization_tools._current_layers)
        }


@wfs_layer_server.tool(
    name="add_wfs_layer_filtered",
    description="""添加过滤的WFS矢量图层到地图，基于图层资源中的真实属性进行精确过滤。

属性匹配机制：
- 自动从layer_registry.py资源中获取图层的真实属性信息
- 支持精确匹配、大小写不敏感匹配和包含匹配
- 优先使用WFS的feature_schema中的详细属性信息
- 如果资源中没有属性信息，会尝试直接使用用户提供的属性名

过滤策略：
- 单值过滤：attribute_filter="CITY_NAME", filter_values="北京"
- 多值过滤：attribute_filter="CITY_NAME", filter_values="北京,上海,广州"
- 支持地名、分类、数值等各种类型的属性过滤

适用场景：
- 查找特定区域的数据（基于行政区划、地名等属性）
- 筛选特定类别的要素（基于土地利用、建筑类型等属性）
- 获取满足特定条件的数据子集

注意：工具会智能匹配属性名，但建议使用准确的属性名以获得最佳结果。
""",
    tags={"wfs", "layer", "vector", "filter", "resource-based", "smart-matching"}
)
async def add_wfs_layer_filtered(
    layer_name: str,
    attribute_filter: str,
    filter_values: str,
    max_features: int = 1000,
    layer_title: Optional[str] = None,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """添加过滤的WFS图层到地图
    
    Args:
        layer_name: 图层名称
        attribute_filter: 要过滤的属性名称
        filter_values: 过滤值，多个值用逗号分隔
        max_features: 最大要素数量，默认1000
        layer_title: 自定义图层标题
        ctx: MCP上下文
    
    Returns:
        包含操作结果的字典
    """
    try:
        if ctx:
            await ctx.info(f"🔍 开始添加过滤WFS图层: {layer_name}")
            await ctx.info(f"📋 过滤条件: {attribute_filter} = {filter_values}")
        
        # 获取图层信息（包含发现功能）
        layer_info = await _get_layer_info_simplified(layer_name, ctx)
        
        # 验证WFS支持
        if not _validate_wfs_support(layer_info, layer_name):
            raise ValueError(f"图层 '{layer_name}' 不支持WFS服务")
        
        # 构建过滤器
        try:
            filter_info = await _build_filter_optimized(layer_info, attribute_filter, filter_values, ctx)
        except ValueError as e:
            # 提取可用属性信息用于错误提示
            available_attrs = _extract_attributes_from_resource(layer_info)
            attr_info = f"可用属性: {', '.join(available_attrs[:10])}" if available_attrs else "无法获取属性信息"
            raise ValueError(f"无法为属性 '{attribute_filter}' 构建有效的过滤器。{attr_info}")
        
        # 获取过滤的WFS数据
        geojson_data = await _fetch_wfs_data_optimized(layer_info, max_features, filter_info, ctx)
        
        # 检查是否返回0个要素，如果是则进行属性值探索
        feature_count = len(geojson_data.get("features", []))
        if feature_count == 0 and filter_info.get("cql_filter"):
            if ctx:
                await ctx.info("🔍 过滤结果为空，开始探索可用属性值...")
            
            # 探索属性值
            value_suggestions = await _explore_attribute_values(
                layer_info, filter_info.get("attribute_name"), ctx
            )
            
            if value_suggestions:
                suggestion_msg = f"💡 属性 '{filter_info.get('attribute_name')}' 的可用值示例: {', '.join(value_suggestions[:10])}"
                if ctx:
                    await ctx.info(suggestion_msg)
                
                # 返回包含建议的结果
                return {
                    "success": False,
                    "message": f"过滤条件未匹配到任何要素",
                    "layer_name": layer_name,
                    "filter_info": {
                        "attribute": attribute_filter,
                        "values": filter_values,
                        "matched_attribute": filter_info.get("attribute_name"),
                        "available_values": value_suggestions
                    },
                    "suggestions": {
                        "attribute_values": value_suggestions,
                        "message": suggestion_msg
                    },
                    "current_layer_count": len(visualization_tools._current_layers)
                }
        
        # 创建图层对象
        wfs_layer = _create_wfs_layer_optimized(layer_info, layer_title or layer_name, geojson_data, filter_info)
        
        # 添加到图层列表
        visualization_tools._current_layers.append(wfs_layer)
        
        success_msg = f"✅ 过滤WFS图层 '{layer_name}' 添加成功，包含 {feature_count} 个要素"
        
        if ctx:
            await ctx.info(success_msg)
            await ctx.info(f"🔍 应用的过滤条件: {filter_info.get('description', '未知')}")
            if filter_info.get("matched_from_resource"):
                await ctx.info("✅ 属性名已从资源中成功匹配")
        
        return {
            "success": True,
            "message": success_msg,
            "layer_info": {
                "name": layer_name,
                "title": wfs_layer["title"],
                "type": "wfs_filtered",
                "feature_count": feature_count,
                "geometry_type": wfs_layer.get("geometry_type"),
                "filter_applied": True,
                "filter_description": filter_info.get("description"),
                "filter_attribute": filter_info.get("attribute_name"),
                "filter_values": filter_info.get("attribute_values", []),
                "attribute_matched_from_resource": filter_info.get("matched_from_resource", False),
                "data_type": "filtered"
            },
            "current_layer_count": len(visualization_tools._current_layers)
        }
        
    except Exception as e:
        error_msg = f"❌ 添加过滤WFS图层失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        if ctx:
            await ctx.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "layer_name": layer_name,
            "filter_info": {
                "attribute": attribute_filter,
                "values": filter_values
            },
            "current_layer_count": len(visualization_tools._current_layers)
        }


async def _explore_attribute_values(
    layer_info: Dict[str, Any], 
    attribute_name: str, 
    ctx: Context,
    sample_size: int = 50
) -> List[str]:
    """探索指定属性的可用值
    
    Args:
        layer_info: 图层信息
        attribute_name: 属性名称
        ctx: MCP上下文
        sample_size: 采样大小
    
    Returns:
        属性值列表
    """
    try:
        if ctx:
            await ctx.debug(f"🔍 开始探索属性 '{attribute_name}' 的可用值")
        
        # 构建无过滤条件的请求来获取样本数据
        no_filter_info = {
            "cql_filter": None,
            "description": "无过滤条件（用于属性值探索）",
            "attribute_name": None,
            "attribute_values": None,
            "filter_type": "none"
        }
        
        # 获取样本数据
        sample_data = await _fetch_wfs_data_optimized(layer_info, sample_size, no_filter_info, ctx)
        
        features = sample_data.get("features", [])
        if not features:
            if ctx:
                await ctx.debug("⚠️ 无法获取样本数据进行属性值探索")
            return []
        
        # 提取指定属性的值
        attribute_values = set()
        for feature in features:
            properties = feature.get("properties", {})
            if attribute_name in properties:
                value = properties[attribute_name]
                if value is not None:
                    # 转换为字符串并添加到集合中
                    str_value = str(value).strip()
                    if str_value:
                        attribute_values.add(str_value)
        
        # 转换为排序的列表
        sorted_values = sorted(list(attribute_values))
        
        if ctx:
            await ctx.debug(f"✅ 从 {len(features)} 个样本要素中发现 {len(sorted_values)} 个不同的属性值")
        
        return sorted_values[:20]  # 返回前20个值作为建议
        
    except Exception as e:
        if ctx:
            await ctx.debug(f"❌ 属性值探索失败: {str(e)}")
        return []


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
    """优化的过滤器构建，直接使用资源中的真实属性信息"""
    filter_info = {
        "cql_filter": None,
        "description": "无过滤条件",
        "attribute_name": None,
        "attribute_values": None,
        "filter_type": "none"
    }
    
    if not attribute_filter or not filter_values:
        return filter_info
    
    # 从layer_registry.py资源中提取真实属性信息
    available_attributes = _extract_attributes_from_resource(layer_info)
    
    if ctx:
        await ctx.debug(f"🔍 从资源获取的属性列表: {available_attributes}")
    
    # 如果没有找到属性，记录警告但不阻止流程
    if not available_attributes:
        if ctx:
            await ctx.warning("⚠️ 未从资源中获取到属性信息，将尝试直接使用用户提供的属性名")
        # 直接使用用户提供的属性名，让WFS服务验证
        matched_attribute = attribute_filter
    else:
        # 智能匹配属性名
        matched_attribute = _smart_match_attribute(attribute_filter, available_attributes, ctx)
        if not matched_attribute:
            if ctx:
                await ctx.warning(f"⚠️ 属性 '{attribute_filter}' 无法匹配，可用属性: {', '.join(available_attributes[:5])}")
            return filter_info
    
    # 构建CQL过滤器
    cql_filter, filter_description = _build_cql_filter(matched_attribute, filter_values)
    
    filter_info.update({
        "cql_filter": cql_filter,
        "description": filter_description,
        "attribute_name": matched_attribute,
        "attribute_values": [v.strip() for v in filter_values.split(',') if v.strip()],
        "filter_type": "single_value" if ',' not in filter_values else "multiple_values",
        "value_count": len([v.strip() for v in filter_values.split(',') if v.strip()]),
        "matched_from_resource": matched_attribute in available_attributes if available_attributes else False
    })
    
    if ctx:
        await ctx.info(f"🔍 构建过滤器: {cql_filter}")
        await ctx.info(f"📊 过滤值数量: {filter_info['value_count']}")
    
    return filter_info


def _extract_attributes_from_resource(layer_info: Dict[str, Any]) -> List[str]:
    """从layer_registry.py资源中提取属性信息
    
    按优先级从多个位置提取属性：
    1. detailed_capabilities.wfs.feature_schema.attributes (最详细)
    2. detailed_capabilities.wfs.attributes (WFS特定)
    3. capabilities.attributes (通用)
    """
    attributes = []
    
    # 优先级1: 从WFS的feature_schema获取（DescribeFeatureType结果）
    wfs_details = layer_info.get("detailed_capabilities", {}).get("wfs", {})
    if wfs_details:
        feature_schema = wfs_details.get("feature_schema", {})
        if feature_schema:
            schema_attrs = feature_schema.get("attributes", [])
            for attr in schema_attrs:
                if isinstance(attr, dict) and attr.get("name"):
                    attributes.append(attr["name"])
        
        # 优先级2: 从WFS详细信息获取
        if not attributes:
            wfs_attrs = wfs_details.get("attributes", [])
            for attr in wfs_attrs:
                if isinstance(attr, dict) and attr.get("name"):
                    attributes.append(attr["name"])
    
    # 优先级3: 从通用capabilities获取
    if not attributes:
        capabilities_attrs = layer_info.get("capabilities", {}).get("attributes", [])
        for attr in capabilities_attrs:
            if isinstance(attr, dict) and attr.get("name"):
                attributes.append(attr["name"])
    
    # 去重并过滤空值
    return list(set([attr for attr in attributes if attr]))


def _smart_match_attribute(target_attr: str, available_attrs: List[str], ctx: Context = None) -> Optional[str]:
    """智能匹配属性名称
    
    匹配策略：
    1. 精确匹配
    2. 大小写不敏感匹配
    3. 包含匹配（目标属性包含在可用属性中）
    4. 被包含匹配（可用属性包含在目标属性中）
    """
    if not available_attrs:
        return target_attr
    
    # 1. 精确匹配
    if target_attr in available_attrs:
        return target_attr
    
    # 2. 大小写不敏感匹配
    for attr in available_attrs:
        if attr.lower() == target_attr.lower():
            if ctx:
                ctx.info(f"🔄 属性名大小写匹配: {target_attr} -> {attr}")
            return attr
    
    # 3. 包含匹配（目标属性包含在可用属性中）
    for attr in available_attrs:
        if target_attr.lower() in attr.lower():
            if ctx:
                ctx.info(f"🔄 属性名包含匹配: {target_attr} -> {attr}")
            return attr
    
    # 4. 被包含匹配（可用属性包含在目标属性中）
    for attr in available_attrs:
        if attr.lower() in target_attr.lower():
            if ctx:
                ctx.info(f"🔄 属性名被包含匹配: {target_attr} -> {attr}")
            return attr
    
    # 无法匹配
    return None


def _build_cql_filter(attribute_name: str, filter_values: str) -> tuple[str, str]:
    """构建CQL过滤器字符串"""
    values_list = [value.strip() for value in filter_values.split(',') if value.strip()]
    
    if len(values_list) == 1:
        # 单个值：使用等值过滤
        escaped_value = values_list[0].replace("'", "''")  # 转义单引号
        cql_filter = f"{attribute_name} = '{escaped_value}'"
        description = f"过滤条件: {attribute_name} = '{values_list[0]}'"
    else:
        # 多个值：使用IN操作符
        escaped_values = [f"'{value.replace(chr(39), chr(39)+chr(39))}'" for value in values_list]
        cql_filter = f"{attribute_name} IN ({', '.join(escaped_values)})"
        description = f"过滤条件: {attribute_name} IN ({', '.join(values_list)})"
    
    return cql_filter, description


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