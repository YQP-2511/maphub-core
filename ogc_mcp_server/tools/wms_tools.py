"""
WMS工具模块

提供WMS服务的地图图像获取功能
"""

import logging
from typing import Dict, Any, Optional
from fastmcp import FastMCP, Context

logger = logging.getLogger(__name__)


async def get_wms_map_url(
    layer_name: str,
    bbox: str,
    width: int = 800,
    height: int = 600,
    crs: Optional[str] = None,
    format_type: str = "image/png",
    styles: Optional[str] = None,
    transparent: bool = True,
    ctx: Context = None
) -> Dict[str, Any]:
    """生成WMS地图图像URL
    
    根据指定参数生成WMS GetMap请求URL
    
    Args:
        layer_name: 图层名称
        bbox: 边界框 (minx,miny,maxx,maxy)
        width: 图像宽度，默认800像素
        height: 图像高度，默认600像素
        crs: 坐标参考系统，默认EPSG:4326
        format_type: 图像格式，默认image/png
        styles: 样式名称，默认为空
        transparent: 是否透明背景，默认True
        ctx: MCP上下文对象
        
    Returns:
        包含WMS地图URL和参数的字典
    """
    if ctx:
        await ctx.info(f"正在生成图层 {layer_name} 的WMS地图URL")
    
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
        
        # 检查图层是否支持WMS服务
        service_type = target_layer.get("service_type", "").upper()
        if service_type not in ["WMS", "BOTH"]:
            raise ValueError(f"图层 {layer_name} 不支持WMS服务 (当前类型: {service_type})")
        
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
        
        # 3. 构建WMS GetMap请求参数
        # 从access_parameters中获取WMS配置
        access_params = layer_config.get("access_parameters", {})
        wms_config = access_params.get("wms", {})
        
        if not wms_config:
            raise ValueError(f"图层 {layer_name} 缺少WMS配置信息")
        
        # 获取基础信息
        basic_info = layer_config.get("basic_info", {})
        service_url = basic_info.get("service_url")
        if not service_url:
            raise ValueError(f"图层 {layer_name} 缺少WMS服务URL")
        
        # 构建请求参数
        params = {
            "service": "WMS",
            "version": wms_config.get("version", "1.3.0"),
            "request": "GetMap",
            "layers": layer_name,
            "bbox": bbox,
            "width": str(width),
            "height": str(height),
            "format": format_type,
            "transparent": str(transparent).lower()
        }
        
        # 处理坐标参考系统
        if crs:
            params["crs"] = crs
        elif wms_config.get("crs"):
            params["crs"] = wms_config["crs"]
        else:
            params["crs"] = "EPSG:4326"
        
        # 修复bbox的坐标轴顺序（WMS 1.3.0 + EPSG:4326需要纬度,经度顺序）
        final_bbox = bbox
        if params["crs"].upper() == "EPSG:4326" and params.get("version", "1.3.0") == "1.3.0":
            # 解析bbox字符串
            bbox_parts = bbox.split(',')
            if len(bbox_parts) == 4:
                try:
                    min_x, min_y, max_x, max_y = map(float, bbox_parts)
                    # 转换为纬度,经度顺序：(min_lat, min_lon, max_lat, max_lon)
                    final_bbox = f"{min_y},{min_x},{max_y},{max_x}"
                    logger.debug(f"WMS 1.3.0 EPSG:4326 bbox转换: {bbox} -> {final_bbox}")
                except ValueError:
                    logger.warning(f"无法解析bbox: {bbox}，使用原始值")
        
        params["bbox"] = final_bbox
        
        # 处理样式
        if styles:
            params["styles"] = styles
        else:
            # 从配置中获取默认样式
            available_styles = wms_config.get("styles", [])
            if available_styles and len(available_styles) > 0:
                params["styles"] = available_styles[0] if isinstance(available_styles[0], str) else ""
            else:
                params["styles"] = ""
        
        # 构建完整的WMS请求URL
        param_string = "&".join([f"{k}={v}" for k, v in params.items()])
        wms_url = f"{service_url}?{param_string}"
        
        logger.info(f"WMS地图URL生成成功: {layer_name}, URL: {wms_url}")
        
        return {
            "layer_name": layer_name,
            "service_type": "WMS",
            "map_url": wms_url,
            "parameters": params,
            "image_size": {"width": width, "height": height},
            "bbox": final_bbox,
            "crs": params["crs"],
            "format": format_type,
            "transparent": transparent,
            "layer_info": {
                "title": basic_info.get("layer_title"),
                "abstract": basic_info.get("layer_abstract"),
                "service_url": service_url,
                "available_crs": layer_config.get("capabilities", {}).get("crs_list", []),
                "available_formats": ["image/png", "image/jpeg", "image/gif"],
                "available_styles": wms_config.get("styles", [])
            }
        }
        
    except Exception as e:
        error_msg = f"生成WMS地图URL失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise ValueError(error_msg)


# 创建WMS工具服务器
wms_server = FastMCP("WMS工具")


@wms_server.tool()
async def get_wms_map_url_tool(
    layer_name: str,
    bbox: str,
    width: int = 800,
    height: int = 600,
    crs: Optional[str] = None,
    format_type: str = "image/png",
    styles: Optional[str] = None,
    transparent: bool = True,
    ctx: Context = None
) -> Dict[str, Any]:
    """生成WMS地图图像URL工具
    
    根据指定参数生成WMS GetMap请求URL，用于获取地图图像
    
    Args:
        layer_name: 图层名称
        bbox: 边界框，格式为 "minx,miny,maxx,maxy"
        width: 图像宽度（像素），默认800
        height: 图像高度（像素），默认600
        crs: 坐标参考系统，如 "EPSG:4326"，默认使用图层默认CRS
        format_type: 图像格式，如 "image/png", "image/jpeg"，默认 "image/png"
        styles: 样式名称，默认使用图层默认样式
        transparent: 是否透明背景，默认True
        
    Returns:
        包含WMS地图URL和相关信息的字典
    """
    return await get_wms_map_url(
        layer_name=layer_name,
        bbox=bbox,
        width=width,
        height=height,
        crs=crs,
        format_type=format_type,
        styles=styles,
        transparent=transparent,
        ctx=ctx
    )




