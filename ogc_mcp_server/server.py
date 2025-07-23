"""OGC MCP服务模块

基于FastMCP框架提供OGC服务资源访问的MCP服务器，
支持WMS和WFS图层的动态注册、资源管理和空间数据访问功能
"""

import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from fastmcp import FastMCP, Context
from pydantic import Field
from typing_extensions import Annotated

from .database import init_database, close_database, get_layer_repository, LayerResourceQuery
from .tools.layer_registration import register_ogc_layers, list_registered_layers, delete_layer_resource
from .utils.ogc_parser import get_ogc_parser

# 配置日志
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    """服务器生命周期管理"""
    # 启动时的初始化操作
    logger.info("正在初始化OGC MCP服务器...")
    
    # 初始化数据库
    await init_database()
    logger.info("数据库初始化完成")
    
    logger.info("OGC MCP服务器启动完成")
    
    yield
    
    # 关闭时的清理操作
    logger.info("正在关闭OGC MCP服务器...")
    
    # 关闭数据库连接
    await close_database()
    logger.info("数据库连接已关闭")
    
    # 关闭OGC解析器
    parser = await get_ogc_parser()
    await parser.close()
    logger.info("OGC解析器已关闭")
    
    logger.info("OGC MCP服务器已关闭")


# 创建OGC MCP服务器实例 - 使用lifespan管理生命周期
mcp = FastMCP(name="OGC服务", lifespan=lifespan)


# ==================== MCP工具 ====================

@mcp.tool
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


@mcp.tool
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


@mcp.tool
async def get_wms_map(
    layer_name: Annotated[str, Field(description="WMS图层名称")],
    width: Annotated[int, Field(description="图像宽度", ge=100, le=2000)] = 800,
    height: Annotated[int, Field(description="图像高度", ge=100, le=2000)] = 600,
    bbox: Annotated[Optional[str], Field(description="边界框，格式：min_x,min_y,max_x,max_y")] = None,
    crs: Annotated[str, Field(description="坐标参考系统")] = "EPSG:4326",
    format: Annotated[str, Field(description="图像格式")] = "image/png",
    ctx: Context = None
) -> Dict[str, Any]:
    """获取WMS图层地图
    
    根据图层名称生成WMS GetMap请求URL，返回图层的预览链接。
    
    Args:
        layer_name: WMS图层名称
        width: 图像宽度
        height: 图像高度
        bbox: 边界框，格式：min_x,min_y,max_x,max_y（可选）
        crs: 坐标参考系统
        format: 图像格式
        ctx: MCP上下文对象
        
    Returns:
        包含地图URL和图层信息的字典
    """
    if ctx:
        await ctx.info(f"正在生成WMS图层地图: {layer_name}")
    
    try:
        # 获取图层资源信息
        repository = await get_layer_repository()
        
        # 查询图层资源
        query = LayerResourceQuery(layer_name=layer_name, service_type="WMS", limit=1)
        layers = await repository.list_resources(query)
        
        if not layers:
            raise ValueError(f"未找到WMS图层: {layer_name}")
        
        layer = layers[0]
        
        # 解析边界框
        bbox_coords = None
        if bbox:
            try:
                coords = [float(x.strip()) for x in bbox.split(',')]
                if len(coords) == 4:
                    bbox_coords = tuple(coords)
            except ValueError:
                raise ValueError("边界框格式错误，应为：min_x,min_y,max_x,max_y")
        
        # 如果没有提供边界框，使用图层的默认边界框
        if not bbox_coords and layer.bbox:
            bbox_coords = (layer.bbox.min_x, layer.bbox.min_y, layer.bbox.max_x, layer.bbox.max_y)
        
        # 生成GetMap URL
        parser = await get_ogc_parser()
        map_url = parser.get_wms_map_url(
            base_url=layer.service_url,
            layer_name=layer.layer_name,
            bbox=bbox_coords,
            width=width,
            height=height,
            crs=crs,
            format=format
        )
        
        result = {
            "layer_info": {
                "resource_id": layer.resource_id,
                "service_name": layer.service_name,
                "service_url": layer.service_url,
                "layer_name": layer.layer_name,
                "layer_title": layer.layer_title,
                "crs": layer.crs
            },
            "map_url": map_url,
            "parameters": {
                "width": width,
                "height": height,
                "bbox": bbox_coords,
                "crs": crs,
                "format": format
            }
        }
        
        if ctx:
            await ctx.info(f"WMS地图URL生成成功: {layer_name}")
        
        logger.info(f"WMS地图URL生成成功: {layer_name}")
        return result
        
    except Exception as e:
        error_msg = f"生成WMS地图失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


@mcp.tool
async def get_wfs_features(
    layer_name: Annotated[str, Field(description="WFS图层（要素类型）名称")],
    max_features: Annotated[int, Field(description="最大要素数量", ge=1, le=1000)] = 100,
    output_format: Annotated[str, Field(description="输出格式")] = "application/json",
    ctx: Context = None
) -> Dict[str, Any]:
    """获取WFS图层要素
    
    根据图层名称生成WFS GetFeature请求URL，返回要素数据的访问链接。
    
    Args:
        layer_name: WFS图层（要素类型）名称
        max_features: 最大要素数量
        output_format: 输出格式
        ctx: MCP上下文对象
        
    Returns:
        包含要素URL和图层信息的字典
    """
    if ctx:
        await ctx.info(f"正在生成WFS要素访问链接: {layer_name}")
    
    try:
        # 获取图层资源信息
        repository = await get_layer_repository()
        
        # 查询图层资源
        query = LayerResourceQuery(layer_name=layer_name, service_type="WFS", limit=1)
        layers = await repository.list_resources(query)
        
        if not layers:
            raise ValueError(f"未找到WFS图层: {layer_name}")
        
        layer = layers[0]
        
        # 生成GetFeature URL
        parser = await get_ogc_parser()
        feature_url = parser.get_wfs_feature_url(
            base_url=layer.service_url,
            type_name=layer.layer_name,
            max_features=max_features,
            output_format=output_format
        )
        
        result = {
            "layer_info": {
                "resource_id": layer.resource_id,
                "service_name": layer.service_name,
                "service_url": layer.service_url,
                "layer_name": layer.layer_name,
                "layer_title": layer.layer_title,
                "crs": layer.crs
            },
            "feature_url": feature_url,
            "parameters": {
                "max_features": max_features,
                "output_format": output_format
            }
        }
        
        if ctx:
            await ctx.info(f"WFS要素URL生成成功: {layer_name}")
        
        logger.info(f"WFS要素URL生成成功: {layer_name}")
        return result
        
    except Exception as e:
        error_msg = f"生成WFS要素URL失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


@mcp.tool
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


# ==================== MCP资源 ====================

@mcp.resource("ogc://layers/list")
async def layer_resources_list(ctx: Context = None) -> Dict[str, Any]:
    """图层资源列表
    
    提供所有已注册的OGC图层资源列表，支持动态更新。
    
    Returns:
        图层资源列表
    """
    if ctx:
        await ctx.info("正在获取图层资源列表")
    
    try:
        repository = await get_layer_repository()
        
        # 获取所有图层资源
        query = LayerResourceQuery(limit=1000, offset=0)
        layers = await repository.list_resources(query)
        total_count = await repository.count(query)
        
        # 按服务类型分组
        wms_layers = []
        wfs_layers = []
        
        for layer in layers:
            layer_dict = {
                "resource_id": layer.resource_id,
                "service_name": layer.service_name,
                "service_url": layer.service_url,
                "layer_name": layer.layer_name,
                "layer_title": layer.layer_title,
                "layer_abstract": layer.layer_abstract,
                "crs": layer.crs,
                "bbox": layer.bbox.to_dict() if layer.bbox else None,
                "created_at": layer.created_at.isoformat(),
                "updated_at": layer.updated_at.isoformat()
            }
            
            if layer.service_type == "WMS":
                wms_layers.append(layer_dict)
            elif layer.service_type == "WFS":
                wfs_layers.append(layer_dict)
        
        result = {
            "summary": {
                "total_layers": total_count,
                "wms_layers": len(wms_layers),
                "wfs_layers": len(wfs_layers)
            },
            "wms_layers": wms_layers,
            "wfs_layers": wfs_layers
        }
        
        if ctx:
            await ctx.info(f"图层资源列表获取成功，共 {total_count} 个图层")
        
        logger.info(f"图层资源列表获取成功，共 {total_count} 个图层")
        return result
        
    except Exception as e:
        error_msg = f"获取图层资源列表失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


@mcp.resource("ogc://layers/{layer_name}/template")
async def layer_template(layer_name: str, ctx: Context = None) -> Dict[str, Any]:
    """图层模板资源
    
    根据图层名称提供图层的详细信息和访问参数模板。
    
    Args:
        layer_name: 图层名称
        
    Returns:
        图层模板信息
    """
    if ctx:
        await ctx.info(f"正在获取图层模板: {layer_name}")
    
    try:
        repository = await get_layer_repository()
        
        # 查询图层资源
        query = LayerResourceQuery(layer_name=layer_name, limit=10)
        layers = await repository.list_resources(query)
        
        if not layers:
            raise ValueError(f"未找到图层: {layer_name}")
        
        # 构建图层模板
        templates = []
        parser = await get_ogc_parser()
        
        for layer in layers:
            template = {
                "layer_info": {
                    "resource_id": layer.resource_id,
                    "service_name": layer.service_name,
                    "service_url": layer.service_url,
                    "service_type": layer.service_type,
                    "layer_name": layer.layer_name,
                    "layer_title": layer.layer_title,
                    "layer_abstract": layer.layer_abstract,
                    "crs": layer.crs,
                    "bbox": layer.bbox.to_dict() if layer.bbox else None
                }
            }
            
            # 根据服务类型生成访问参数模板
            if layer.service_type == "WMS":
                # WMS访问参数模板
                bbox_coords = None
                if layer.bbox:
                    bbox_coords = (layer.bbox.min_x, layer.bbox.min_y, layer.bbox.max_x, layer.bbox.max_y)
                
                template["wms_parameters"] = {
                    "service": "WMS",
                    "version": "1.3.0",
                    "request": "GetMap",
                    "layers": layer.layer_name,
                    "styles": "",
                    "crs": layer.crs or "EPSG:4326",
                    "bbox": bbox_coords,
                    "width": 800,
                    "height": 600,
                    "format": "image/png"
                }
                
                # 生成示例URL
                template["example_url"] = parser.get_wms_map_url(
                    base_url=layer.service_url,
                    layer_name=layer.layer_name,
                    bbox=bbox_coords,
                    width=800,
                    height=600,
                    crs=layer.crs or "EPSG:4326",
                    format="image/png"
                )
                
            elif layer.service_type == "WFS":
                # WFS访问参数模板
                template["wfs_parameters"] = {
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetFeature",
                    "typeNames": layer.layer_name,
                    "maxFeatures": 100,
                    "outputFormat": "application/json"
                }
                
                # 生成示例URL
                template["example_url"] = parser.get_wfs_feature_url(
                    base_url=layer.service_url,
                    type_name=layer.layer_name,
                    max_features=100,
                    output_format="application/json"
                )
            
            templates.append(template)
        
        result = {
            "layer_name": layer_name,
            "found_layers": len(templates),
            "templates": templates
        }
        
        if ctx:
            await ctx.info(f"图层模板获取成功: {layer_name}，找到 {len(templates)} 个匹配图层")
        
        logger.info(f"图层模板获取成功: {layer_name}，找到 {len(templates)} 个匹配图层")
        return result
        
    except Exception as e:
        error_msg = f"获取图层模板失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


def get_ogc_mcp_server() -> FastMCP:
    """获取OGC MCP服务器实例
    
    用于依赖注入，提供OGC MCP服务器实例
    
    Returns:
        FastMCP: OGC MCP服务器实例
    """
    return mcp