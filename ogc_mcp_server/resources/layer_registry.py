"""
图层注册表资源

提供简单的数据端点，用于访问图层注册表信息
只包含两个核心资源：图层列表和单个图层详情
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastmcp import FastMCP,Context

from ..database.connection import DatabaseManager
from ..database.repository import LayerResourceRepository
from ..database.models import LayerResourceQuery
from ..services.ogc_parser import get_ogc_parser

# 配置日志
logger = logging.getLogger(__name__)

# 创建图层注册服务器
layer_registry_server = FastMCP("图层注册服务")


async def _get_all_layers() -> List[Dict[str, Any]]:
    """获取所有图层的基础信息
    
    Returns:
        图层列表
    """
    try:
        db_manager = DatabaseManager()
        repository = LayerResourceRepository(db_manager)
        # 使用10000的limit值获取所有图层
        query = LayerResourceQuery(limit=10000)
        layers = await repository.list_resources(query)
        return [layer.to_dict() for layer in layers]
    except Exception as e:
        logger.error(f"获取图层列表失败: {e}")
        return []


@layer_registry_server.resource("ogc://layers")
async def layers_list(ctx: Context = None) -> Dict[str, Any]:
    """图层列表资源
    
    返回所有已注册图层的基础信息列表
    
    Returns:
        图层列表数据
    """
    layers = await _get_all_layers()
    
    return {
        "total": len(layers),
        "layers": layers,
        "timestamp": datetime.now().isoformat()
    }


@layer_registry_server.resource("ogc://layer/{layer_name}")
async def layer_detail(ctx: Context, layer_name: str) -> str:
    """获取指定图层的详细信息
    
    仅支持精确匹配
    
    Args:
        ctx: 请求上下文
        layer_name: 图层名称
        
    Returns:
        图层详细信息的JSON字符串
    """
    try:
        # 从数据库获取图层基础信息
        db_manager = DatabaseManager()
        repository = LayerResourceRepository(db_manager)
        query = LayerResourceQuery(limit=10000)  # 获取所有图层
        layers = await repository.list_resources(query)
        
        # 精确匹配查找图层
        target_layer = None
        for layer in layers:
            layer_dict = layer.to_dict()
            if layer_dict.get('layer_name') == layer_name:
                target_layer = layer_dict
                logger.info(f"精确匹配找到图层: {layer_name}")
                break
        
        if not target_layer:
            # 提供可用图层的建议
            available_layers = [layer.to_dict().get('layer_name') for layer in layers[:10]]
            return json.dumps({
                "error": f"图层 '{layer_name}' 不存在",
                "layer_name": layer_name,
                "suggestions": available_layers,
                "total_available": len(layers),
                "note": "请使用精确的图层名称"
            }, ensure_ascii=False, indent=2)
        
        # 使用ogc_parser动态获取图层详细信息
        try:
            parser = await get_ogc_parser()
            
            # 动态获取OGC标准参数
            ogc_details = await parser.get_layer_details(
                service_url=target_layer['service_url'],
                service_type=target_layer['service_type'],
                layer_name=layer_name
            )
            
            # 构建完整的图层详细信息
            layer_details = {
                "layer_name": layer_name,
                "basic_info": {
                    "resource_id": target_layer.get('resource_id'),
                    "layer_name": target_layer['layer_name'],
                    "layer_title": ogc_details.get('title', target_layer.get('layer_title', layer_name)),
                    "layer_abstract": ogc_details.get('abstract', target_layer.get('layer_abstract')),
                    "service_type": target_layer['service_type'],
                    "service_url": target_layer['service_url'],
                    "service_name": target_layer.get('service_name'),
                    "keywords": ogc_details.get('keywords', []),
                    "created_at": target_layer.get('created_at'),
                    "updated_at": target_layer.get('updated_at')
                },
                "access_parameters": {
                    "wms": {
                        "service": "WMS",
                        "version": "1.3.0",
                        "request": "GetMap",
                        "layers": layer_name,
                        "bbox": ogc_details.get('bbox', {}).get('wgs84', [-180, -90, 180, 90]),
                        "crs": ogc_details.get('default_crs', 'EPSG:4326'),
                        "width": 256,
                        "height": 256,
                        "format": "image/png",
                        "styles": ogc_details.get('styles', [])
                    } if target_layer['service_type'].upper() in ['WMS', 'BOTH'] else None,
                    "wfs": {
                        "service": "WFS",
                        "version": "2.0.0",
                        "request": "GetFeature",
                        "typeNames": layer_name,
                        "srsName": ogc_details.get('default_crs', 'EPSG:4326'),
                        "bbox": ogc_details.get('bbox', {}).get('wgs84', [-180, -90, 180, 90]),
                        "maxFeatures": 1000,
                        "outputFormat": "application/json"
                    } if target_layer['service_type'].upper() in ['WFS', 'BOTH'] else None
                },
                "capabilities": {
                    "bbox": ogc_details.get('bbox'),
                    "crs_list": ogc_details.get('crs_list', ['EPSG:4326']),
                    "default_crs": ogc_details.get('default_crs', 'EPSG:4326'),
                    "queryable": ogc_details.get('queryable', False),
                    "geometry_type": ogc_details.get('geometry_type'),
                    "attributes": ogc_details.get('attributes', [])
                },
                # 新增：增强的详细信息部分
                "enhanced_details": {
                    "feature_schema": ogc_details.get('feature_schema'),  # WFS DescribeFeatureType 信息
                    "dynamic_bbox": ogc_details.get('dynamic_bbox'),      # 动态边界框信息
                    "styles_detailed": ogc_details.get('styles', []),     # 详细样式信息
                    "wms_specific": {
                        "opaque": ogc_details.get('opaque', False),
                        "cascaded": ogc_details.get('cascaded', 0)
                    } if target_layer['service_type'].upper() in ['WMS', 'BOTH'] else None
                },
                "metadata": {
                    "source": "dynamic_ogc_capabilities_enhanced",
                    "last_updated": datetime.now().isoformat(),
                    "ogc_compliant": True,
                    "capabilities_source": ogc_details.get('bbox', {}).get('source', 'capabilities'),
                    "has_feature_schema": bool(ogc_details.get('feature_schema')),
                    "has_dynamic_bbox": bool(ogc_details.get('dynamic_bbox')),
                    "primary_service": ogc_details.get('primary_service', target_layer['service_type'])
                }
            }
            
        except Exception as e:
            logger.warning(f"动态获取图层详细信息失败，使用备用参数: {e}")
            
            # 备用参数（当动态获取失败时）
            layer_details = {
                "layer_name": layer_name,
                "basic_info": {
                    "resource_id": target_layer.get('resource_id'),
                    "layer_name": target_layer['layer_name'],
                    "layer_title": target_layer.get('layer_title', layer_name),
                    "layer_abstract": target_layer.get('layer_abstract'),
                    "service_type": target_layer['service_type'],
                    "service_url": target_layer['service_url'],
                    "service_name": target_layer.get('service_name'),
                    "keywords": [],
                    "created_at": target_layer.get('created_at'),
                    "updated_at": target_layer.get('updated_at')
                },
                "access_parameters": {
                    "wms": {
                        "service": "WMS",
                        "version": "1.3.0",
                        "request": "GetMap",
                        "layers": layer_name,
                        "bbox": [-180, -90, 180, 90],
                        "crs": "EPSG:4326",
                        "width": 256,
                        "height": 256,
                        "format": "image/png",
                        "styles": []
                    } if target_layer['service_type'].upper() in ['WMS', 'BOTH'] else None,
                    "wfs": {
                        "service": "WFS",
                        "version": "2.0.0",
                        "request": "GetFeature",
                        "typeNames": layer_name,
                        "srsName": "EPSG:4326",
                        "bbox": [-180, -90, 180, 90],
                        "maxFeatures": 1000,
                        "outputFormat": "application/json"
                    } if target_layer['service_type'].upper() in ['WFS', 'BOTH'] else None
                },
                "capabilities": {
                    "bbox": {"wgs84": [-180, -90, 180, 90], "crs": "EPSG:4326"},
                    "crs_list": ["EPSG:4326"],
                    "default_crs": "EPSG:4326",
                    "queryable": False,
                    "geometry_type": None,
                    "attributes": []
                },
                "metadata": {
                    "source": "fallback_parameters",
                    "last_updated": datetime.now().isoformat(),
                    "ogc_compliant": True,
                    "note": "使用备用参数，建议检查服务连接"
                }
            }
        
        return json.dumps(layer_details, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"获取图层详细信息失败: {e}")
        return json.dumps({
            "error": f"获取图层详细信息失败: {str(e)}",
            "layer_name": layer_name
        }, ensure_ascii=False, indent=2)
