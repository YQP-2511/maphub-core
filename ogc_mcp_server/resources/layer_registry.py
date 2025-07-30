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
    
    支持同名不同服务类型的图层，合并WMS和WFS访问参数
    不进行动态检测，严格按照数据库记录提供访问参数
    
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
        
        # 查找所有同名的图层记录（可能有不同的服务类型）
        matching_layers = []
        for layer in layers:
            layer_dict = layer.to_dict()
            if layer_dict.get('layer_name') == layer_name:
                matching_layers.append(layer_dict)
        
        if not matching_layers:
            # 提供可用图层的建议
            available_layers = [layer.to_dict().get('layer_name') for layer in layers[:10]]
            return json.dumps({
                "error": f"图层 '{layer_name}' 不存在",
                "layer_name": layer_name,
                "suggestions": available_layers,
                "total_available": len(layers),
                "note": "请使用精确的图层名称"
            }, ensure_ascii=False, indent=2)
        
        logger.info(f"找到图层 {layer_name} 的 {len(matching_layers)} 个记录")
        
        # 分析支持的服务类型
        supports_wms = False
        supports_wfs = False
        wms_layer = None
        wfs_layer = None
        
        for layer_record in matching_layers:
            service_type = layer_record['service_type'].upper()
            if service_type == 'WMS':
                supports_wms = True
                wms_layer = layer_record
            elif service_type == 'WFS':
                supports_wfs = True
                wfs_layer = layer_record
        
        # 使用第一个记录作为基础信息（通常它们的基础信息是相同的）
        base_layer = matching_layers[0]
        
        # 记录支持的服务类型
        supported_types = []
        if supports_wms:
            supported_types.append('WMS')
        if supports_wfs:
            supported_types.append('WFS')
        
        logger.info(f"图层 {layer_name} 支持的服务类型: {', '.join(supported_types)}")
        
        # 构建访问参数 - 只为支持的服务类型提供完整参数
        access_parameters = {}
        
        if supports_wms and wms_layer:
            access_parameters["wms"] = {
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
            }
        else:
            access_parameters["wms"] = False  # 明确标记不支持
            
        if supports_wfs and wfs_layer:
            access_parameters["wfs"] = {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": layer_name,
                "srsName": "EPSG:4326",
                "bbox": [-180, -90, 180, 90],
                "maxFeatures": 1000,
                "outputFormat": "application/json"
            }
        else:
            access_parameters["wfs"] = False  # 明确标记不支持
        
        # 构建图层详细信息
        layer_details = {
            "layer_name": layer_name,
            "basic_info": {
                "resource_id": base_layer.get('resource_id'),
                "layer_name": base_layer['layer_name'],
                "layer_title": base_layer.get('layer_title', layer_name),
                "layer_abstract": base_layer.get('layer_abstract'),
                "service_type": ', '.join(supported_types),  # 显示所有支持的类型
                "detected_service_type": ', '.join(supported_types),
                "service_url": base_layer['service_url'],
                "service_name": base_layer.get('service_name'),
                "keywords": [],
                "created_at": base_layer.get('created_at'),
                "updated_at": base_layer.get('updated_at'),
                "multiple_service_types": len(matching_layers) > 1,
                "available_records": len(matching_layers)
            },
            "access_parameters": access_parameters,
            "capabilities": {
                "bbox": {"wgs84": [-180, -90, 180, 90], "crs": "EPSG:4326"},
                "crs_list": ["EPSG:4326"],
                "default_crs": "EPSG:4326",
                "queryable": supports_wfs,  # WFS图层可查询
                "geometry_type": None,
                "attributes": []
            },
            "metadata": {
                "source": "database_merged_service_types",
                "last_updated": datetime.now().isoformat(),
                "ogc_compliant": True,
                "primary_service": supported_types[0] if supported_types else "unknown",
                "supported_services": supported_types,
                "note": f"合并了{len(matching_layers)}个服务类型记录，未进行动态检测"
            }
        }
        
        return json.dumps(layer_details, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"获取图层详细信息失败: {e}")
        return json.dumps({
            "error": f"获取图层详细信息失败: {str(e)}",
            "layer_name": layer_name
        }, ensure_ascii=False, indent=2)
