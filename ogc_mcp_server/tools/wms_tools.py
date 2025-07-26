"""WMS工具模块

基于资源驱动的WMS地图服务工具
专注于WMS地图图像的生成和获取功能
"""

import logging
import json
from typing import Dict, Any, Optional
from fastmcp import FastMCP, Context
from pydantic import Field
from typing_extensions import Annotated

from ..utils.ogc_parser import get_ogc_parser

logger = logging.getLogger(__name__)

# 创建WMS工具服务器
wms_server = FastMCP(name="WMS地图工具")


@wms_server.tool
async def get_wms_map_url(
    layer_name: Annotated[str, Field(description="WMS图层名称")],
    width: Annotated[int, Field(description="图像宽度", ge=100, le=2000)] = 800,
    height: Annotated[int, Field(description="图像高度", ge=100, le=2000)] = 600,
    bbox: Annotated[Optional[str], Field(description="边界框，格式：min_x,min_y,max_x,max_y")] = None,
    crs: Annotated[str, Field(description="坐标参考系统")] = "EPSG:4326",
    format: Annotated[str, Field(description="图像格式")] = "image/png",
    styles: Annotated[Optional[str], Field(description="样式名称")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """生成WMS地图图像URL
    
    通过资源获取图层信息，然后生成WMS GetMap请求URL。
    
    Args:
        layer_name: WMS图层名称
        width: 图像宽度
        height: 图像高度
        bbox: 边界框，格式：min_x,min_y,max_x,max_y
        crs: 坐标参考系统
        format: 图像格式
        styles: 样式名称（注意：此参数仅用于接口兼容性，实际由parser自动处理）
        ctx: MCP上下文对象
        
    Returns:
        包含地图URL和相关信息的字典
    """
    if ctx:
        await ctx.info(f"正在生成WMS地图URL: {layer_name}")
    
    try:
        # 通过资源获取图层信息
        layer_resource = await ctx.read_resource(f"ogc://layer/{layer_name}")
        
        # 修复：处理不同的资源返回格式
        layer_data = None
        if isinstance(layer_resource, str):
            # 直接是JSON字符串
            layer_data = json.loads(layer_resource)
        elif isinstance(layer_resource, list) and len(layer_resource) > 0:
            # 是列表，取第一个元素
            if hasattr(layer_resource[0], 'content'):
                # 有content属性
                layer_data = json.loads(layer_resource[0].content)
            else:
                # 直接是数据
                layer_data = layer_resource[0]
        elif isinstance(layer_resource, dict):
            # 直接是字典
            layer_data = layer_resource
        else:
            raise ValueError(f"未知的资源格式: {type(layer_resource)}")
        
        if not layer_data:
            raise ValueError(f"无法解析图层资源: {layer_name}")
        
        if "error" in layer_data:
            raise ValueError(f"图层资源错误: {layer_data['error']}")
        
        # 验证是否支持WMS
        wms_params = layer_data["access_parameters"].get("wms")
        if not wms_params:
            raise ValueError(f"图层 {layer_name} 不支持WMS服务")
        
        # 解析边界框
        bbox_coords = _parse_bbox(bbox) if bbox else None
        
        # 如果没有提供边界框，使用图层的默认边界框
        if not bbox_coords:
            bbox_info = layer_data["capabilities"]["bbox"]
            if bbox_info and "wgs84" in bbox_info:
                bbox_coords = tuple(bbox_info["wgs84"])
        
        # 生成GetMap URL
        parser = await get_ogc_parser()
        basic_info = layer_data["basic_info"]
        
        # 修复：移除styles参数，因为parser方法不支持
        map_url = parser.get_wms_map_url(
            base_url=basic_info["service_url"],
            layer_name=wms_params["layers"],
            bbox=bbox_coords,
            width=width,
            height=height,
            crs=crs,
            format=format
        )
        
        result = {
            "layer_info": {
                "name": basic_info["layer_name"],
                "title": basic_info["layer_title"],
                "service_url": basic_info["service_url"],
                "service_type": basic_info["service_type"]
            },
            "map_url": map_url,
            "parameters": {
                "width": width,
                "height": height,
                "bbox": bbox_coords,
                "crs": crs,
                "format": format,
                "styles": styles or ""  # 记录用户请求的样式
            },
            "usage": {
                "direct_access": f"直接访问地图图像: {map_url}",
                "embed_html": f'<img src="{map_url}" alt="{basic_info["layer_title"]}" width="{width}" height="{height}">',
                "description": "可以直接在浏览器中打开URL查看地图图像"
            }
        }
        
        if ctx:
            await ctx.info(f"WMS地图URL生成成功: {layer_name}")
        
        logger.info(f"WMS地图URL生成成功: {layer_name}")
        return result
        
    except Exception as e:
        error_msg = f"生成WMS地图URL失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


# 辅助函数

def _parse_bbox(bbox_str: str) -> tuple:
    """解析边界框字符串"""
    try:
        coords = [float(x.strip()) for x in bbox_str.split(',')]
        if len(coords) == 4:
            return tuple(coords)
        else:
            raise ValueError("边界框必须包含4个坐标值")
    except ValueError as e:
        raise ValueError(f"边界框格式错误: {e}")