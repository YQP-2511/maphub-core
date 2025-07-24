"""通用可视化工具模块

提供通用的地图可视化功能，作为工作台接受任意的WMS/WFS数据进行组合可视化
完全利用现有的web_server基础设施，避免重复代码
"""

import logging
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP, Context
from pydantic import Field
from typing_extensions import Annotated

from ..services.web_server.server import get_web_server
from ..database import get_layer_repository, LayerResourceQuery
from ..utils.ogc_parser import get_ogc_parser

logger = logging.getLogger(__name__)

# 创建通用可视化工具子服务器
visualization_server = FastMCP(name="通用可视化工具服务")


@visualization_server.tool
async def create_composite_visualization(
    layers: Annotated[List[Dict[str, Any]], Field(description="图层配置列表，每个图层包含type(wms/geojson)、data、config等信息")],
    map_config: Annotated[Optional[Dict[str, Any]], Field(description="地图配置，包含center、zoom、width、height等")] = None,
    title: Annotated[str, Field(description="可视化标题")] = "复合图层可视化",
    ctx: Context = None
) -> Dict[str, Any]:
    """创建复合图层可视化
    
    这是一个通用的可视化工作台，可以接受任意的WMS图层和GeoJSON数据进行组合可视化。
    AI可以通过调用WMS和WFS工具获取数据，然后使用此工具进行统一可视化。
    
    Args:
        layers: 图层配置列表，支持以下格式：
            - WMS图层: {"type": "wms", "layer_info": {...}, "map_config": {...}}
            - GeoJSON图层: {"type": "geojson", "layer_info": {...}, "geojson_data": {...}, "style": {...}}
        map_config: 地图配置
        title: 可视化标题
        
    Returns:
        可视化结果信息
    """
    if ctx:
        await ctx.info(f"正在创建复合图层可视化: {title}")
    
    try:
        # 验证图层配置
        if not layers:
            raise ValueError("至少需要提供一个图层")
        
        # 设置默认地图配置
        default_map_config = {
            "center": [39.9042, 116.4074],  # 默认北京
            "zoom": 10,
            "width": 1200,
            "height": 800
        }
        
        if map_config:
            default_map_config.update(map_config)
        
        # 获取Web服务器
        web_server = await get_web_server()
        
        # 直接使用web_server的add_composite_visualization方法
        # 这样可以完全利用现有的基础设施，避免重复代码
        visualization_url = await web_server.add_composite_visualization(
            title=title,
            layers=layers,
            map_config=default_map_config
        )
        
        # 获取创建的可视化信息
        viz_id = f"composite_{title.replace(' ', '_').replace(':', '_').replace('/', '_')}"
        viz_info = web_server.get_visualization_by_id(viz_id)
        
        if not viz_info:
            raise RuntimeError("复合可视化创建失败，无法获取可视化信息")
        
        # 构建返回结果
        processed_layers = viz_info.get("layers", [])
        
        result = {
            "visualization_info": {
                "type": "composite",
                "title": title,
                "url": visualization_url,
                "web_server": web_server._get_base_url()
            },
            "layers_info": {
                "total_layers": len(processed_layers),
                "layer_types": [layer.get("type", "unknown") for layer in processed_layers],
                "layer_names": [layer.get("name", f"图层{i+1}") for i, layer in enumerate(processed_layers)]
            },
            "map_config": viz_info.get("map_config", default_map_config),
            "instructions": {
                "access": f"在浏览器中访问: {visualization_url}",
                "web_server": f"Web服务器首页: {web_server._get_base_url()}",
                "features": [
                    "多图层叠加可视化",
                    "交互式地图操作",
                    "图层控制和切换",
                    "要素属性查看",
                    "测量和分析工具"
                ]
            }
        }
        
        if ctx:
            await ctx.info(f"复合可视化创建成功，包含 {len(processed_layers)} 个图层，访问地址: {visualization_url}")
        
        logger.info(f"复合可视化创建成功: {title}，图层数量: {len(processed_layers)}")
        return result
        
    except Exception as e:
        error_msg = f"创建复合可视化失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


@visualization_server.tool
async def create_single_layer_visualization(
    layer_config: Annotated[Dict[str, Any], Field(description="单个图层配置")],
    map_config: Annotated[Optional[Dict[str, Any]], Field(description="地图配置")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """创建单图层可视化
    
    为单个图层创建可视化，自动选择合适的处理器
    支持 WMS、WFS 和 GeoJSON 图层类型
    
    Args:
        layer_config: 图层配置，支持以下格式：
            - WMS图层: {"type": "wms", "layer_name": "...", "service_url": "..."}
            - WFS图层: {"type": "wfs", "layer_name": "...", "service_url": "...", "style": {...}}
            - GeoJSON图层: {"type": "geojson", "geojson_data": {...}, "style": {...}}
        map_config: 地图配置
        
    Returns:
        可视化结果信息
    """
    if ctx:
        await ctx.info("正在创建单图层可视化")
    
    try:
        layer_type = layer_config.get("type", "").lower()
        
        # 设置默认地图配置
        default_map_config = {
            "center": [39.9042, 116.4074],
            "zoom": 10,
            "width": 1200,
            "height": 800
        }
        
        if map_config:
            default_map_config.update(map_config)
        
        # 获取Web服务器
        web_server = await get_web_server()
        
        # 根据图层类型选择合适的方法
        if layer_type == "wms":
            layer_name = layer_config.get("layer_name", "未命名WMS图层")
            layer_info = {
                "layer_name": layer_name,
                "service_url": layer_config.get("service_url", ""),
                "service_type": "WMS"
            }
            
            visualization_url = await web_server.add_wms_visualization(
                layer_name=layer_name,
                layer_info=layer_info,
                map_config=default_map_config
            )
            
        elif layer_type == "wfs":
            # 处理WFS图层：先获取GeoJSON数据，然后创建可视化
            layer_name = layer_config.get("layer_name", "未命名WFS图层")
            service_url = layer_config.get("service_url", "")
            
            if ctx:
                await ctx.info(f"正在获取WFS图层数据: {layer_name}")
            
            # 获取WFS GeoJSON数据
            geojson_data = await _fetch_wfs_geojson_data(
                layer_name=layer_name,
                service_url=service_url,
                max_features=layer_config.get("max_features", 100),
                bbox=layer_config.get("bbox"),
                cql_filter=layer_config.get("cql_filter"),
                ctx=ctx
            )
            
            # 计算统计信息
            stats = _calculate_geojson_stats(geojson_data)
            
            # 构建图层信息
            layer_info = {
                "layer_name": layer_name,
                "service_url": service_url,
                "service_type": "WFS",
                "style": layer_config.get("style", {}),
                "popup_properties": layer_config.get("popup_properties", [])
            }
            
            # 如果用户提供了地图中心点，使用用户配置；否则自动计算
            if not map_config or "center" not in map_config:
                auto_center = _calculate_geojson_center(geojson_data)
                if auto_center:
                    default_map_config["center"] = auto_center
                    if ctx:
                        await ctx.info(f"自动计算地图中心点: {auto_center}")
            
            visualization_url = await web_server.add_geojson_visualization(
                layer_name=layer_name,
                layer_info=layer_info,
                geojson_data=geojson_data,
                stats=stats,
                map_config=default_map_config
            )
            
        elif layer_type == "geojson":
            layer_name = layer_config.get("layer_name", "未命名GeoJSON图层")
            geojson_data = layer_config.get("geojson_data", {})
            stats = _calculate_geojson_stats(geojson_data)
            
            layer_info = {
                "layer_name": layer_name,
                "service_type": "GeoJSON",
                "style": layer_config.get("style", {}),
                "popup_properties": layer_config.get("popup_properties", [])
            }
            
            visualization_url = await web_server.add_geojson_visualization(
                layer_name=layer_name,
                layer_info=layer_info,
                geojson_data=geojson_data,
                stats=stats,
                map_config=default_map_config
            )
            
        else:
            raise ValueError(f"不支持的图层类型: {layer_type}。支持的类型: wms, wfs, geojson")
        
        result = {
            "visualization_info": {
                "type": layer_type,
                "layer_name": layer_config.get("layer_name", "未命名图层"),
                "url": visualization_url,
                "web_server": web_server._get_base_url()
            },
            "map_config": default_map_config,
            "instructions": {
                "access": f"在浏览器中访问: {visualization_url}",
                "web_server": f"Web服务器首页: {web_server._get_base_url()}"
            }
        }
        
        if layer_type == "wfs":
            result["data_info"] = {
                "feature_count": stats.get("feature_count", 0),
                "geometry_types": stats.get("geometry_types", [])
            }
        
        if ctx:
            await ctx.info(f"单图层可视化创建成功，访问地址: {visualization_url}")
        
        logger.info(f"单图层可视化创建成功: {layer_config.get('layer_name', '未命名图层')} ({layer_type})")
        return result
        
    except Exception as e:
        error_msg = f"创建单图层可视化失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


@visualization_server.tool
async def list_visualizations(ctx: Context = None) -> Dict[str, Any]:
    """列出所有可视化
    
    Returns:
        可视化列表信息
    """
    try:
        web_server = await get_web_server()
        visualizations = web_server.list_visualizations()
        
        if ctx:
            await ctx.info(f"当前共有 {visualizations['total']} 个可视化")
        
        return visualizations
        
    except Exception as e:
        error_msg = f"获取可视化列表失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


@visualization_server.tool
async def remove_visualization(
    viz_id: Annotated[str, Field(description="可视化ID")],
    ctx: Context = None
) -> Dict[str, Any]:
    """删除指定的可视化
    
    Args:
        viz_id: 可视化ID
        
    Returns:
        删除结果
    """
    try:
        web_server = await get_web_server()
        success = web_server.remove_visualization(viz_id)
        
        if success:
            result = {"success": True, "message": f"可视化 {viz_id} 已删除"}
            if ctx:
                await ctx.info(f"可视化 {viz_id} 删除成功")
        else:
            result = {"success": False, "message": f"可视化 {viz_id} 不存在或删除失败"}
            if ctx:
                await ctx.warning(f"可视化 {viz_id} 删除失败")
        
        return result
        
    except Exception as e:
        error_msg = f"删除可视化失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


@visualization_server.tool
async def get_web_server_info(ctx: Context = None) -> Dict[str, Any]:
    """获取Web服务器信息
    
    Returns:
        服务器信息
    """
    try:
        web_server = await get_web_server()
        
        server_info = {
            "base_url": web_server._get_base_url(),
            "is_running": web_server.is_running,
            "host": web_server.host,
            "port": web_server.port,
            "total_visualizations": len(web_server.visualizations),
            "api_endpoints": {
                "visualizations": f"{web_server._get_base_url()}/api/visualizations",
                "index": f"{web_server._get_base_url()}/index.html"
            }
        }
        
        if ctx:
            await ctx.info(f"Web服务器运行在: {server_info['base_url']}")
        
        return server_info
        
    except Exception as e:
        error_msg = f"获取Web服务器信息失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


# 辅助函数

async def _fetch_wfs_geojson_data(
    layer_name: str,
    service_url: str,
    max_features: int = 100,
    bbox: Optional[str] = None,
    cql_filter: Optional[str] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """获取WFS图层的GeoJSON数据
    
    Args:
        layer_name: 图层名称
        service_url: WFS服务URL
        max_features: 最大要素数量
        bbox: 边界框过滤
        cql_filter: CQL过滤条件
        ctx: 上下文
        
    Returns:
        GeoJSON数据
    """
    try:
        # 如果没有提供service_url，尝试从数据库获取
        if not service_url:
            repository = await get_layer_repository()
            query = LayerResourceQuery(layer_name=layer_name)
            layers = await repository.find_layers(query)
            
            if not layers:
                raise ValueError(f"未找到图层: {layer_name}")
            
            layer = layers[0]
            service_url = layer.service_url
        
        # 构建WFS GetFeature请求参数
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeName": layer_name,
            "outputFormat": "application/json",
            "maxFeatures": max_features
        }
        
        # 添加可选参数
        if bbox:
            params["bbox"] = bbox
        if cql_filter:
            params["CQL_FILTER"] = cql_filter
        
        # 发送HTTP请求获取数据
        import httpx
        import json
        
        async with httpx.AsyncClient() as client:
            response = await client.get(service_url, params=params)
            
            if response.status_code != 200:
                raise Exception(f"WFS请求失败: HTTP {response.status_code}")
            
            content_type = response.headers.get('content-type', '')
            if 'json' in content_type:
                geojson_data = response.json()
            else:
                text_content = response.text
                geojson_data = json.loads(text_content)
        
        # 验证GeoJSON格式
        if not isinstance(geojson_data, dict) or geojson_data.get("type") != "FeatureCollection":
            raise ValueError("返回的数据不是有效的GeoJSON FeatureCollection")
        
        if ctx:
            feature_count = len(geojson_data.get("features", []))
            await ctx.info(f"成功获取 {feature_count} 个要素")
        
        return geojson_data
        
    except Exception as e:
        error_msg = f"获取WFS GeoJSON数据失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


def _calculate_geojson_stats(geojson_data: Dict[str, Any]) -> Dict[str, Any]:
    """计算GeoJSON统计信息
    
    Args:
        geojson_data: GeoJSON数据
        
    Returns:
        统计信息
    """
    features = geojson_data.get("features", [])
    feature_count = len(features)
    
    geometry_types = set()
    property_names = set()
    
    for feature in features:
        # 统计几何类型
        geometry = feature.get("geometry", {})
        geom_type = geometry.get("type")
        if geom_type:
            geometry_types.add(geom_type)
        
        # 统计属性字段
        properties = feature.get("properties", {})
        if properties:
            property_names.update(properties.keys())
    
    return {
        "feature_count": feature_count,
        "geometry_types": list(geometry_types),
        "property_names": list(property_names)
    }


def _calculate_geojson_center(geojson_data: Dict[str, Any]) -> Optional[List[float]]:
    """计算GeoJSON数据的中心点
    
    Args:
        geojson_data: GeoJSON数据
        
    Returns:
        中心点坐标 [lat, lon]，如果无法计算则返回None
    """
    try:
        features = geojson_data.get("features", [])
        if not features:
            return None
        
        # 收集所有坐标点
        all_coords = []
        
        for feature in features:
            geometry = feature.get("geometry", {})
            geom_type = geometry.get("type")
            coordinates = geometry.get("coordinates", [])
            
            if geom_type == "Point":
                all_coords.append(coordinates)
            elif geom_type in ["LineString", "MultiPoint"]:
                all_coords.extend(coordinates)
            elif geom_type == "Polygon":
                # 只使用外环
                if coordinates:
                    all_coords.extend(coordinates[0])
            elif geom_type == "MultiLineString":
                for line in coordinates:
                    all_coords.extend(line)
            elif geom_type == "MultiPolygon":
                for polygon in coordinates:
                    if polygon:
                        all_coords.extend(polygon[0])
        
        if not all_coords:
            return None
        
        # 计算平均坐标
        total_lon = sum(coord[0] for coord in all_coords)
        total_lat = sum(coord[1] for coord in all_coords)
        count = len(all_coords)
        
        center_lat = total_lat / count
        center_lon = total_lon / count
        
        return [center_lat, center_lon]
        
    except Exception as e:
        logger.warning(f"计算GeoJSON中心点失败: {e}")
        return None