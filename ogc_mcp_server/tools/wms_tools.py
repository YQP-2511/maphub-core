"""WMS工具模块

提供WMS相关的工具函数，统一使用Web服务器提供可视化
"""

import logging
from typing import Dict, Any, Optional
from fastmcp import FastMCP, Context
from pydantic import Field
from typing_extensions import Annotated

from ..database import get_layer_repository, LayerResourceQuery
from ..utils.ogc_parser import get_ogc_parser
from ..services.web_server.server import get_web_server

logger = logging.getLogger(__name__)

# 创建WMS工具子服务器
wms_server = FastMCP(name="WMS工具服务")


@wms_server.tool
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
    """
    if ctx:
        await ctx.info(f"正在生成WMS图层地图: {layer_name}")
    
    try:
        # 获取图层资源信息
        repository = await get_layer_repository()
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


@wms_server.tool
async def create_wms_visualization(
    layer_name: Annotated[str, Field(description="WMS图层名称")],
    width: Annotated[int, Field(description="地图容器宽度", ge=300, le=2000)] = 1000,
    height: Annotated[int, Field(description="地图容器高度", ge=300, le=2000)] = 700,
    initial_zoom: Annotated[int, Field(description="初始缩放级别", ge=1, le=18)] = 10,
    bbox: Annotated[Optional[str], Field(description="边界框，格式：min_x,min_y,max_x,max_y")] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """创建WMS图层Web可视化
    
    在统一Web服务器中创建WMS图层的交互式地图可视化。
    """
    if ctx:
        await ctx.info(f"正在创建WMS图层可视化: {layer_name}")
    
    try:
        # 获取图层信息
        repository = await get_layer_repository()
        query = LayerResourceQuery(layer_name=layer_name, service_type="WMS", limit=1)
        layers = await repository.list_resources(query)
        
        if not layers:
            raise ValueError(f"未找到WMS图层: {layer_name}")
        
        layer = layers[0]
        
        # 处理边界框
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
        
        # 计算地图中心点
        center_lat, center_lng = 39.9042, 116.4074  # 默认北京
        if bbox_coords:
            center_lat = (bbox_coords[1] + bbox_coords[3]) / 2
            center_lng = (bbox_coords[0] + bbox_coords[2]) / 2
        
        # 构建图层信息和地图配置
        layer_info = {
            "resource_id": layer.resource_id,
            "service_name": layer.service_name,
            "service_url": layer.service_url,
            "layer_name": layer.layer_name,
            "layer_title": layer.layer_title,
            "crs": layer.crs
        }
        
        map_config = {
            "center": [center_lat, center_lng],
            "zoom": initial_zoom,
            "width": width,
            "height": height,
            "bbox": bbox_coords
        }
        
        # 获取Web服务器并添加可视化
        web_server = await get_web_server()
        visualization_url = await web_server.add_wms_visualization(
            layer_name, layer_info, map_config
        )
        
        result = {
            "visualization_info": {
                "type": "wms",
                "layer_name": layer_name,
                "url": visualization_url,
                "web_server": web_server._get_base_url()
            },
            "layer_info": layer_info,
            "map_config": map_config,
            "instructions": {
                "access": f"在浏览器中访问: {visualization_url}",
                "web_server": f"Web服务器首页: {web_server._get_base_url()}",
                "features": [
                    "WMS图层交互式地图",
                    "缩放和平移操作",
                    "图层控制和底图切换",
                    "坐标显示和点击查询",
                    "比例尺显示"
                ]
            }
        }
        
        if ctx:
            await ctx.info(f"WMS可视化创建成功，访问地址: {visualization_url}")
        
        logger.info(f"WMS可视化创建成功: {layer_name}，URL: {visualization_url}")
        return result
        
    except Exception as e:
        error_msg = f"创建WMS可视化失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


@wms_server.tool
async def get_web_server_status(ctx: Context = None) -> Dict[str, Any]:
    """获取Web服务器状态
    
    返回统一Web可视化服务器的状态信息和可视化列表。
    """
    if ctx:
        await ctx.info("正在获取Web服务器状态")
    
    try:
        # 获取Web服务器
        web_server = await get_web_server()
        
        # 获取服务器信息和可视化列表
        server_info = web_server._get_server_info()
        visualizations = web_server.list_visualizations()
        
        result = {
            "server_status": server_info,
            "visualizations": visualizations,
            "access_info": {
                "web_interface": server_info["base_url"],
                "api_endpoint": f"{server_info['base_url']}/api/visualizations",
                "total_visualizations": visualizations["total"]
            },
            "instructions": {
                "web_access": f"在浏览器中访问: {server_info['base_url']}",
                "api_access": f"API接口: {server_info['base_url']}/api/visualizations",
                "features": [
                    "统一的可视化管理界面",
                    "WMS和GeoJSON地图展示",
                    "可视化结果浏览和管理",
                    "RESTful API接口"
                ]
            }
        }
        
        if ctx:
            await ctx.info(f"Web服务器运行正常，共有 {visualizations['total']} 个可视化")
        
        logger.info(f"Web服务器状态查询成功，可视化数量: {visualizations['total']}")
        return result
        
    except Exception as e:
        error_msg = f"获取Web服务器状态失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise