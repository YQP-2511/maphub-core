"""管理工具模块

提供图层管理相关的工具函数，包括注册、列表、删除等
"""

import logging
from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from pydantic import Field
from typing_extensions import Annotated

from ..services.layer_service import (
    register_ogc_layers,
    list_registered_layers,
    delete_layer_resource
)

logger = logging.getLogger(__name__)

# 创建管理工具子服务器
management_server = FastMCP(name="图层管理服务")


@management_server.tool
async def register_ogc_service_layers(
    service_urls: Annotated[List[str], Field(description="OGC服务URL列表")],
    service_name: Annotated[Optional[str], Field(description="服务名称（可选）")] = None,
    service_type: Annotated[Optional[str], Field(description="服务类型：WMS或WFS（可选，不提供则自动检测）")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """注册OGC服务图层
    
    解析OGC服务的能力文档，提取图层信息并注册到资源列表中。
    支持WMS和WFS服务的自动检测和解析。
    
    Args:
        service_urls: OGC服务URL列表
        service_name: 服务名称（可选）
        service_type: 服务类型，WMS或WFS（可选，不提供则自动检测）
        ctx: MCP上下文对象
        
    Returns:
        注册结果字典，包含成功和失败的统计信息
    """
    return await register_ogc_layers(service_urls, service_name, service_type, ctx)


@management_server.tool
async def list_layer_resources(
    service_type: Annotated[Optional[str], Field(description="按服务类型筛选（WMS/WFS）")] = None,
    service_name: Annotated[Optional[str], Field(description="按服务名称筛选")] = None,
    layer_name: Annotated[Optional[str], Field(description="按图层名称筛选")] = None,
    limit: Annotated[int, Field(description="返回结果数量限制", ge=1, le=1000)] = 100,
    offset: Annotated[int, Field(description="结果偏移量", ge=0)] = 0,
    ctx: Context = None
) -> Dict[str, Any]:
    """列出已注册的图层资源
    
    查询已注册的OGC图层资源，支持按服务类型、服务名称、图层名称进行筛选。
    
    Args:
        service_type: 按服务类型筛选（可选）
        service_name: 按服务名称筛选（可选）
        layer_name: 按图层名称筛选（可选）
        limit: 返回结果数量限制
        offset: 结果偏移量
        ctx: MCP上下文对象
        
    Returns:
        图层资源列表和统计信息
    """
    return await list_registered_layers(service_type, service_name, layer_name, limit, offset, ctx)


@management_server.tool
async def delete_layer(
    resource_id: Annotated[str, Field(description="图层资源ID")],
    ctx: Context = None
) -> Dict[str, Any]:
    """删除图层资源
    
    从资源列表中删除指定的图层资源。
    
    Args:
        resource_id: 图层资源ID
        ctx: MCP上下文对象
        
    Returns:
        删除结果
    """
    return await delete_layer_resource(resource_id, ctx)