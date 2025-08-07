"""管理工具模块

提供核心的图层管理工具
采用资源驱动设计，通过MCP资源获取图层信息，专注于管理操作
包含功能：批量注册OGC服务、列出图层、删除图层、更新图层信息
"""

import logging
import json
from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from pydantic import Field
from typing_extensions import Annotated

from ..services.layer_service import (
    register_ogc_layers,
    delete_layer_resource,
    update_layer_resource
)

logger = logging.getLogger(__name__)

# 创建管理工具服务器
management_server = FastMCP(name="OGC图层管理")


@management_server.tool
async def register_ogc_services(
    service_urls: Annotated[List[str], Field(description="OGC服务URL列表")],
    service_name: Annotated[Optional[str], Field(description="服务名称（可选，适用于所有服务）")] = None,
    service_type: Annotated[Optional[str], Field(description="服务类型：WMS、WFS或WMTS（可选，适用于所有服务）")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """注册和添加OGC地理数据服务
    
    批量注册OGC地理数据服务，包括地图服务、要素服务和瓦片服务。
    支持自动发现和解析WMS、WFS、WMTS服务的图层信息。
    用于添加新的地理数据源，扩展可用的地理数据集合。
    
    关键词：注册、添加、导入、地理数据、地图服务、数据源
    
    Args:
        service_urls: OGC服务URL列表
        service_name: 服务名称（可选，适用于所有服务）
        service_type: 服务类型，WMS、WFS或WMTS（可选，适用于所有服务）
        ctx: MCP上下文对象
        
    Returns:
        注册结果字典，包含成功和失败的统计信息
    """
    if ctx:
        await ctx.info(f"开始注册 {len(service_urls)} 个OGC服务")
    
    # 执行注册操作
    result = await register_ogc_layers(service_urls, service_name, service_type, ctx)
    
    if ctx:
        # 注册完成后，提示用户可以通过资源查看结果
        await ctx.info("注册完成！可以通过 ogc://layers 资源查看所有已注册的图层")
    
    return result


@management_server.tool
async def search_and_list_geographic_data(
    ctx: Context = None
) -> Dict[str, Any]:
    """列出所有可用的地理数据图层
    
    获取系统中所有已注册的地理数据图层，供AI了解可用的图层资源。
    自动合并同名图层的不同服务类型，避免重复显示。
    
    关键词：搜索、查找、浏览、发现、探索、数据、图层、地理数据
    
    Args:
        ctx: MCP上下文对象
        
    Returns:
        所有地理数据图层列表，按图层名称去重并显示支持的服务类型
    """
    try:
        # 直接读取图层资源
        layers_resource_result = await ctx.read_resource("ogc://layers")
        
        if not layers_resource_result or not layers_resource_result[0].content:
            return {"error": "无法获取图层列表资源", "layers": []}
        
        layers_content = layers_resource_result[0].content
        
        # 处理资源数据
        if isinstance(layers_content, str):
            layers_data = json.loads(layers_content)
        else:
            layers_data = layers_content
        
        # 如果有错误，直接返回
        if "error" in layers_data:
            return layers_data
        
        # 合并同名图层的不同服务类型
        merged_layers = {}
        original_layers = layers_data.get("layers", [])
        
        for layer in original_layers:
            layer_name = layer.get("layer_name")
            service_type = layer.get("service_type", "").upper()
            
            if layer_name not in merged_layers:
                # 创建新的合并图层记录
                merged_layers[layer_name] = {
                    "layer_name": layer_name,
                    "layer_title": layer.get("layer_title", layer_name),
                    "layer_abstract": layer.get("layer_abstract", ""),
                    "service_name": layer.get("service_name", ""),
                    "service_url": layer.get("service_url", ""),
                    "supported_services": [service_type] if service_type else [],
                    "primary_service": service_type,
                    "resource_id": layer.get("resource_id"),
                    "created_at": layer.get("created_at"),
                    "updated_at": layer.get("updated_at"),
                    "service_records": {service_type: layer} if service_type else {}
                }
            else:
                # 合并到现有记录
                if service_type and service_type not in merged_layers[layer_name]["supported_services"]:
                    merged_layers[layer_name]["supported_services"].append(service_type)
                    merged_layers[layer_name]["service_records"][service_type] = layer
        
        # 转换为列表并添加服务能力说明
        merged_layer_list = []
        for layer_name, layer_info in merged_layers.items():
            services = layer_info["supported_services"]
            layer_info["service_capabilities"] = {
                "supports_wms": "WMS" in services,
                "supports_wfs": "WFS" in services,
                "supports_wmts": "WMTS" in services,
                "total_services": len(services)
            }
            layer_info["usage_note"] = f"支持 {', '.join(services)} 服务" if services else "服务类型未知"
            merged_layer_list.append(layer_info)
        
        # 构建返回结果
        result = {
            "layers": merged_layer_list,
            "total_unique_layers": len(merged_layer_list),
            "total_service_records": len(original_layers),
            "summary": {
                "unique_layers": len(merged_layer_list),
                "service_records": len(original_layers),
                "note": "已自动合并同名图层的不同服务类型"
            },
            "usage_instructions": {
                "wfs_filtering": "对于支持WFS的图层，先调用get_wfs_layer_attributes获取属性信息",
                "layer_selection": "使用layer_name字段作为图层标识符",
                "service_check": "查看supported_services了解图层支持的服务类型"
            }
        }
        
        return result
        
    except Exception as e:
        logger.error(f"获取图层列表失败: {e}")
        return {"error": str(e), "layers": []}


@management_server.tool
async def get_wfs_layer_attributes(
    layer_name: Annotated[str, Field(description="WFS图层名称")],
    ctx: Context = None
) -> Dict[str, Any]:
    """获取WFS图层的属性信息和示例值
    
    **重要：在使用WFS过滤工具之前必须先调用此工具！**
    
    专门用于获取WFS图层的属性列表和示例值，帮助AI了解可用的过滤条件。
    返回准确的属性名称、数据类型和真实的示例值，确保WFS过滤查询使用正确的参数。
    自动处理同名图层的多服务类型情况，智能识别WFS服务能力。
    
    使用场景：
    1. 在调用add_wfs_layer工具进行过滤查询之前
    2. 了解图层包含哪些可过滤的属性
    3. 获取属性的真实值，避免使用不存在的过滤值
    
    工作流程：
    1. 先调用此工具获取图层属性信息
    2. 根据返回的属性名称和示例值构建过滤条件
    3. 再调用add_wfs_layer工具进行实际的数据获取
    
    关键词：WFS属性、过滤条件、属性值、数据类型、必须先调用
    
    Args:
        layer_name: WFS图层名称
        ctx: MCP上下文对象
        
    Returns:
        WFS图层的属性信息，包含属性名称、类型和真实示例值
    """
    try:
        # 读取图层详细资源
        layer_resource_result = await ctx.read_resource(f"ogc://layer/{layer_name}")
        
        if not layer_resource_result or not layer_resource_result[0].content:
            return {
                "error": f"无法获取图层 '{layer_name}' 的详细信息",
                "layer_name": layer_name,
                "success": False
            }
        
        layer_content = layer_resource_result[0].content
        
        # 处理资源数据
        if isinstance(layer_content, str):
            layer_data = json.loads(layer_content)
        else:
            layer_data = layer_content
        
        # 检查是否有错误信息
        if isinstance(layer_data, dict) and "error" in layer_data:
            return {
                "error": layer_data["error"],
                "layer_name": layer_name,
                "success": False,
                "suggestions": layer_data.get("suggestions", [])
            }
        
        # 检查图层是否支持WFS服务
        supported_services = []
        
        # 从metadata中获取支持的服务类型
        if "metadata" in layer_data and "supported_services" in layer_data["metadata"]:
            supported_services = layer_data["metadata"]["supported_services"]
        
        # 如果metadata中没有，尝试从basic_info中获取
        if not supported_services and "basic_info" in layer_data:
            service_type_str = layer_data["basic_info"].get("service_type", "")
            if service_type_str:
                # 处理逗号分隔的服务类型字符串
                supported_services = [s.strip().upper() for s in service_type_str.split(',')]
        
        # 检查是否支持WFS
        supports_wfs = "WFS" in [s.upper() for s in supported_services]
        
        if not supports_wfs:
            return {
                "error": f"图层 '{layer_name}' 不支持WFS服务",
                "layer_name": layer_name,
                "success": False,
                "supported_services": supported_services,
                "message": f"该图层支持的服务类型: {', '.join(supported_services) if supported_services else '未知'}",
                "suggestion": "请选择支持WFS服务的图层，或使用其他服务类型的工具"
            }
        
        # 提取WFS属性信息
        attributes = []
        sample_data = {}
        
        # 从detailed_capabilities中获取WFS详细信息
        if "detailed_capabilities" in layer_data and "wfs" in layer_data["detailed_capabilities"]:
            wfs_details = layer_data["detailed_capabilities"]["wfs"]
            attributes = wfs_details.get("attributes", [])
            sample_data = wfs_details.get("sample_data", {})
        
        # 如果detailed_capabilities中没有，尝试从capabilities中获取
        if not attributes and "capabilities" in layer_data:
            attributes = layer_data["capabilities"].get("attributes", [])
        
        if not attributes:
            return {
                "layer_name": layer_name,
                "service_type": "WFS",
                "supported_services": supported_services,
                "attributes": [],
                "success": True,
                "message": "该WFS图层暂无可用的属性信息，可以尝试不使用过滤条件获取数据",
                "filter_ready": False,
                "suggestion": "建议先调用add_wfs_layer工具获取完整数据，查看实际的属性结构"
            }
        
        # 构建详细的属性信息
        attribute_info = []
        for attr in attributes:
            attr_name = attr.get("name")
            attr_type = attr.get("type", "unknown")
            
            # 从示例数据中提取该属性的真实值
            sample_values = []
            if sample_data and "features" in sample_data:
                for feature in sample_data.get("features", [])[:10]:
                    properties = feature.get("properties", {})
                    if attr_name in properties:
                        value = properties[attr_name]
                        if value is not None and str(value).strip():
                            sample_values.append(str(value))
            
            # 去重并保持顺序
            unique_samples = []
            seen = set()
            for val in sample_values:
                if val not in seen:
                    unique_samples.append(val)
                    seen.add(val)
                if len(unique_samples) >= 8:  # 限制示例数量
                    break
            
            attribute_info.append({
                "name": attr_name,
                "type": attr_type,
                "sample_values": unique_samples,
                "has_samples": len(unique_samples) > 0,
                "usage_example": f"attribute_filter='{attr_name}', filter_values='{unique_samples[0]}'" if unique_samples else f"attribute_filter='{attr_name}'"
            })
        
        return {
            "layer_name": layer_name,
            "service_type": "WFS",
            "supported_services": supported_services,
            "success": True,
            "total_attributes": len(attributes),
            "attributes": attribute_info,
            "filter_ready": True,
            "usage_instructions": {
                "step1": "选择一个属性名称作为attribute_filter参数",
                "step2": "从sample_values中选择一个或多个值作为filter_values参数",
                "step3": "多个值用逗号分隔，如：'值1,值2,值3'",
                "step4": "然后调用add_wfs_layer工具进行实际的数据获取"
            },
            "ready_for_filtering": True,
            "message": f"✅ 找到 {len(attributes)} 个可用属性，已准备好进行WFS过滤查询"
        }
        
    except Exception as e:
        error_msg = f"获取WFS图层 '{layer_name}' 属性信息失败: {e}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "layer_name": layer_name,
            "success": False
        }