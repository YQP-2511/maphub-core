"""
WFS工具模块

提供WFS服务的要素数据获取功能
"""

import logging
from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context

logger = logging.getLogger(__name__)


async def get_wfs_features(
    layer_name: str,
    max_features: int = 100,
    bbox: Optional[str] = None,
    crs: Optional[str] = None,
    property_names: Optional[List[str]] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """获取WFS要素数据
    
    从指定图层获取要素数据，支持空间和属性过滤
    
    Args:
        layer_name: 图层名称
        max_features: 最大要素数量，默认100
        bbox: 边界框过滤 (minx,miny,maxx,maxy)
        crs: 坐标参考系统，默认EPSG:4326
        property_names: 要返回的属性名称列表
        ctx: MCP上下文对象
        
    Returns:
        包含要素数据和元数据的字典
    """
    if ctx:
        await ctx.info(f"正在获取图层 {layer_name} 的WFS要素数据")
    
    try:
        # 1. 先读取静态列表资源进行验证
        layers_resource_result = await ctx.read_resource(f"ogc://layers")
        
        # 修复：正确处理资源返回的数据结构
        if not layers_resource_result or not layers_resource_result[0].content:
            raise ValueError("无法获取图层列表资源")
        
        layers_content = layers_resource_result[0].content
        
        # 如果content是字符串，需要解析为JSON
        if isinstance(layers_content, str):
            import json
            layers_data_dict = json.loads(layers_content)
        else:
            layers_data_dict = layers_content
        
        # 获取图层列表
        layers_data = layers_data_dict.get("layers", [])
        
        # 查找目标图层
        target_layer = None
        for layer in layers_data:
            if layer["layer_name"] == layer_name:
                target_layer = layer
                break
        
        if not target_layer:
            raise ValueError(f"图层 {layer_name} 不存在")
        
        # 检查图层是否支持WFS服务
        service_type = target_layer.get("service_type", "").upper()
        # 验证图层是否支持WFS服务
        if service_type != "WFS":
            raise ValueError(f"图层 {layer_name} 不支持WFS服务，当前服务类型: {service_type}")
        
        # 2. 读取图层详细配置
        layer_resource_result = await ctx.read_resource(f"ogc://layer/{layer_name}")
        
        # 修复：正确处理资源返回的数据结构
        if not layer_resource_result or not layer_resource_result[0].content:
            raise ValueError(f"无法获取图层 {layer_name} 的配置信息")
        
        layer_content = layer_resource_result[0].content
        
        # 如果content是字符串，需要解析为JSON
        if isinstance(layer_content, str):
            import json
            layer_config = json.loads(layer_content)
        else:
            layer_config = layer_content
        
        # 检查是否包含错误信息
        if isinstance(layer_config, dict) and "error" in layer_config:
            raise ValueError(f"图层资源错误: {layer_config['error']}")
        
        # 3. 构建WFS GetFeature请求参数
        # 从access_parameters中获取WFS配置
        access_params = layer_config.get("access_parameters", {})
        wfs_config = access_params.get("wfs", {})
        
        if not wfs_config:
            raise ValueError(f"图层 {layer_name} 缺少WFS配置信息")
        
        # 获取基础信息
        basic_info = layer_config.get("basic_info", {})
        service_url = basic_info.get("service_url")
        if not service_url:
            raise ValueError(f"图层 {layer_name} 缺少WFS服务URL")
        
        # 构建请求参数
        params = {
            "service": "WFS",
            "version": wfs_config.get("version", "2.0.0"),
            "request": "GetFeature",
            "typeName": layer_name,
            "outputFormat": wfs_config.get("outputFormat", "application/json"),
            "maxFeatures": str(max_features)
        }
        
        # 添加可选参数
        if bbox:
            params["bbox"] = bbox
        
        if crs:
            params["srsName"] = crs
        elif wfs_config.get("srsName"):
            params["srsName"] = wfs_config["srsName"]
        else:
            params["srsName"] = "EPSG:4326"
        
        if property_names:
            params["propertyName"] = ",".join(property_names)
        
        # 构建完整的WFS请求URL
        param_string = "&".join([f"{k}={v}" for k, v in params.items()])
        wfs_url = f"{service_url}?{param_string}"
        
        logger.info(f"WFS要素获取成功: {layer_name}, URL: {wfs_url}")
        
        return {
            "layer_name": layer_name,
            "service_type": "WFS",
            "request_url": wfs_url,
            "parameters": params,
            "max_features": max_features,
            "bbox": bbox,
            "crs": params["srsName"],
            "property_names": property_names,
            "layer_info": {
                "title": basic_info.get("layer_title"),
                "abstract": basic_info.get("layer_abstract"),
                "service_url": service_url,
                "available_crs": layer_config.get("capabilities", {}).get("crs_list", []),
                "geometry_type": layer_config.get("capabilities", {}).get("geometry_type"),
                "attributes": layer_config.get("capabilities", {}).get("attributes", [])
            }
        }
        
    except Exception as e:
        error_msg = f"获取WFS要素失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise ValueError(error_msg)


# 创建WFS工具服务器
wfs_server = FastMCP("WFS工具")


@wfs_server.tool()
async def get_wfs_features_tool(
    layer_name: str,
    max_features: int = 100,
    bbox: Optional[str] = None,
    crs: Optional[str] = None,
    property_names: Optional[List[str]] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """获取WFS要素数据工具
    
    从指定图层获取要素数据，支持空间和属性过滤
    
    Args:
        layer_name: 图层名称
        max_features: 最大要素数量，默认100
        bbox: 边界框过滤，格式为 "minx,miny,maxx,maxy"
        crs: 坐标参考系统，如 "EPSG:4326"
        property_names: 要返回的属性名称列表
        
    Returns:
        包含要素数据请求URL和元数据的字典
    """
    return await get_wfs_features(
        layer_name=layer_name,
        max_features=max_features,
        bbox=bbox,
        crs=crs,
        property_names=property_names,
        ctx=ctx
    )