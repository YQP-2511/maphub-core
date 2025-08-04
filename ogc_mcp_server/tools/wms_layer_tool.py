"""WMS图层添加工具

基于FastMCP最佳实践设计的WMS图层添加工具
充分利用layer_registry资源提供的图层信息，避免重复处理
专门用于添加WMS（地图图像）图层到可视化列表

工具功能：
- 通过layer_registry资源获取图层详细信息
- 验证图层WMS服务支持
- 创建增强的WMS图层对象
- 添加到全局图层列表供可视化使用
"""

import json
import logging
from typing import Dict, Any
from fastmcp import FastMCP, Context
from pydantic import Field
from typing_extensions import Annotated

logger = logging.getLogger(__name__)

# 创建WMS图层工具服务器
wms_layer_server = FastMCP(name="WMS图层添加工具")

# 导入全局图层存储（与visualization_tools共享）
from . import visualization_tools


@wms_layer_server.tool
async def add_wms_layer(
    layer_name: Annotated[str, Field(description="WMS图层名称")],
    layer_title: Annotated[str, Field(description="图层显示标题，可选，默认使用图层名称")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """添加WMS图层到可视化列表
    
    专门用于添加WMS（地图图像）图层，适合：
    - 底图和背景图层  
    - 栅格数据可视化
    - 大范围地理数据展示
    
    通过layer_registry资源获取图层的完整信息，包括：
    - WMS访问参数和服务URL
    - 图层边界框和坐标系信息
    - 样式和格式支持信息
    - 动态边界框等增强功能
    
    Args:
        layer_name: WMS图层名称，必须是layer_registry中存在的图层
        layer_title: 图层显示标题，可选，默认使用图层名称
        ctx: FastMCP上下文对象，用于访问资源和日志记录
        
    Returns:
        添加结果和当前图层列表状态的字典
        
    Raises:
        ValueError: 当图层不存在或不支持WMS服务时
        Exception: 其他处理错误
    """
    try:
        if ctx:
            await ctx.info(f"正在添加WMS图层: {layer_name}")
        
        # 通过layer_registry资源获取图层详细信息
        layer_info = await _get_layer_from_registry_resource(layer_name, ctx)
        
        # 验证图层支持WMS服务
        wms_params = layer_info.get("access_parameters", {}).get("wms")
        if not wms_params or wms_params is False:
            supported_services = layer_info.get("metadata", {}).get("supported_services", [])
            raise ValueError(
                f"图层 '{layer_name}' 不支持WMS服务。"
                f"支持的服务类型: {', '.join(supported_services) if supported_services else '无'}"
            )
        
        # 创建增强的WMS图层对象
        wms_layer = _create_enhanced_wms_layer(layer_info, layer_title or layer_name)
        
        # 添加到全局图层列表
        visualization_tools._current_layers.append(wms_layer)
        
        if ctx:
            await ctx.info(f"✅ WMS图层 {layer_name} 添加成功，当前共 {len(visualization_tools._current_layers)} 个图层")
        
        return {
            "success": True,
            "message": f"✅ WMS图层 '{layer_name}' 添加成功",
            "layer_info": {
                "name": layer_name,
                "title": wms_layer["title"],
                "type": "wms",
                "geometry_type": wms_layer.get("geometry_type"),
                "queryable": wms_layer.get("queryable", False)
            },
            "current_layer_count": len(visualization_tools._current_layers)
        }
        
    except Exception as e:
        error_msg = f"添加WMS图层失败: {str(e)}"
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
    """从layer_registry资源获取图层详细信息 - 包含图层发现功能
    
    先读取图层列表资源进行图层发现，然后读取详细资源
    这样AI可以了解所有可用图层，提供更好的用户体验
    
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
        # 第一步：读取图层列表资源进行图层发现
        if ctx:
            await ctx.debug(f"🔍 开始图层发现 - 读取图层列表资源")
        
        try:
            layers_list_content = await ctx.read_resource("ogc://layers")
            
            # 处理图层列表内容
            if isinstance(layers_list_content, list) and len(layers_list_content) > 0:
                content_item = layers_list_content[0]
                if hasattr(content_item, 'text'):
                    layers_data = json.loads(content_item.text)
                elif hasattr(content_item, 'content'):
                    layers_data = json.loads(content_item.content)
                elif isinstance(content_item, dict):
                    layers_data = content_item
                else:
                    layers_data = json.loads(str(content_item))
            elif isinstance(layers_list_content, dict):
                layers_data = layers_list_content
            else:
                layers_data = json.loads(str(layers_list_content))
            
            # 提取图层列表
            available_layers = layers_data.get("layers", [])
            total_layers = layers_data.get("total", len(available_layers))
            
            if ctx:
                await ctx.info(f"📋 发现 {total_layers} 个可用图层")
                
                # 显示部分图层名称供参考
                layer_names = [layer.get("layer_name", "") for layer in available_layers[:10] if layer.get("layer_name")]
                if layer_names:
                    await ctx.debug(f"🏷️ 部分可用图层: {', '.join(layer_names)}")
                    
                # 检查目标图层是否在列表中
                target_layer_found = any(layer.get("layer_name") == layer_name for layer in available_layers)
                if target_layer_found:
                    await ctx.info(f"✅ 目标图层 '{layer_name}' 在可用图层列表中")
                else:
                    await ctx.warning(f"⚠️ 目标图层 '{layer_name}' 不在当前可用图层列表中")
                    
        except Exception as e:
            if ctx:
                await ctx.warning(f"⚠️ 图层发现失败，继续尝试直接访问: {str(e)}")
        
        # 第二步：读取具体图层的详细资源
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


def _create_enhanced_wms_layer(layer_info: Dict[str, Any], title: str) -> Dict[str, Any]:
    """从资源信息创建增强的WMS图层对象
    
    充分利用layer_registry提供的增强信息，包括：
    - 基础图层信息和服务参数
    - 动态边界框和坐标系信息  
    - 样式和格式支持信息
    - WMS特定的增强功能
    
    Args:
        layer_info: 从layer_registry资源获取的图层信息
        title: 图层显示标题
        
    Returns:
        增强的WMS图层对象字典
    """
    basic_info = layer_info.get("basic_info", {})
    wms_params = layer_info.get("access_parameters", {}).get("wms", {})
    capabilities = layer_info.get("capabilities", {})
    detailed_capabilities = layer_info.get("detailed_capabilities", {})
    
    # 获取WMS特定的详细信息
    wms_details = detailed_capabilities.get("wms", {})
    
    # 构建增强的WMS图层对象
    wms_layer = {
        # 基础信息
        "name": basic_info.get("layer_name", ""),
        "title": title,
        "type": "wms",
        "service_type": basic_info.get("service_type", "WMS"),
        "layer_info": basic_info,
        
        # WMS服务信息
        "wms_url": basic_info.get("service_url", ""),
        "wms_params": wms_params,
        
        # 空间信息（优先使用详细能力信息）
        "bbox": wms_details.get("bbox") or capabilities.get("bbox", {}),
        "crs_list": wms_details.get("crs_list") or capabilities.get("crs_list", ["EPSG:4326"]),
        "default_crs": wms_details.get("default_crs") or capabilities.get("default_crs", "EPSG:4326"),
        
        # 增强功能信息
        "dynamic_bbox": wms_details.get("dynamic_bbox"),
        "bbox_source": "dynamic" if wms_details.get("dynamic_bbox") else "static",
        
        # 样式和格式信息
        "styles": wms_details.get("styles", []),
        "formats": wms_params.get("formats", ["image/png"]),
        "default_format": wms_params.get("format", "image/png"),
        "default_style": wms_params.get("default_style", ""),
        
        # WMS特定增强信息
        "wms_specific": wms_details.get("wms_specific", {}),
        "queryable": wms_details.get("queryable", False),
        "opaque": wms_details.get("opaque", False),
        "cascaded": wms_details.get("cascaded", 0),
        
        # 元数据
        "metadata": {
            "source": "layer_registry_resource",
            "has_detailed_capabilities": bool(wms_details),
            "parsing_status": layer_info.get("metadata", {}).get("parsing_status", {}),
            "last_updated": layer_info.get("metadata", {}).get("last_updated")
        }
    }
    
    return wms_layer