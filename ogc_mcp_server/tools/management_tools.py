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
    """搜索和查找所有可用的地理数据图层
    
    搜索、查找、浏览所有已注册的地理数据图层和数据集。
    返回完整的地理数据资源列表，包括所有类型的服务。
    用于数据发现、数据探索、图层查找、数据检索等场景。
    
    关键词：搜索、查找、浏览、发现、探索、数据、图层、地理数据、人口数据、统计数据
    适用场景：查看数据、寻找数据、数据情况、数据状况、数据概览
    
    Args:
        ctx: MCP上下文对象
        
    Returns:
        所有地理数据图层列表和统计信息
    """
    if ctx:
        await ctx.info("正在搜索所有可用的地理数据图层...")
    
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
        
        # 获取所有图层，不进行筛选
        all_layers = layers_data.get("layers", [])
        
        # 统计各类型数据
        type_stats = {}
        for layer in all_layers:
            service_type = layer.get("service_type", "Unknown")
            type_stats[service_type] = type_stats.get(service_type, 0) + 1
        
        # 构建返回结果
        result = {
            "layers": all_layers,
            "total_count": len(all_layers),
            "type_statistics": type_stats,
            "source": "ogc://layers resource",
            "search_completed": True,
            "data_discovery": f"发现 {len(all_layers)} 个可用的地理数据图层"
        }
        
        if ctx:
            await ctx.info(f"搜索完成：发现 {len(all_layers)} 个地理数据图层")
        
        logger.info(f"地理数据搜索完成: {len(all_layers)} 个图层")
        return result
        
    except Exception as e:
        error_msg = f"搜索地理数据失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        
        return {
            "error": error_msg,
            "layers": [],
            "total_count": 0
        }