"""WMTS图层添加工具

基于FastMCP最佳实践设计的WMTS图层添加工具
充分利用layer_registry资源提供的图层信息，避免重复处理
专门用于添加WMTS（瓦片地图）图层到可视化列表

工具功能：
- 通过layer_registry资源获取图层详细信息
- 验证图层WMTS服务支持
- 支持瓦片矩阵集选择
- 创建增强的WMTS图层对象
"""

import json
import logging
from typing import Dict, Any, Optional
from fastmcp import FastMCP, Context
from pydantic import Field
from typing_extensions import Annotated

logger = logging.getLogger(__name__)

# 创建WMTS图层工具服务器
wmts_layer_server = FastMCP(name="WMTS图层添加工具")

# 导入全局图层存储（与visualization_tools共享）
from . import visualization_tools


@wmts_layer_server.tool
async def add_wmts_layer(
    layer_name: Annotated[str, Field(description="WMTS图层名称")],
    layer_title: Annotated[str, Field(description="图层显示标题，可选，默认使用图层名称")] = None,
    tile_matrix_set: Annotated[Optional[str], Field(description="瓦片矩阵集名称，可选，默认自动选择最佳")] = None,
    style: Annotated[Optional[str], Field(description="图层样式名称，可选，默认使用默认样式")] = None,
    format: Annotated[Optional[str], Field(description="瓦片格式，可选，默认使用image/png")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """添加WMTS图层到可视化列表
    
    专门用于添加WMTS（瓦片地图）图层，适合：
    - 高性能底图显示
    - 预渲染的瓦片数据
    - 大比例尺地图浏览
    
    通过layer_registry资源获取图层的完整信息，包括：
    - WMTS访问参数和服务URL
    - 支持的瓦片矩阵集列表
    - 可用的样式和格式
    - 瓦片URL模板和资源URL
    
    支持灵活的配置选项：
    - 自动选择最佳瓦片矩阵集
    - 可指定特定的样式和格式
    - 智能默认值处理
    
    Args:
        layer_name: WMTS图层名称，必须是layer_registry中存在的图层
        layer_title: 图层显示标题，可选，默认使用图层名称
        tile_matrix_set: 瓦片矩阵集名称，可选，默认自动选择最佳
        style: 图层样式名称，可选，默认使用默认样式
        format: 瓦片格式，可选，默认使用image/png
        ctx: FastMCP上下文对象，用于访问资源和日志记录
        
    Returns:
        添加结果和当前图层列表状态的字典
        
    Raises:
        ValueError: 当图层不存在、不支持WMTS服务或参数无效时
        Exception: 其他处理错误
    """
    try:
        if ctx:
            await ctx.info(f"正在添加WMTS图层: {layer_name}")
        
        # 通过layer_registry资源获取图层详细信息
        layer_info = await _get_layer_from_registry_resource(layer_name, ctx)
        
        # 验证图层支持WMTS服务
        wmts_params = layer_info.get("access_parameters", {}).get("wmts")
        if not wmts_params or wmts_params is False:
            supported_services = layer_info.get("metadata", {}).get("supported_services", [])
            raise ValueError(
                f"图层 '{layer_name}' 不支持WMTS服务。"
                f"支持的服务类型: {', '.join(supported_services) if supported_services else '无'}"
            )
        
        # 验证和选择配置参数
        config = _validate_and_select_wmts_config(
            layer_info, tile_matrix_set, style, format, ctx
        )
        
        # 创建增强的WMTS图层对象
        wmts_layer = _create_enhanced_wmts_layer(
            layer_info, layer_title or layer_name, config
        )
        
        # 添加到全局图层列表
        visualization_tools._current_layers.append(wmts_layer)
        
        if ctx:
            await ctx.info(f"✅ WMTS图层 {layer_name} 添加成功，当前共 {len(visualization_tools._current_layers)} 个图层")
        
        return {
            "success": True,
            "message": f"✅ WMTS图层 '{layer_name}' 添加成功",
            "layer_info": {
                "name": layer_name,
                "title": wmts_layer["title"],
                "type": "wmts",
                "tile_matrix_set": wmts_layer.get("tile_matrix_set"),
                "style": wmts_layer.get("style_name")
            },
            "current_layer_count": len(visualization_tools._current_layers)
        }
        
    except Exception as e:
        error_msg = f"添加WMTS图层失败: {str(e)}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "layer_name": layer_name,
            "current_layer_count": len(visualization_tools._current_layers)
        }


async def _get_layer_from_registry_resource(layer_name: str, ctx: Context) -> Dict[str, Any]:
    """从layer_registry资源获取图层详细信息
    
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
        
        # 通过上下文读取资源
        layer_info_raw = await ctx.read_resource(layer_resource_uri)
        
        # 处理不同的返回格式
        if isinstance(layer_info_raw, str):
            # 如果是字符串，直接解析JSON
            layer_info = json.loads(layer_info_raw)
        elif isinstance(layer_info_raw, dict):
            # 如果已经是字典，直接使用
            layer_info = layer_info_raw
        elif isinstance(layer_info_raw, list):
            # 如果是列表，检查是否包含ReadResourceContents对象或图层数据
            if len(layer_info_raw) == 1:
                item = layer_info_raw[0]
                # 检查是否是ReadResourceContents对象
                if hasattr(item, 'content'):
                    # 从ReadResourceContents对象中提取内容
                    layer_info = json.loads(item.content)
                elif isinstance(item, dict):
                    layer_info = item
                else:
                    layer_info = json.loads(str(item))
            else:
                raise Exception(f"资源返回了意外的列表格式: {layer_info_raw}")
        else:
            # 检查是否是ReadResourceContents对象
            if hasattr(layer_info_raw, 'content'):
                layer_info = json.loads(layer_info_raw.content)
            else:
                # 尝试转换为字符串再解析
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


def _validate_and_select_wmts_config(
    layer_info: Dict[str, Any],
    tile_matrix_set: Optional[str],
    style: Optional[str], 
    format: Optional[str],
    ctx: Context
) -> Dict[str, Any]:
    """验证和选择WMTS配置参数
    
    Args:
        layer_info: 图层信息
        tile_matrix_set: 指定的瓦片矩阵集
        style: 指定的样式
        format: 指定的格式
        ctx: FastMCP上下文对象
        
    Returns:
        验证后的配置字典
        
    Raises:
        ValueError: 当参数无效时
    """
    wmts_params = layer_info.get("access_parameters", {}).get("wmts", {})
    detailed_capabilities = layer_info.get("detailed_capabilities", {})
    wmts_details = detailed_capabilities.get("wmts", {})
    
    # 获取可用选项
    available_matrix_sets = wmts_params.get("tile_matrix_sets", [])
    available_styles = wmts_params.get("styles", [])
    available_formats = wmts_params.get("formats", ["image/png"])
    
    config = {}
    
    # 选择瓦片矩阵集
    if tile_matrix_set:
        if tile_matrix_set not in available_matrix_sets:
            raise ValueError(
                f"瓦片矩阵集 '{tile_matrix_set}' 不可用。"
                f"可用选项: {', '.join(available_matrix_sets)}"
            )
        config["tile_matrix_set"] = tile_matrix_set
    else:
        # 自动选择最佳瓦片矩阵集
        config["tile_matrix_set"] = _select_best_tile_matrix_set(available_matrix_sets)
    
    # 选择样式
    if style:
        # 处理样式列表，兼容字符串和字典格式
        style_identifiers = []
        for s in available_styles:
            if isinstance(s, dict):
                style_identifiers.append(s.get("identifier", ""))
            else:
                style_identifiers.append(str(s))
        
        if style not in style_identifiers:
            raise ValueError(
                f"样式 '{style}' 不可用。"
                f"可用选项: {', '.join(style_identifiers)}"
            )
        config["style"] = style
    else:
        # 使用默认样式
        config["style"] = wmts_params.get("default_style", "")
    
    # 选择格式
    if format:
        if format not in available_formats:
            raise ValueError(
                f"格式 '{format}' 不可用。"
                f"可用选项: {', '.join(available_formats)}"
            )
        config["format"] = format
    else:
        # 使用默认格式
        config["format"] = wmts_params.get("default_format", "image/png")
    
    return config


def _select_best_tile_matrix_set(available_matrix_sets: list) -> str:
    """自动选择最佳的瓦片矩阵集
    
    Args:
        available_matrix_sets: 可用的瓦片矩阵集列表
        
    Returns:
        选择的瓦片矩阵集名称
    """
    if not available_matrix_sets:
        return "GoogleMapsCompatible"  # 默认值
    
    # 优先级顺序
    preferred_order = [
        "GoogleMapsCompatible",
        "EPSG:3857", 
        "EPSG:4326",
        "WebMercatorQuad",
        "WGS84"
    ]
    
    # 按优先级选择
    for preferred in preferred_order:
        if preferred in available_matrix_sets:
            return preferred
    
    # 如果没有匹配的，返回第一个可用的
    return available_matrix_sets[0]


def _create_enhanced_wmts_layer(
    layer_info: Dict[str, Any], 
    title: str,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """从资源信息创建增强的WMTS图层对象
    
    Args:
        layer_info: 从layer_registry资源获取的图层信息
        title: 图层显示标题
        config: 验证后的配置参数
        
    Returns:
        增强的WMTS图层对象字典
    """
    basic_info = layer_info.get("basic_info", {})
    wmts_params = layer_info.get("access_parameters", {}).get("wmts", {})
    capabilities = layer_info.get("capabilities", {})
    detailed_capabilities = layer_info.get("detailed_capabilities", {})
    
    # 获取WMTS特定的详细信息
    wmts_details = detailed_capabilities.get("wmts", {})
    
    # 构建增强的WMTS图层对象
    wmts_layer = {
        # 基础信息
        "name": basic_info.get("layer_name", ""),
        "title": title,
        "type": "wmts",
        "service_type": basic_info.get("service_type", "WMTS"),
        "layer_info": basic_info,
        
        # WMTS服务信息
        "wmts_url": basic_info.get("service_url", ""),
        "wmts_params": wmts_params,
        
        # 当前配置
        "current_config": config,
        "tile_matrix_set": config["tile_matrix_set"],
        "style": config["style"],
        "format": config["format"],
        
        # 可用选项
        "tile_matrix_sets": wmts_params.get("tile_matrix_sets", []),
        "styles": wmts_params.get("styles", []),
        "formats": wmts_params.get("formats", []),
        
        # 空间信息（优先使用详细能力信息）
        "bbox": wmts_details.get("bbox") or capabilities.get("bbox", {}),
        "crs_list": wmts_details.get("crs_list") or capabilities.get("crs_list", ["EPSG:4326"]),
        "default_crs": wmts_details.get("default_crs") or capabilities.get("default_crs", "EPSG:4326"),
        
        # WMTS特定信息
        "dimensions": wmts_params.get("dimensions", {}),
        "resource_urls": wmts_params.get("resource_urls", {}),
        "tile_url_template": wmts_details.get("tile_url_template"),
        
        # 瓦片信息
        "tile_size": wmts_details.get("tile_size", 256),
        "min_zoom": wmts_details.get("min_zoom", 0),
        "max_zoom": wmts_details.get("max_zoom", 18),
        
        # 增强功能信息
        "dynamic_bbox": wmts_details.get("dynamic_bbox"),
        "bbox_source": "dynamic" if wmts_details.get("dynamic_bbox") else "static",
        
        # 元数据
        "metadata": {
            "source": "layer_registry_resource",
            "has_detailed_capabilities": bool(wmts_details),
            "parsing_status": layer_info.get("metadata", {}).get("parsing_status", {}),
            "last_updated": layer_info.get("metadata", {}).get("last_updated"),
            "auto_selected_matrix_set": config["tile_matrix_set"] not in wmts_params.get("tile_matrix_sets", [])
        }
    }
    
    return wmts_layer