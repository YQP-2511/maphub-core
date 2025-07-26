"""WFS工具模块

基于资源驱动的WFS数据获取工具
专注于WFS要素数据的获取和查询功能
"""

import logging
import json
from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from pydantic import Field
from typing_extensions import Annotated

from ..utils.ogc_parser import get_ogc_parser

logger = logging.getLogger(__name__)

# 创建WFS工具服务器
wfs_server = FastMCP(name="WFS数据工具")


@wfs_server.tool
async def get_wfs_features(
    layer_name: Annotated[str, Field(description="WFS图层名称")],
    max_features: Annotated[int, Field(description="最大要素数量", ge=1, le=1000)] = 100,
    bbox: Annotated[Optional[str], Field(description="边界框，格式：min_x,min_y,max_x,max_y")] = None,
    property_names: Annotated[Optional[str], Field(description="属性名称列表，逗号分隔")] = None,
    cql_filter: Annotated[Optional[str], Field(description="CQL过滤条件")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """获取WFS图层要素数据
    
    通过资源获取图层信息，然后从WFS服务获取要素数据。
    支持边界框过滤、属性选择和CQL查询。
    
    Args:
        layer_name: WFS图层名称
        max_features: 最大要素数量
        bbox: 边界框，格式：min_x,min_y,max_x,max_y
        property_names: 属性名称列表，逗号分隔
        cql_filter: CQL过滤条件
        ctx: MCP上下文对象
        
    Returns:
        包含要素数据的GeoJSON格式结果
    """
    if ctx:
        await ctx.info(f"正在获取WFS图层要素: {layer_name}")
    
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
        
        # 验证是否支持WFS
        wfs_params = layer_data["access_parameters"].get("wfs")
        if not wfs_params:
            raise ValueError(f"图层 {layer_name} 不支持WFS服务")
        
        # 解析查询参数
        bbox_coords = _parse_bbox(bbox) if bbox else None
        properties = _parse_property_names(property_names) if property_names else None
        
        # 获取要素数据
        parser = await get_ogc_parser()
        
        # 构建请求参数
        params = {
            "service": "WFS",
            "version": wfs_params["version"],
            "request": "GetFeature",
            "typeNames": wfs_params["typeNames"],
            "maxFeatures": max_features,
            "outputFormat": "application/json"
        }
        
        if bbox_coords:
            params["bbox"] = ",".join(map(str, bbox_coords))
        
        if properties:
            params["propertyName"] = ",".join(properties)
        
        if cql_filter:
            params["cql_filter"] = cql_filter
        
        # 发送请求
        basic_info = layer_data["basic_info"]
        response = await parser.http_client.get(basic_info["service_url"], params=params)
        
        if response.status_code != 200:
            raise RuntimeError(f"WFS请求失败: {response.status_code} - {response.text}")
        
        features_data = response.json()
        
        result = {
            "layer_info": {
                "name": basic_info["layer_name"],
                "title": basic_info["layer_title"],
                "service_url": basic_info["service_url"],
                "service_type": basic_info["service_type"]
            },
            "features": features_data,
            "query_parameters": {
                "max_features": max_features,
                "bbox": bbox_coords,
                "property_names": properties,
                "cql_filter": cql_filter
            },
            "summary": {
                "total_features": len(features_data.get("features", [])),
                "feature_type": features_data.get("type", "FeatureCollection")
            }
        }
        
        if ctx:
            await ctx.info(f"成功获取 {len(features_data.get('features', []))} 个要素")
        
        logger.info(f"WFS要素获取成功: {layer_name}, 要素数量: {len(features_data.get('features', []))}")
        return result
        
    except Exception as e:
        error_msg = f"获取WFS要素失败: {e}"
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


def _parse_property_names(property_str: str) -> List[str]:
    """解析属性名称列表"""
    return [name.strip() for name in property_str.split(',') if name.strip()]