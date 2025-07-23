"""图层资源模块

提供图层相关的MCP资源，包括图层列表和模板
"""

import logging
from typing import Dict, Any
from fastmcp import FastMCP, Context

from ..database import get_layer_repository, LayerResourceQuery
from ..utils.ogc_parser import get_ogc_parser

logger = logging.getLogger(__name__)

# 创建图层资源子服务器
layer_resource_server = FastMCP(name="图层资源服务")


@layer_resource_server.resource("ogc://layers/list")
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


@layer_resource_server.resource("ogc://layers/{layer_name}/template")
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
                template["wfs_parameters"] = {
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetFeature",
                    "typeNames": layer.layer_name,
                    "maxFeatures": 100,
                    "outputFormat": "application/json"
                }
                
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