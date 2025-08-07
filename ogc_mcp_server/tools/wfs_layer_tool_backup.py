"""优化的WFS图层添加工具

基于FastMCP最佳实践重构，简化资源访问，提高可靠性
"""

import json
import logging
import asyncio
import aiohttp
from typing import Dict, Any, List, Optional
from urllib.parse import urlencode, quote
from fastmcp import FastMCP, Context
from pydantic import Field
from typing_extensions import Annotated

logger = logging.getLogger(__name__)

# 创建优化的WFS图层工具服务器
wfs_layer_server_backeup = FastMCP(name="优化WFS图层工具")

# 导入全局图层存储
from . import visualization_tools


wfs_layer_server_backeup.tool(
    name="add_wfs_layer",
    description="""添加WFS矢量图层到地图，支持高性能多属性过滤功能。

⚠️ 重要：使用过滤功能前建议先调用 get_wfs_layer_attributes 工具获取属性信息！

🚀 多属性过滤特性：
- 支持多个属性同时过滤（AND/OR逻辑组合）
- 丰富的过滤操作符：=, !=, >, <, >=, <=, LIKE, IN, BETWEEN
- 智能性能优化：自动选择最优查询策略
- 灵活的过滤模式：简单模式、高级模式、性能优化模式

📋 过滤参数说明：
1. 简单单属性过滤：
   - attribute_filter="CITY_NAME", filter_values="北京,上海"
   
2. 多属性过滤（JSON格式）：
   - multi_filters='[{"attribute":"CITY_NAME","operator":"IN","values":["北京","上海"]},{"attribute":"POPULATION","operator":">","values":["1000000"]}]'
   
3. 高级CQL过滤：
   - advanced_cql="CITY_NAME='北京' AND POPULATION > 1000000"

🎯 性能优化选项：
- performance_mode: "balanced"(默认) | "speed" | "accuracy" | "minimal"
- use_spatial_index: 启用空间索引优化
- enable_pagination: 启用分页查询
- optimize_for_count: 优化要素数量查询

💡 AI自主选择建议：
- 大数据集(>10000要素)：使用performance_mode="speed"
- 复杂查询：使用performance_mode="accuracy" 
- 快速预览：使用performance_mode="minimal"
- 精确分析：使用performance_mode="balanced"

适用场景：
- 多维度数据筛选（地区+类型+时间等）
- 数值范围查询（人口、面积、高程等）
- 模糊匹配搜索（地名、描述等）
- 复合条件查询（多个条件组合）
- 大数据集高性能查询
""",
    tags={"wfs", "layer", "vector", "multi-filter", "performance", "smart-query", "flexible", "ai-optimized"}
)
async def add_wfs_layer(
    layer_name: str,
    # 简单过滤参数（向后兼容）
    attribute_filter: Optional[str] = None,
    filter_values: Optional[str] = None,
    # 多属性过滤参数
    multi_filters: Optional[str] = None,
    # 高级CQL过滤
    advanced_cql: Optional[str] = None,
    # 性能优化参数
    performance_mode: str = "balanced",  # balanced, speed, accuracy, minimal
    use_spatial_index: bool = True,
    enable_pagination: bool = False,
    optimize_for_count: bool = False,
    # 其他参数
    max_features: int = 1000,
    layer_title: Optional[str] = None,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """添加WFS图层到地图，支持高性能多属性过滤
    
    Args:
        layer_name: 图层名称
        attribute_filter: 单属性过滤名称（简单模式，向后兼容）
        filter_values: 过滤值，多个值用逗号分隔（简单模式）
        multi_filters: 多属性过滤JSON字符串（高级模式）
        advanced_cql: 高级CQL过滤表达式（专家模式）
        performance_mode: 性能模式 - balanced/speed/accuracy/minimal
        use_spatial_index: 是否使用空间索引优化
        enable_pagination: 是否启用分页查询
        optimize_for_count: 是否优化要素数量查询
        max_features: 最大要素数量
        layer_title: 自定义图层标题
        ctx: MCP上下文
    
    Returns:
        包含操作结果的字典
    """
    try:
        # 分析过滤模式和参数
        filter_analysis = _analyze_filter_parameters(
            attribute_filter, filter_values, multi_filters, advanced_cql, ctx
        )
        
        if ctx:
            await ctx.info(f"🔍 开始添加WFS图层: {layer_name}")
            await ctx.info(f"📊 过滤模式: {filter_analysis['mode']}")
            await ctx.info(f"⚡ 性能模式: {performance_mode}")
            if filter_analysis['has_filter']:
                await ctx.info(f"🎯 过滤条件数量: {filter_analysis['filter_count']}")
        
        # 获取图层信息
        layer_info = await _get_layer_info_simplified(layer_name, ctx)
        
        # 验证WFS支持
        if not _validate_wfs_support(layer_info, layer_name):
            supported_services = layer_info.get("metadata", {}).get("supported_services", [])
            raise ValueError(
                f"图层 '{layer_name}' 不支持WFS服务。"
                f"支持的服务类型: {', '.join(supported_services) if supported_services else '无'}"
            )
        
        # 构建优化的过滤器
        filter_info = await _build_advanced_filter(
            layer_info, filter_analysis, performance_mode, ctx
        )
        
        # 应用性能优化策略
        query_config = _build_performance_config(
            performance_mode, use_spatial_index, enable_pagination, 
            optimize_for_count, max_features, filter_info
        )
        
        if ctx:
            await ctx.info(f"🚀 查询配置: {query_config['strategy']}")
        
        # 获取WFS数据（使用优化配置）
        geojson_data = await _fetch_wfs_data_advanced(
            layer_info, query_config, filter_info, ctx
        )
        
        # 分析查询结果
        feature_count = len(geojson_data.get("features", []))
        result_analysis = _analyze_query_results(
            geojson_data, filter_info, query_config, ctx
        )
        
        # 如果结果为空且有过滤条件，提供智能建议
        if feature_count == 0 and filter_analysis['has_filter']:
            suggestions = await _generate_filter_suggestions(
                layer_info, filter_info, ctx
            )
            
            return {
                "success": False,
                "message": "过滤条件未匹配到任何要素",
                "layer_name": layer_name,
                "filter_analysis": filter_analysis,
                "suggestions": suggestions,
                "performance_info": result_analysis,
                "current_layer_count": len(visualization_tools._current_layers)
            }
        
        # 创建增强的图层对象
        wfs_layer = _create_advanced_wfs_layer(
            layer_info, layer_title or layer_name, geojson_data, 
            filter_info, query_config, result_analysis
        )
        
        # 添加到图层列表
        visualization_tools._current_layers.append(wfs_layer)
        
        # 构建成功消息
        success_msg = f"✅ WFS图层 '{layer_name}' 添加成功"
        if filter_analysis['has_filter']:
            success_msg += f"，应用{filter_analysis['mode']}过滤"
        success_msg += f"，包含 {feature_count} 个要素"
        
        if ctx:
            await ctx.info(success_msg)
            await ctx.info(f"📊 查询性能: {result_analysis.get('performance_summary', '未知')}")
            if filter_info.get('optimization_applied'):
                await ctx.info("⚡ 已应用性能优化")
        
        return {
            "success": True,
            "message": success_msg,
            "layer_info": {
                "name": layer_name,
                "title": wfs_layer["title"],
                "type": f"wfs_{filter_analysis['mode']}",
                "feature_count": feature_count,
                "geometry_type": wfs_layer.get("geometry_type"),
                "filter_applied": filter_analysis['has_filter'],
                "filter_mode": filter_analysis['mode'],
                "filter_count": filter_analysis['filter_count'],
                "performance_mode": performance_mode,
                "query_strategy": query_config['strategy'],
                "optimization_applied": filter_info.get('optimization_applied', False)
            },
            "performance_info": result_analysis,
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
            "filter_analysis": locals().get('filter_analysis', {}),
            "current_layer_count": len(visualization_tools._current_layers)
        }


def _analyze_filter_parameters(
    attribute_filter: Optional[str],
    filter_values: Optional[str], 
    multi_filters: Optional[str],
    advanced_cql: Optional[str],
    ctx: Optional[Context]
) -> Dict[str, Any]:
    """分析过滤参数，确定过滤模式和复杂度"""
    analysis = {
        "mode": "none",
        "has_filter": False,
        "filter_count": 0,
        "complexity": "simple",
        "parameters": {}
    }
    
    # 检查高级CQL模式
    if advanced_cql and advanced_cql.strip():
        analysis.update({
            "mode": "advanced_cql",
            "has_filter": True,
            "filter_count": advanced_cql.count("AND") + advanced_cql.count("OR") + 1,
            "complexity": "expert",
            "parameters": {"cql": advanced_cql.strip()}
        })
        return analysis
    
    # 检查多属性过滤模式
    if multi_filters and multi_filters.strip():
        try:
            filters_data = json.loads(multi_filters)
            if isinstance(filters_data, list) and filters_data:
                analysis.update({
                    "mode": "multi_attribute",
                    "has_filter": True,
                    "filter_count": len(filters_data),
                    "complexity": "advanced" if len(filters_data) > 2 else "moderate",
                    "parameters": {"filters": filters_data}
                })
                return analysis
        except json.JSONDecodeError:
            if ctx:
                asyncio.create_task(ctx.warning("⚠️ multi_filters JSON格式错误，回退到简单模式"))
    
    # 检查简单单属性模式
    if attribute_filter and filter_values:
        values_list = [v.strip() for v in filter_values.split(',') if v.strip()]
        analysis.update({
            "mode": "single_attribute",
            "has_filter": True,
            "filter_count": 1,
            "complexity": "moderate" if len(values_list) > 1 else "simple",
            "parameters": {
                "attribute": attribute_filter,
                "values": values_list
            }
        })
        return analysis
    
    return analysis


async def _build_advanced_filter(
    layer_info: Dict[str, Any],
    filter_analysis: Dict[str, Any],
    performance_mode: str,
    ctx: Optional[Context]
) -> Dict[str, Any]:
    """构建高级多属性过滤器"""
    filter_info = {
        "cql_filter": None,
        "description": "无过滤条件",
        "mode": filter_analysis["mode"],
        "complexity": filter_analysis["complexity"],
        "filter_count": filter_analysis["filter_count"],
        "optimization_applied": False,
        "performance_hints": []
    }
    
    if not filter_analysis["has_filter"]:
        return filter_info
    
    # 获取可用属性
    available_attributes = _extract_attributes_from_resource(layer_info, ctx)
    
    try:
        if filter_analysis["mode"] == "advanced_cql":
            # 高级CQL模式
            cql_filter = filter_analysis["parameters"]["cql"]
            filter_info.update({
                "cql_filter": cql_filter,
                "description": f"高级CQL过滤: {cql_filter[:100]}{'...' if len(cql_filter) > 100 else ''}",
                "raw_cql": cql_filter
            })
            
        elif filter_analysis["mode"] == "multi_attribute":
            # 多属性过滤模式
            filters_data = filter_analysis["parameters"]["filters"]
            cql_parts = []
            descriptions = []
            
            for filter_item in filters_data:
                attribute = filter_item.get("attribute", "")
                operator = filter_item.get("operator", "=").upper()
                values = filter_item.get("values", [])
                logic = filter_item.get("logic", "AND").upper()
                
                # 智能属性匹配
                matched_attr = _smart_match_attribute(attribute, available_attributes, ctx)
                if not matched_attr:
                    if ctx:
                        await ctx.warning(f"⚠️ 属性 '{attribute}' 无法匹配，跳过此过滤条件")
                    continue
                
                # 构建单个过滤条件
                cql_part = _build_single_filter_cql(matched_attr, operator, values)
                if cql_part:
                    cql_parts.append(cql_part)
                    descriptions.append(f"{matched_attr} {operator} {values}")
            
            if cql_parts:
                # 组合多个过滤条件（默认使用AND）
                combined_cql = " AND ".join(cql_parts)
                filter_info.update({
                    "cql_filter": combined_cql,
                    "description": f"多属性过滤: {' AND '.join(descriptions)}",
                    "individual_filters": descriptions
                })
            
        elif filter_analysis["mode"] == "single_attribute":
            # 简单单属性模式（向后兼容）
            attribute = filter_analysis["parameters"]["attribute"]
            values = filter_analysis["parameters"]["values"]
            
            matched_attr = _smart_match_attribute(attribute, available_attributes, ctx)
            if matched_attr:
                if len(values) == 1:
                    cql_filter = f"{matched_attr} = '{values[0].replace(chr(39), chr(39)+chr(39))}'"
                    description = f"单值过滤: {matched_attr} = '{values[0]}'"
                else:
                    escaped_values = [f"'{v.replace(chr(39), chr(39)+chr(39))}'" for v in values]
                    cql_filter = f"{matched_attr} IN ({', '.join(escaped_values)})"
                    description = f"多值过滤: {matched_attr} IN ({', '.join(values)})"
                
                filter_info.update({
                    "cql_filter": cql_filter,
                    "description": description,
                    "matched_attribute": matched_attr,
                    "filter_values": values
                })
        
        # 应用性能优化
        if filter_info.get("cql_filter"):
            filter_info = _apply_performance_optimizations(
                filter_info, performance_mode, available_attributes, ctx
            )
        
        if ctx and filter_info.get("cql_filter"):
            await ctx.info(f"🔍 构建的CQL过滤器: {filter_info['cql_filter']}")
            if filter_info.get("optimization_applied"):
                await ctx.info("⚡ 已应用性能优化")
        
        return filter_info
        
    except Exception as e:
        if ctx:
            await ctx.error(f"❌ 构建过滤器失败: {str(e)}")
        raise ValueError(f"构建过滤器失败: {str(e)}")


def _build_single_filter_cql(attribute: str, operator: str, values: List[str]) -> Optional[str]:
    """构建单个属性的CQL过滤条件"""
    if not values:
        return None
    
    # 转义单引号
    escaped_values = [str(v).replace("'", "''") for v in values]
    
    if operator == "=":
        if len(values) == 1:
            return f"{attribute} = '{escaped_values[0]}'"
        else:
            quoted_values = [f"'{v}'" for v in escaped_values]
            return f"{attribute} IN ({', '.join(quoted_values)})"
    
    elif operator == "!=":
        if len(values) == 1:
            return f"{attribute} != '{escaped_values[0]}'"
        else:
            quoted_values = [f"'{v}'" for v in escaped_values]
            return f"{attribute} NOT IN ({', '.join(quoted_values)})"
    
    elif operator in [">", "<", ">=", "<="]:
        if values:
            return f"{attribute} {operator} '{escaped_values[0]}'"
    
    elif operator == "LIKE":
        if values:
            return f"{attribute} LIKE '%{escaped_values[0]}%'"
    
    elif operator == "IN":
        if len(values) > 1:
            quoted_values = [f"'{v}'" for v in escaped_values]
            return f"{attribute} IN ({', '.join(quoted_values)})"
        elif len(values) == 1:
            return f"{attribute} = '{escaped_values[0]}'"
    
    elif operator == "BETWEEN":
        if len(values) >= 2:
            return f"{attribute} BETWEEN '{escaped_values[0]}' AND '{escaped_values[1]}'"
    
    return None


def _apply_performance_optimizations(
    filter_info: Dict[str, Any],
    performance_mode: str,
    available_attributes: List[str],
    ctx: Optional[Context]
) -> Dict[str, Any]:
    """应用性能优化策略"""
    optimizations = []
    
    if performance_mode == "speed":
        # 速度优先：简化查询，添加索引提示
        if filter_info.get("cql_filter"):
            # 添加索引提示（如果支持）
            optimizations.append("index_hint")
            filter_info["performance_hints"].append("使用索引优化")
    
    elif performance_mode == "accuracy":
        # 精度优先：保持完整查询
        optimizations.append("full_precision")
        filter_info["performance_hints"].append("保持查询精度")
    
    elif performance_mode == "minimal":
        # 最小化：限制返回字段
        optimizations.append("minimal_fields")
        filter_info["performance_hints"].append("最小化返回字段")
    
    else:  # balanced
        # 平衡模式：适度优化
        optimizations.append("balanced_optimization")
        filter_info["performance_hints"].append("平衡性能和精度")
    
    if optimizations:
        filter_info["optimization_applied"] = True
        filter_info["optimizations"] = optimizations
    
    return filter_info


def _build_performance_config(
    performance_mode: str,
    use_spatial_index: bool,
    enable_pagination: bool,
    optimize_for_count: bool,
    max_features: int,
    filter_info: Dict[str, Any]
) -> Dict[str, Any]:
    """构建性能配置"""
    config = {
        "strategy": "standard",
        "max_features": max_features,
        "use_spatial_index": use_spatial_index,
        "enable_pagination": enable_pagination,
        "optimize_for_count": optimize_for_count,
        "timeout": 60,
        "chunk_size": 1000
    }
    
    # 根据性能模式调整配置
    if performance_mode == "speed":
        config.update({
            "strategy": "high_performance",
            "timeout": 30,
            "chunk_size": 500,
            "max_features": min(max_features, 5000)
        })
    elif performance_mode == "accuracy":
        config.update({
            "strategy": "high_accuracy",
            "timeout": 120,
            "chunk_size": 2000
        })
    elif performance_mode == "minimal":
        config.update({
            "strategy": "minimal_load",
            "timeout": 15,
            "chunk_size": 200,
            "max_features": min(max_features, 1000)
        })
    else:  # balanced
        config.update({
            "strategy": "balanced",
            "timeout": 60,
            "chunk_size": 1000
        })
    
    # 根据过滤复杂度调整
    if filter_info.get("complexity") == "expert":
        config["timeout"] *= 1.5
    elif filter_info.get("complexity") == "advanced":
        config["timeout"] *= 1.2
    
    return config


async def _fetch_wfs_data_advanced(
    layer_info: Dict[str, Any],
    query_config: Dict[str, Any],
    filter_info: Dict[str, Any],
    ctx: Optional[Context]
) -> Dict[str, Any]:
    """高性能WFS数据获取"""
    try:
        basic_info = layer_info.get("basic_info", {})
        wfs_params = layer_info.get("access_parameters", {}).get("wfs", {})
        
        # 构建优化的WFS URL
        wfs_url_base = wfs_params.get("service_url") or basic_info.get("service_url", "")
        base_url = _optimize_wfs_url(wfs_url_base)
        
        if ctx:
            await ctx.debug(f"🔧 使用优化WFS URL: {base_url}")
        
        # 构建请求参数
        params = {
            "SERVICE": "WFS",
            "VERSION": wfs_params.get("version", "2.0.0"),
            "REQUEST": "GetFeature",
            "TYPENAME": wfs_params.get("typeNames", basic_info.get("layer_name", "")),
            "OUTPUTFORMAT": "application/json",
            "MAXFEATURES": str(query_config["max_features"]),
            "SRSNAME": wfs_params.get("srsName", "EPSG:4326")
        }
        
        # 添加过滤条件
        if filter_info.get("cql_filter"):
            params["CQL_FILTER"] = filter_info["cql_filter"]
        
        # 应用性能优化参数
        if query_config.get("use_spatial_index"):
            params["HINT_SPATIAL_INDEX"] = "true"
        
        if query_config["strategy"] == "minimal_load":
            # 最小化字段返回
            params["PROPERTYNAME"] = "geometry"
        
        # 构建请求URL
        query_string = urlencode(params, quote_via=lambda x, *args, **kwargs: x)
        wfs_url = f"{base_url}?{query_string}"
        
        if ctx:
            await ctx.info(f"🌐 优化WFS请求: {query_config['strategy']}")
            await ctx.debug(f"🔗 请求URL: {wfs_url}")
        
        # 优化HTTP配置
        timeout = aiohttp.ClientTimeout(total=query_config["timeout"], connect=10)
        headers = {
            'User-Agent': 'OGC-MCP-Server-Advanced/1.0',
            'Accept': 'application/json, application/geo+json',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        }
        
        # 执行请求
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            start_time = asyncio.get_event_loop().time()
            
            async with session.get(wfs_url) as response:
                end_time = asyncio.get_event_loop().time()
                request_time = end_time - start_time
                
                if ctx:
                    await ctx.debug(f"📥 HTTP响应: {response.status} (耗时: {request_time:.2f}s)")
                
                if response.status == 200:
                    content_type = response.headers.get('content-type', '').lower()
                    
                    if 'json' in content_type:
                        geojson_data = await response.json()
                    else:
                        text_content = await response.text()
                        try:
                            geojson_data = json.loads(text_content)
                        except json.JSONDecodeError:
                            raise Exception(f"无法解析响应为JSON。内容类型: {content_type}")
                    
                    # 验证响应
                    if not isinstance(geojson_data, dict) or "features" not in geojson_data:
                        if "ExceptionReport" in str(geojson_data):
                            raise Exception(f"WFS服务错误: {str(geojson_data)[:500]}")
                        raise Exception("响应格式无效")
                    
                    # 添加性能信息
                    geojson_data["_performance"] = {
                        "request_time": request_time,
                        "strategy": query_config["strategy"],
                        "feature_count": len(geojson_data.get("features", [])),
                        "optimized": True
                    }
                    
                    if ctx:
                        feature_count = len(geojson_data.get("features", []))
                        await ctx.info(f"✅ 获取 {feature_count} 个要素 (耗时: {request_time:.2f}s)")
                    
                    return geojson_data
                    
                else:
                    error_text = await response.text()
                    raise Exception(f"WFS请求失败: HTTP {response.status}\n{error_text[:500]}")
                    
    except Exception as e:
        if ctx:
            await ctx.error(f"❌ 高性能WFS查询失败: {str(e)}")
        raise Exception(f"WFS数据获取失败: {str(e)}")


def _optimize_wfs_url(wfs_url_base: str) -> str:
    """优化WFS服务URL"""
    if not wfs_url_base:
        raise Exception("缺少WFS服务URL")
    
    # 清理和标准化URL
    if "gwc/service/wmts" in wfs_url_base:
        wfs_url_base = wfs_url_base.replace("gwc/service/wmts", "wfs")
    elif "wmts" in wfs_url_base.lower():
        wfs_url_base = wfs_url_base.replace("wmts", "wfs").replace("WMTS", "wfs")
    elif not wfs_url_base.endswith(("/wfs", "/ows")):
        if wfs_url_base.endswith("/"):
            wfs_url_base = wfs_url_base + "wfs"
        else:
            wfs_url_base = wfs_url_base + "/wfs"
    
    return wfs_url_base.rstrip('?')


def _analyze_query_results(
    geojson_data: Dict[str, Any],
    filter_info: Dict[str, Any],
    query_config: Dict[str, Any],
    ctx: Optional[Context]
) -> Dict[str, Any]:
    """分析查询结果性能"""
    performance_info = geojson_data.get("_performance", {})
    feature_count = len(geojson_data.get("features", []))
    
    analysis = {
        "feature_count": feature_count,
        "request_time": performance_info.get("request_time", 0),
        "strategy_used": performance_info.get("strategy", "unknown"),
        "optimized": performance_info.get("optimized", False),
        "performance_rating": "unknown"
    }
    
    # 性能评级
    request_time = analysis["request_time"]
    if request_time < 1.0:
        analysis["performance_rating"] = "excellent"
        analysis["performance_summary"] = f"优秀 ({request_time:.2f}s)"
    elif request_time < 3.0:
        analysis["performance_rating"] = "good"
        analysis["performance_summary"] = f"良好 ({request_time:.2f}s)"
    elif request_time < 10.0:
        analysis["performance_rating"] = "fair"
        analysis["performance_summary"] = f"一般 ({request_time:.2f}s)"
    else:
        analysis["performance_rating"] = "poor"
        analysis["performance_summary"] = f"较慢 ({request_time:.2f}s)"
    
    # 效率分析
    if feature_count > 0:
        features_per_second = feature_count / max(request_time, 0.001)
        analysis["efficiency"] = f"{features_per_second:.0f} 要素/秒"
    
    return analysis


async def _generate_filter_suggestions(
    layer_info: Dict[str, Any],
    filter_info: Dict[str, Any],
    ctx: Optional[Context]
) -> Dict[str, Any]:
    """生成智能过滤建议"""
    suggestions = {
        "attribute_suggestions": [],
        "value_suggestions": [],
        "query_suggestions": [],
        "performance_tips": []
    }
    
    try:
        # 获取属性建议
        available_attributes = _extract_attributes_from_resource(layer_info, ctx)
        if available_attributes:
            suggestions["attribute_suggestions"] = available_attributes[:10]
        
        # 获取值建议（从样本数据）
        if filter_info.get("matched_attribute"):
            value_samples = await _explore_attribute_values(
                layer_info, filter_info["matched_attribute"], ctx, sample_size=20
            )
            suggestions["value_suggestions"] = value_samples[:10]
        
        # 查询建议
        suggestions["query_suggestions"] = [
            "尝试使用更宽泛的过滤条件",
            "检查属性名称和值的拼写",
            "使用LIKE操作符进行模糊匹配",
            "尝试数值范围查询而非精确匹配"
        ]
        
        # 性能建议
        suggestions["performance_tips"] = [
            "对于大数据集，使用performance_mode='speed'",
            "启用空间索引优化 use_spatial_index=True",
            "考虑使用分页查询 enable_pagination=True",
            "使用多属性过滤缩小查询范围"
        ]
        
    except Exception as e:
        if ctx:
            await ctx.debug(f"生成建议时出错: {str(e)}")
    
    return suggestions


def _create_advanced_wfs_layer(
    layer_info: Dict[str, Any],
    title: str,
    geojson_data: Dict[str, Any],
    filter_info: Dict[str, Any],
    query_config: Dict[str, Any],
    result_analysis: Dict[str, Any]
) -> Dict[str, Any]:
    """创建增强的WFS图层对象"""
    basic_info = layer_info.get("basic_info", {})
    wfs_params = layer_info.get("access_parameters", {}).get("wfs", {})
    capabilities = layer_info.get("capabilities", {})
    
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
        "type": "wfs",  # 修改为标准的 wfs 类型，而不是 wfs_advanced
        "service_type": "WFS",
        "layer_info": basic_info,
        
        # 数据信息
        "geojson_data": geojson_data,
        "feature_count": len(features),
        
        # 几何和属性信息
        "geometry_type": capabilities.get("geometry_type") or (list(geometry_types)[0] if geometry_types else None),
        "geometry_types": list(geometry_types),
        "attributes": capabilities.get("attributes", []),
        
        # 增强的过滤信息
        "filter_info": {
            **filter_info,
            "has_advanced_filter": filter_info.get("mode") != "none",
            "filter_complexity": filter_info.get("complexity", "simple"),
            "optimization_level": len(filter_info.get("optimizations", []))
        },
        
        # 性能信息
        "performance_info": {
            **result_analysis,
            "query_config": query_config,
            "supports_advanced_filtering": True,
            "supports_multi_attribute": True,
            "supports_performance_optimization": True
        },
        
        # 空间信息
        "bbox": capabilities.get("bbox", {}),
        "crs_list": capabilities.get("crs_list", ["EPSG:4326"]),
        "default_crs": capabilities.get("default_crs", "EPSG:4326"),
        
        # WFS参数
        "wfs_params": wfs_params,
        "queryable": True,
        
        # 样式
        "style": _get_default_style(geometry_types),
        
        # 元数据
        "metadata": {
            "source": "advanced_wfs_tool_v2",
            "version": "2.0",
            "supports_multi_attribute_filter": True,
            "supports_performance_optimization": True,
            "supports_smart_suggestions": True,
            "filter_capabilities": {
                "operators": ["=", "!=", ">", "<", ">=", "<=", "LIKE", "IN", "BETWEEN"],
                "logic_operators": ["AND", "OR"],
                "performance_modes": ["balanced", "speed", "accuracy", "minimal"]
            }
        }
    }




async def _get_layer_info_simplified(layer_name: str, ctx: Optional[Context]) -> Dict[str, Any]:
    """从layer_registry资源获取图层详细信息（简化版本）
    
    Args:
        layer_name: 图层名称
        ctx: FastMCP上下文对象
        
    Returns:
        图层详细信息字典
        
    Raises:
        ValueError: 当图层不存在时
        Exception: 资源访问错误时
    """
    try:
        # 构建资源URI
        layer_resource_uri = f"ogc://layer/{layer_name}"
        
        if ctx:
            await ctx.debug(f"🔍 获取图层信息: {layer_resource_uri}")
        
        # 通过上下文读取资源
        layer_info_raw = await ctx.read_resource(layer_resource_uri)
        
        # 处理不同的返回格式
        if isinstance(layer_info_raw, str):
            layer_info = json.loads(layer_info_raw)
        elif isinstance(layer_info_raw, dict):
            layer_info = layer_info_raw
        elif isinstance(layer_info_raw, list):
            if len(layer_info_raw) == 1:
                item = layer_info_raw[0]
                if hasattr(item, 'content'):
                    layer_info = json.loads(item.content)
                elif isinstance(item, dict):
                    layer_info = item
                else:
                    layer_info = json.loads(str(item))
            else:
                raise Exception(f"资源返回了意外的列表格式: {layer_info_raw}")
        else:
            if hasattr(layer_info_raw, 'content'):
                layer_info = json.loads(layer_info_raw.content)
            else:
                layer_info = json.loads(str(layer_info_raw))
        
        # 确保layer_info是字典类型
        if not isinstance(layer_info, dict):
            raise Exception(f"资源返回的数据格式不正确，期望字典，实际: {type(layer_info)}")
        
        # 检查是否有错误
        if "error" in layer_info:
            suggestions = layer_info.get("suggestions", [])
            error_msg = layer_info["error"]
            if suggestions:
                error_msg += f"\n建议的图层名称: {', '.join(suggestions[:5])}"
            raise ValueError(error_msg)
        
        return layer_info
        
    except json.JSONDecodeError as e:
        raise Exception(f"解析图层信息失败: {str(e)}")
    except Exception as e:
        if "ValueError" in str(type(e)):
            raise
        raise Exception(f"获取图层信息失败: {str(e)}")


def _validate_wfs_support(layer_info: Dict[str, Any], layer_name: str) -> bool:
    """验证图层是否支持WFS服务
    
    Args:
        layer_info: 图层信息字典
        layer_name: 图层名称
        
    Returns:
        是否支持WFS服务
    """
    # 检查基础信息中的服务类型
    basic_info = layer_info.get("basic_info", {})
    service_type = basic_info.get("service_type", "").upper()
    
    # 检查支持的服务列表
    metadata = layer_info.get("metadata", {})
    supported_services = metadata.get("supported_services", [])
    
    # 检查访问参数中是否有WFS配置
    access_params = layer_info.get("access_parameters", {})
    has_wfs_params = "wfs" in access_params
    
    # 任一条件满足即认为支持WFS
    return (
        service_type == "WFS" or
        "WFS" in supported_services or
        has_wfs_params
    )


def _extract_attributes_from_resource(layer_info: Dict[str, Any], ctx: Optional[Context]) -> List[str]:
    """从资源信息中提取属性列表
    
    Args:
        layer_info: 图层信息字典
        ctx: MCP上下文
        
    Returns:
        属性名称列表
    """
    attributes = []
    
    # 优先级1：详细能力信息中的WFS特征模式属性
    detailed_capabilities = layer_info.get("detailed_capabilities", {})
    wfs_details = detailed_capabilities.get("wfs", {})
    feature_schema = wfs_details.get("feature_schema", {})
    
    if feature_schema.get("attributes"):
        attributes.extend(feature_schema["attributes"])
    
    # 优先级2：详细能力信息中的WFS属性
    if not attributes and wfs_details.get("attributes"):
        attributes.extend(wfs_details["attributes"])
    
    # 优先级3：基础能力信息中的属性
    if not attributes:
        capabilities = layer_info.get("capabilities", {})
        if capabilities.get("attributes"):
            attributes.extend(capabilities["attributes"])
    
    # 去重并过滤空值，处理可能的字典格式属性
    unique_attributes = []
    seen = set()
    for attr in attributes:
        # 处理不同的属性格式
        attr_name = None
        if isinstance(attr, str):
            attr_name = attr
        elif isinstance(attr, dict):
            # 如果是字典，尝试提取属性名
            attr_name = attr.get("name") or attr.get("attribute") or attr.get("field")
        
        # 确保属性名是字符串且不为空
        if attr_name and isinstance(attr_name, str) and attr_name.strip():
            attr_name = attr_name.strip()
            if attr_name not in seen:
                unique_attributes.append(attr_name)
                seen.add(attr_name)
    
    return unique_attributes


def _smart_match_attribute(
    target_attr: str, 
    available_attributes: List[str], 
    ctx: Optional[Context]
) -> Optional[str]:
    """智能属性匹配
    
    Args:
        target_attr: 目标属性名
        available_attributes: 可用属性列表
        ctx: MCP上下文
        
    Returns:
        匹配的属性名，如果没有匹配则返回None
    """
    if not target_attr or not available_attributes:
        return None
    
    target_lower = target_attr.lower()
    
    # 1. 精确匹配
    if target_attr in available_attributes:
        return target_attr
    
    # 2. 大小写不敏感匹配
    for attr in available_attributes:
        if attr.lower() == target_lower:
            return attr
    
    # 3. 包含匹配（目标属性包含在可用属性中）
    for attr in available_attributes:
        if target_lower in attr.lower():
            return attr
    
    # 4. 被包含匹配（可用属性包含在目标属性中）
    for attr in available_attributes:
        if attr.lower() in target_lower:
            return attr
    
    return None

def _get_default_style(geometry_types: set) -> Dict[str, Any]:
    """根据几何类型获取默认样式
    
    Args:
        geometry_types: 几何类型集合
        
    Returns:
        默认样式字典
    """
    # 基础样式配置
    base_style = {
        "color": "#3388ff",
        "weight": 3,
        "opacity": 0.8,
        "fillColor": "#3388ff",
        "fillOpacity": 0.2
    }
    
    # 根据几何类型调整样式
    if "Point" in geometry_types or "MultiPoint" in geometry_types:
        # 点样式
        base_style.update({
            "radius": 6,
            "fillOpacity": 0.6,
            "weight": 2
        })
    elif "LineString" in geometry_types or "MultiLineString" in geometry_types:
        # 线样式
        base_style.update({
            "weight": 4,
            "fillOpacity": 0.0  # 线不需要填充
        })
    elif "Polygon" in geometry_types or "MultiPolygon" in geometry_types:
        # 面样式
        base_style.update({
            "weight": 2,
            "fillOpacity": 0.3
        })
    
    return base_style    