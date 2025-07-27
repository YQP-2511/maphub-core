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
    service_type: Annotated[Optional[str], Field(description="服务类型：WMS或WFS（可选，适用于所有服务）")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """批量注册OGC服务
    
    批量解析多个OGC服务的能力文档，提取图层信息并注册到资源列表中。
    支持WMS和WFS服务的自动检测和解析。
    注册完成后，新图层将自动出现在ogc://layers资源中。
    
    Args:
        service_urls: OGC服务URL列表
        service_name: 服务名称（可选，适用于所有服务）
        service_type: 服务类型，WMS或WFS（可选，适用于所有服务）
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
async def list_layers_from_resource(
    service_type_filter: Annotated[Optional[str], Field(description="按服务类型筛选（WMS/WFS）")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """通过资源列出已注册的图层
    
    使用资源驱动的方式获取图层列表，从ogc://layers资源读取数据。
    这是推荐的获取图层列表的方式，确保数据一致性。
    
    Args:
        service_type_filter: 按服务类型筛选（可选）
        ctx: MCP上下文对象
        
    Returns:
        图层资源列表和统计信息
    """
    if ctx:
        await ctx.info("正在从资源获取图层列表...")
    
    try:
        # 通过资源获取图层列表
        layers_resource_result = await ctx.read_resource("ogc://layers")
        
        # 修复：正确处理资源返回的数据结构
        if not layers_resource_result or not layers_resource_result[0].content:
            raise ValueError("无法获取图层列表资源")
        
        layers_content = layers_resource_result[0].content
        
        # 如果content是字符串，需要解析为JSON
        if isinstance(layers_content, str):
            layers_data = json.loads(layers_content)
        else:
            layers_data = layers_content
        
        # 检查是否包含错误信息
        if isinstance(layers_data, dict) and "error" in layers_data:
            raise ValueError(f"图层资源错误: {layers_data['error']}")
        
        # 应用筛选条件
        filtered_layers = layers_data.get("layers", [])
        if service_type_filter:
            filtered_layers = [
                layer for layer in filtered_layers 
                if layer.get("service_type", "").upper() == service_type_filter.upper()
            ]
        
        # 构建返回结果
        result = {
            "layers": filtered_layers,
            "total_count": len(filtered_layers),
            "filter_applied": {
                "service_type": service_type_filter
            },
            "source": "ogc://layers resource"
        }
        
        if ctx:
            await ctx.info(f"获取到 {len(filtered_layers)} 个图层资源")
        
        logger.info(f"通过资源获取图层列表完成: {len(filtered_layers)} 个图层")
        return result
        
    except Exception as e:
        error_msg = f"从资源获取图层列表失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        
        return {
            "error": error_msg,
            "layers": [],
            "total_count": 0
        }