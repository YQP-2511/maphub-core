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


async def _build_access_parameters_from_details(layer_details: Dict[str, Any], layer_name: str) -> Dict[str, Any]:
    """根据详细信息构建访问参数
    
    Args:
        layer_details: 从layer_details.py获取的详细信息
        layer_name: 图层名称
        
    Returns:
        访问参数字典
    """
    access_parameters = {}
    service_type = layer_details.get("service_type", "").upper()
    
    if service_type == "WMS":
        # 构建WMS访问参数
        styles = layer_details.get("styles", [])
        default_style = styles[0]["name"] if styles else ""
        
        bbox = layer_details.get("bbox", {}).get("wgs84", [-180, -90, 180, 90])
        default_crs = layer_details.get("default_crs", "EPSG:4326")
        
        access_parameters["wms"] = {
            "service": "WMS",
            "version": "1.3.0",
            "request": "GetMap",
            "layers": layer_name,
            "bbox": bbox,
            "crs": default_crs,
            "width": 256,
            "height": 256,
            "format": "image/png",
            "styles": [style["name"] for style in styles],
            "default_style": default_style
        }
        
    elif service_type == "WFS":
        # 构建WFS访问参数
        bbox = layer_details.get("bbox", {}).get("wgs84", [-180, -90, 180, 90])
        default_crs = layer_details.get("default_crs", "EPSG:4326")
        
        access_parameters["wfs"] = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": layer_name,
            "srsName": default_crs,
            "bbox": bbox,
            "maxFeatures": 1000,
            "outputFormat": "application/json"
        }
        
    elif service_type == "WMTS":
        # 构建WMTS访问参数
        tile_matrix_sets = layer_details.get("tile_matrix_sets", [])
        formats = layer_details.get("formats", ["image/png"])
        styles = layer_details.get("styles", [])
        default_style = layer_details.get("default_style", "")
        default_format = layer_details.get("default_format", "image/png")
        
        # 选择默认的瓦片矩阵集
        default_tile_matrix_set = ""
        if tile_matrix_sets:
            # 优先选择常见的瓦片矩阵集
            for tms in ["GoogleMapsCompatible", "EPSG:4326", "EPSG:3857"]:
                if tms in tile_matrix_sets:
                    default_tile_matrix_set = tms
                    break
            if not default_tile_matrix_set:
                default_tile_matrix_set = tile_matrix_sets[0]
        
        # 处理样式列表，兼容字符串和字典两种格式
        style_identifiers = []
        for style in styles:
            if isinstance(style, dict):
                style_identifiers.append(style.get("identifier", ""))
            else:
                style_identifiers.append(str(style))
        
        access_parameters["wmts"] = {
            "service": "WMTS",
            "version": "1.0.0",
            "request": "GetTile",
            "layer": layer_name,
            "style": default_style,
            "format": default_format,
            "tilematrixset": default_tile_matrix_set,
            "tilematrix": "0",  # 默认缩放级别
            "tilerow": 0,
            "tilecol": 0,
            "tile_matrix_sets": tile_matrix_sets,
            "formats": formats,
            "styles": style_identifiers,
            "default_style": default_style,
            "dimensions": layer_details.get("dimensions", {}),
            "resource_urls": layer_details.get("resource_urls", {})
        }
    
    return access_parameters


@layer_registry_server.resource("ogc://layer/{layer_name}")
async def layer_detail(ctx: Context, layer_name: str) -> str:
    """获取指定图层的详细信息
    
    支持WMS、WFS和WMTS服务类型，使用layer_details.py进行详细解析
    
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
        supports_wmts = False
        service_records = {}
        
        for layer_record in matching_layers:
            service_type = layer_record['service_type'].upper()
            if service_type == 'WMS':
                supports_wms = True
                service_records['WMS'] = layer_record
            elif service_type == 'WFS':
                supports_wfs = True
                service_records['WFS'] = layer_record
            elif service_type == 'WMTS':
                supports_wmts = True
                service_records['WMTS'] = layer_record
        
        # 使用第一个记录作为基础信息
        base_layer = matching_layers[0]
        
        # 记录支持的服务类型
        supported_types = []
        if supports_wms:
            supported_types.append('WMS')
        if supports_wfs:
            supported_types.append('WFS')
        if supports_wmts:
            supported_types.append('WMTS')
        
        logger.info(f"图层 {layer_name} 支持的服务类型: {', '.join(supported_types)}")
        
        # 获取OGC解析器
        ogc_parser = await get_ogc_parser()
        
        # 构建访问参数 - 使用layer_details.py获取详细信息
        access_parameters = {}
        detailed_capabilities = {}
        
        # 为每个支持的服务类型获取详细信息
        for service_type in supported_types:
            if service_type in service_records:
                layer_record = service_records[service_type]
                service_url = layer_record['service_url']
                
                try:
                    # 使用layer_details.py获取详细信息
                    layer_details = await ogc_parser.layer_details_parser.get_layer_details(
                        service_url, service_type, layer_name, strict_mode=True
                    )
                    
                    # 构建访问参数
                    service_access_params = await _build_access_parameters_from_details(layer_details, layer_name)
                    access_parameters.update(service_access_params)
                    
                    # 保存详细能力信息
                    detailed_capabilities[service_type.lower()] = layer_details
                    
                    logger.info(f"成功获取 {service_type} 图层详细信息")
                    
                except Exception as e:
                    logger.warning(f"获取 {service_type} 详细信息失败: {e}")
                    # 提供基础的访问参数作为备选
                    if service_type == 'WMS':
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
                    elif service_type == 'WFS':
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
                    elif service_type == 'WMTS':
                        access_parameters["wmts"] = {
                            "service": "WMTS",
                            "version": "1.0.0",
                            "request": "GetTile",
                            "layer": layer_name,
                            "style": "",
                            "format": "image/png",
                            "tilematrixset": "GoogleMapsCompatible",
                            "tilematrix": "0",
                            "tilerow": 0,
                            "tilecol": 0
                        }
        
        # 为不支持的服务类型明确标记
        if not supports_wms:
            access_parameters["wms"] = False
        if not supports_wfs:
            access_parameters["wfs"] = False
        if not supports_wmts:
            access_parameters["wmts"] = False
        
        # 构建综合的能力信息
        combined_capabilities = {
            "bbox": {"wgs84": [-180, -90, 180, 90], "crs": "EPSG:4326"},
            "crs_list": ["EPSG:4326"],
            "default_crs": "EPSG:4326",
            "queryable": supports_wfs,
            "geometry_type": None,
            "attributes": []
        }
        
        # 如果有详细能力信息，使用第一个可用的
        if detailed_capabilities:
            first_detail = list(detailed_capabilities.values())[0]
            if first_detail.get("bbox"):
                combined_capabilities["bbox"] = first_detail["bbox"]
            if first_detail.get("crs_list"):
                combined_capabilities["crs_list"] = first_detail["crs_list"]
            if first_detail.get("default_crs"):
                combined_capabilities["default_crs"] = first_detail["default_crs"]
            if first_detail.get("attributes"):
                combined_capabilities["attributes"] = first_detail["attributes"]
            if first_detail.get("geometry_type"):
                combined_capabilities["geometry_type"] = first_detail["geometry_type"]
        
        # 构建图层详细信息
        layer_details_response = {
            "layer_name": layer_name,
            "basic_info": {
                "resource_id": base_layer.get('resource_id'),
                "layer_name": base_layer['layer_name'],
                "layer_title": base_layer.get('layer_title', layer_name),
                "layer_abstract": base_layer.get('layer_abstract'),
                "service_type": ', '.join(supported_types),
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
            "capabilities": combined_capabilities,
            "detailed_capabilities": detailed_capabilities,  # 新增：详细的服务能力信息
            "metadata": {
                "source": "database_with_detailed_parsing",
                "last_updated": datetime.now().isoformat(),
                "ogc_compliant": True,
                "primary_service": supported_types[0] if supported_types else "unknown",
                "supported_services": supported_types,
                "note": f"合并了{len(matching_layers)}个服务类型记录，使用layer_details.py进行详细解析",
                "parsing_status": {
                    service_type: service_type in detailed_capabilities 
                    for service_type in supported_types
                }
            }
        }
        
        return json.dumps(layer_details_response, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"获取图层详细信息失败: {e}")
        return json.dumps({
            "error": f"获取图层详细信息失败: {str(e)}",
            "layer_name": layer_name
        }, ensure_ascii=False, indent=2)
