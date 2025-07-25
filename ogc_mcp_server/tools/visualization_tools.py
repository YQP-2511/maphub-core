"""通用可视化工作台模块

提供强大的地图可视化功能，支持多种图层类型的灵活组合和叠加
完全利用现有的web_server基础设施，提供统一的可视化工作台
"""

import logging
from typing import Dict, Any, List, Optional, Union
from fastmcp import FastMCP, Context
from pydantic import Field
from typing_extensions import Annotated

from ..services.web_server.server import get_web_server
from ..database import get_layer_repository, LayerResourceQuery
from ..utils.ogc_parser import get_ogc_parser

logger = logging.getLogger(__name__)

# 创建通用可视化工具子服务器
visualization_server = FastMCP(name="通用可视化工作台")


@visualization_server.tool
async def create_visualization_workspace(
    layers: Annotated[List[Dict[str, Any]], Field(description="图层配置列表")],
    map_config: Annotated[Optional[Dict[str, Any]], Field(description="地图配置")] = None,
    title: Annotated[str, Field(description="工作台标题")] = "可视化工作台",
    workspace_type: Annotated[str, Field(description="工作台类型: single, layered, comparison")] = "layered",
    ctx: Context = None
) -> Dict[str, Any]:
    """创建灵活的可视化工作台
    
    这是一个强大的可视化工作台，支持：
    - 单图层显示：独立展示单个图层
    - 分层叠加：多个图层的灵活叠加和控制
    - 对比显示：并排对比多个图层
    - 自动图层识别和配置
    - 智能样式和布局优化
    
    Args:
        layers: 图层配置列表，支持多种配置方式：
            1. 通过图层名称自动查找：{"layer_name": "图层名称"}
            2. 完整配置：{"type": "wms/wfs/geojson", "layer_name": "...", "service_url": "...", ...}
            3. 直接GeoJSON数据：{"type": "geojson", "geojson_data": {...}, "style": {...}}
            4. 图层ID引用：{"layer_id": "数据库中的图层ID"}
        map_config: 地图配置
        title: 可视化标题
        workspace_type: 工作台类型
        
    Returns:
        可视化结果信息
    """
    if ctx:
        await ctx.info(f"正在创建{workspace_type}可视化工作台: {title}")
    
    try:
        # 验证输入
        if not layers:
            raise ValueError("至少需要提供一个图层配置")
        
        # 处理图层配置
        processed_layers = []
        
        for i, layer_config in enumerate(layers):
            if ctx:
                await ctx.info(f"正在处理图层 {i+1}/{len(layers)}")
            
            # 智能处理图层配置
            processed_layer = await _smart_process_layer(layer_config, ctx=ctx)
            processed_layers.append(processed_layer)
        
        # 根据工作台类型设置地图配置
        final_map_config = await _configure_workspace_layout(
            workspace_type, processed_layers, map_config, ctx
        )
        
        # 创建可视化
        web_server = await get_web_server()
        
        # 根据工作台类型创建可视化
        if workspace_type == "single":
            # 单图层显示
            layer = processed_layers[0]
            if layer.get("type") == "wms":
                # 修复：使用正确的参数调用add_wms_visualization
                visualization_url = await web_server.add_wms_visualization(
                    layer_name=title,  # 使用title作为layer_name
                    layer_info=layer.get("layer_info", {}),
                    map_config=final_map_config
                )
            else:
                # 修复：使用正确的参数调用add_geojson_visualization
                visualization_url = await web_server.add_geojson_visualization(
                    layer_name=title,  # 使用title作为layer_name
                    layer_info=layer.get("layer_info", {}),
                    geojson_data=layer["geojson_data"],
                    stats=layer.get("stats", {}),
                    map_config=final_map_config
                )
        elif workspace_type == "comparison":
            # 对比显示 - 创建多个独立的可视化
            visualization_urls = []
            for i, layer in enumerate(processed_layers):
                layer_title = f"{title} - {layer.get('name', f'图层{i+1}')}"
                if layer.get("type") == "wms":
                    # 修复：使用正确的参数调用add_wms_visualization
                    url = await web_server.add_wms_visualization(
                        layer_name=layer_title,  # 使用layer_title作为layer_name
                        layer_info=layer.get("layer_info", {}),
                        map_config=final_map_config
                    )
                else:
                    # 修复：使用正确的参数调用add_geojson_visualization
                    url = await web_server.add_geojson_visualization(
                        layer_name=layer_title,  # 使用layer_title作为layer_name
                        layer_info=layer.get("layer_info", {}),
                        geojson_data=layer["geojson_data"],
                        stats=layer.get("stats", {}),
                        map_config=final_map_config
                    )
                visualization_urls.append(url)
            visualization_url = visualization_urls[0]  # 主要URL
        else:
            # 分层叠加显示（默认）
            visualization_url = await web_server.add_composite_visualization(
                title=title,
                layers=processed_layers,
                map_config=final_map_config
            )
        
        # 获取可视化信息
        viz_id = visualization_url.split('/')[-1].replace('.html', '')
        viz_info = web_server.get_visualization_by_id(viz_id)
        
        if not viz_info:
            raise RuntimeError("可视化工作台创建失败，无法获取可视化信息")
        
        # 构建结果
        result = {
            "visualization_info": {
                "type": workspace_type,
                "title": title,
                "url": visualization_url,
                "web_server": web_server._get_base_url()
            },
            "workspace_summary": {
                "workspace_type": workspace_type,
                "total_layers": len(processed_layers),
                "layer_types": _summarize_layer_types(processed_layers),
                "layer_details": [
                    {
                        "name": layer.get("name", f"图层{i+1}"),
                        "type": layer.get("type", "unknown"),
                        "service_type": layer.get("layer_info", {}).get("service_type", "unknown"),
                        "feature_count": layer.get("stats", {}).get("feature_count", 0)
                    }
                    for i, layer in enumerate(processed_layers)
                ]
            },
            "map_config": final_map_config,
            "capabilities": _get_workspace_capabilities(workspace_type),
            "instructions": {
                "access": f"在浏览器中访问: {visualization_url}",
                "web_server": f"Web服务器首页: {web_server._get_base_url()}",
                "features": _get_workspace_features(workspace_type)
            }
        }
        
        # 如果是对比模式，添加所有URL
        if workspace_type == "comparison" and 'visualization_urls' in locals():
            result["comparison_urls"] = visualization_urls
        
        if ctx:
            await ctx.info(f"{workspace_type}可视化工作台创建成功！共{len(processed_layers)}个图层")
            await ctx.info(f"访问地址: {visualization_url}")
        
        logger.info(f"{workspace_type}可视化工作台创建成功: {title}，图层数: {len(processed_layers)}")
        return result
        
    except Exception as e:
        error_msg = f"创建可视化工作台失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


@visualization_server.tool
async def create_single_layer_view(
    layer_config: Annotated[Dict[str, Any], Field(description="单个图层配置")],
    map_config: Annotated[Optional[Dict[str, Any]], Field(description="地图配置")] = None,
    title: Annotated[str, Field(description="可视化标题")] = "单图层视图",
    ctx: Context = None
) -> Dict[str, Any]:
    """创建单图层视图
    
    专门用于展示单个图层的简化接口
    
    Args:
        layer_config: 图层配置
        map_config: 地图配置
        title: 可视化标题
        
    Returns:
        可视化结果信息
    """
    return await create_visualization_workspace(
        layers=[layer_config],
        map_config=map_config,
        title=title,
        workspace_type="single",
        ctx=ctx
    )


@visualization_server.tool
async def create_layer_comparison(
    layers: Annotated[List[Dict[str, Any]], Field(description="要对比的图层列表")],
    map_config: Annotated[Optional[Dict[str, Any]], Field(description="地图配置")] = None,
    title: Annotated[str, Field(description="对比标题")] = "图层对比",
    ctx: Context = None
) -> Dict[str, Any]:
    """创建图层对比视图
    
    并排对比多个图层
    
    Args:
        layers: 要对比的图层列表
        map_config: 地图配置
        title: 对比标题
        
    Returns:
        对比结果信息
    """
    return await create_visualization_workspace(
        layers=layers,
        map_config=map_config,
        title=title,
        workspace_type="comparison",
        ctx=ctx
    )


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


# 智能图层处理函数

async def _smart_process_layer(
    layer_config: Dict[str, Any], 
    ctx: Context = None
) -> Dict[str, Any]:
    """智能处理图层配置
    
    支持多种配置方式的自动识别和处理
    
    Args:
        layer_config: 图层配置
        ctx: 上下文
        
    Returns:
        处理后的图层配置
    """
    try:
        # 方式1: 通过layer_id查找
        if "layer_id" in layer_config:
            return await _process_layer_by_id(layer_config["layer_id"], layer_config, ctx)
        
        # 方式2: 通过layer_name自动查找
        elif "layer_name" in layer_config and "type" not in layer_config:
            return await _process_layer_by_name(layer_config["layer_name"], layer_config, ctx)
        
        # 方式3: 完整配置
        elif "type" in layer_config:
            layer_type = layer_config["type"].lower()
            
            if layer_type == "wms":
                return await _process_wms_layer_safe(layer_config, ctx)
            elif layer_type == "wfs":
                return await _process_wfs_layer_safe(layer_config, ctx)
            elif layer_type == "geojson":
                return await _process_geojson_layer_safe(layer_config, ctx)
            else:
                raise ValueError(f"不支持的图层类型: {layer_type}")
        
        # 方式4: 尝试智能推断
        else:
            return await _infer_layer_config(layer_config, ctx)
        
    except Exception as e:
        logger.error(f"智能处理图层配置失败: {e}")
        raise


async def _process_layer_by_id(
    layer_id: str, 
    layer_config: Dict[str, Any], 
    ctx: Context = None
) -> Dict[str, Any]:
    """通过图层ID处理图层"""
    try:
        repository = await get_layer_repository()
        layer = await repository.get_resource(layer_id)
        
        if not layer:
            raise ValueError(f"未找到图层ID: {layer_id}")
        
        # 构建完整配置
        full_config = {
            "type": layer.service_type.lower(),
            "layer_name": layer.layer_name,
            "service_url": layer.service_url,
            "layer_title": layer.layer_title,
            "crs": layer.crs
        }
        
        # 合并用户提供的额外配置
        full_config.update({k: v for k, v in layer_config.items() if k != "layer_id"})
        
        if ctx:
            await ctx.info(f"通过ID找到图层: {layer.layer_name} ({layer.service_type})")
        
        return await _smart_process_layer(full_config, ctx)
        
    except Exception as e:
        logger.error(f"通过ID处理图层失败: {e}")
        raise


async def _process_layer_by_name(
    layer_name: str, 
    layer_config: Dict[str, Any], 
    ctx: Context = None
) -> Dict[str, Any]:
    """通过图层名称自动查找和处理图层"""
    try:
        repository = await get_layer_repository()
        query = LayerResourceQuery(layer_name=layer_name, limit=10)
        layers = await repository.list_resources(query)
        
        if not layers:
            raise ValueError(f"未找到图层: {layer_name}")
        
        # 选择最合适的图层
        selected_layer = layers[0]  # 默认选择第一个
        
        # 如果有多个，尝试智能选择
        if len(layers) > 1:
            # 优先选择WFS类型（更适合数据可视化）
            for layer in layers:
                if layer.service_type == "WFS":
                    selected_layer = layer
                    break
        
        # 构建完整配置
        full_config = {
            "type": selected_layer.service_type.lower(),
            "layer_name": selected_layer.layer_name,
            "service_url": selected_layer.service_url,
            "layer_title": selected_layer.layer_title,
            "crs": selected_layer.crs
        }
        
        # 合并用户提供的额外配置
        full_config.update({k: v for k, v in layer_config.items() if k != "layer_name"})
        
        if ctx:
            await ctx.info(f"自动识别图层 {layer_name} 为 {selected_layer.service_type} 类型")
        
        return await _smart_process_layer(full_config, ctx)
        
    except Exception as e:
        logger.error(f"通过名称处理图层失败: {e}")
        raise


async def _process_wms_layer_safe(
    layer_config: Dict[str, Any], 
    ctx: Context = None
) -> Dict[str, Any]:
    """安全处理WMS图层配置"""
    layer_name = layer_config.get("layer_name")
    service_url = layer_config.get("service_url")
    
    if not layer_name or not service_url:
        raise ValueError("WMS图层必须提供layer_name和service_url")
    
    processed_config = {
        "type": "wms",
        "name": layer_name,
        "layer_info": {
            "layer_name": layer_name,
            "service_url": service_url,
            "service_type": "WMS",
            "layer_title": layer_config.get("layer_title", layer_name),
            "crs": layer_config.get("crs", "EPSG:4326")
        },
        "config": {
            "opacity": layer_config.get("opacity", 0.8),
            "visible": layer_config.get("visible", True)
        }
    }
    
    return processed_config


async def _process_wfs_layer_safe(
    layer_config: Dict[str, Any], 
    ctx: Context = None
) -> Dict[str, Any]:
    """安全处理WFS图层配置"""
    layer_name = layer_config.get("layer_name")
    service_url = layer_config.get("service_url")
    
    if not layer_name or not service_url:
        raise ValueError("WFS图层必须提供layer_name和service_url")
    
    if ctx:
        await ctx.info(f"正在获取WFS图层数据: {layer_name}")
    
    try:
        # 获取WFS GeoJSON数据
        geojson_data = await _fetch_wfs_geojson_data_safe(
            layer_name=layer_name,
            service_url=service_url,
            max_features=layer_config.get("max_features", 100),
            bbox=layer_config.get("bbox"),
            cql_filter=layer_config.get("cql_filter"),
            ctx=ctx
        )
        
        # 计算统计信息
        stats = _calculate_geojson_stats(geojson_data)
        
        # 设置默认样式
        default_style = {
            "color": "#3388ff",
            "weight": 2,
            "opacity": 0.8,
            "fillColor": "#3388ff",
            "fillOpacity": 0.3,
            "radius": 6
        }
        
        style = layer_config.get("style", {})
        default_style.update(style)
        
        processed_config = {
            "type": "geojson",  # WFS转换为GeoJSON
            "name": layer_name,
            "layer_info": {
                "layer_name": layer_name,
                "service_url": service_url,
                "service_type": "WFS",
                "layer_title": layer_config.get("layer_title", layer_name),
                "crs": layer_config.get("crs", "EPSG:4326")
            },
            "geojson_data": geojson_data,
            "stats": stats,
            "style": default_style
        }
        
        return processed_config
        
    except Exception as e:
        logger.error(f"处理WFS图层失败: {e}")
        # 如果WFS获取失败，返回基本的WMS配置作为备选
        if ctx:
            await ctx.warning(f"WFS数据获取失败，尝试作为WMS图层处理: {e}")
        
        return await _process_wms_layer_safe(layer_config, ctx)


async def _process_geojson_layer_safe(
    layer_config: Dict[str, Any], 
    ctx: Context = None
) -> Dict[str, Any]:
    """安全处理GeoJSON图层配置"""
    geojson_data = layer_config.get("geojson_data")
    if not geojson_data:
        raise ValueError("GeoJSON图层必须提供geojson_data")
    
    # 计算统计信息
    stats = _calculate_geojson_stats(geojson_data)
    
    # 设置默认样式
    default_style = {
        "color": "#ff7800",
        "weight": 2,
        "opacity": 0.8,
        "fillColor": "#ff7800",
        "fillOpacity": 0.3,
        "radius": 6
    }
    
    style = layer_config.get("style", {})
    default_style.update(style)
    
    processed_config = {
        "type": "geojson",
        "name": layer_config.get("name", "GeoJSON图层"),
        "layer_info": {
            "layer_name": layer_config.get("name", "GeoJSON图层"),
            "service_type": "GeoJSON",
            "layer_title": layer_config.get("title", layer_config.get("name", "GeoJSON图层")),
            "crs": "EPSG:4326"
        },
        "geojson_data": geojson_data,
        "stats": stats,
        "style": default_style
    }
    
    return processed_config


async def _fetch_wfs_geojson_data_safe(
    layer_name: str,
    service_url: str,
    max_features: int = 100,
    bbox: Optional[List[float]] = None,
    cql_filter: Optional[str] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """安全获取WFS GeoJSON数据"""
    try:
        if not service_url:
            raise ValueError("service_url不能为空")
        
        # 使用OGC解析器获取数据
        parser = await get_ogc_parser()
        
        # 构建WFS GetFeature请求参数
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeName": layer_name,
            "outputFormat": "application/json",
            "maxFeatures": max_features
        }
        
        if bbox:
            params["bbox"] = ",".join(map(str, bbox))
        
        if cql_filter:
            params["cql_filter"] = cql_filter
        
        # 发送请求
        response = await parser.http_client.get(service_url, params=params)
        
        if response.status_code != 200:
            raise RuntimeError(f"WFS请求失败: {response.status_code} - {response.text}")
        
        geojson_data = response.json()
        
        if ctx:
            feature_count = len(geojson_data.get("features", []))
            await ctx.info(f"成功获取 {feature_count} 个要素")
        
        return geojson_data
        
    except Exception as e:
        logger.error(f"获取WFS GeoJSON数据失败: {e}")
        raise


async def _infer_layer_config(
    layer_config: Dict[str, Any], 
    ctx: Context = None
) -> Dict[str, Any]:
    """智能推断图层配置"""
    # 如果包含geojson_data，推断为GeoJSON类型
    if "geojson_data" in layer_config:
        layer_config["type"] = "geojson"
        return await _process_geojson_layer_safe(layer_config, ctx)
    
    # 如果包含service_url，尝试推断服务类型
    if "service_url" in layer_config:
        service_url = layer_config["service_url"].lower()
        if "wms" in service_url:
            layer_config["type"] = "wms"
            return await _process_wms_layer_safe(layer_config, ctx)
        elif "wfs" in service_url:
            layer_config["type"] = "wfs"
            return await _process_wfs_layer_safe(layer_config, ctx)
    
    raise ValueError("无法推断图层类型，请提供明确的type字段或layer_name进行自动查找")


# 工作台配置函数

async def _configure_workspace_layout(
    workspace_type: str,
    processed_layers: List[Dict[str, Any]],
    user_map_config: Optional[Dict[str, Any]],
    ctx: Context = None
) -> Dict[str, Any]:
    """配置工作台布局"""
    # 设置默认地图配置
    default_map_config = {
        "center": [39.9042, 116.4074],  # 默认北京
        "zoom": 10,
        "width": 1200,
        "height": 800
    }
    
    # 根据工作台类型调整配置
    if workspace_type == "comparison":
        default_map_config.update({
            "width": 600,  # 对比模式使用较小宽度
            "height": 400
        })
    elif workspace_type == "single":
        default_map_config.update({
            "width": 1000,
            "height": 700
        })
    
    # 合并用户配置
    if user_map_config:
        default_map_config.update(user_map_config)
    
    # 自动计算地图中心点（基于数据图层）
    if not user_map_config or "center" not in user_map_config:
        auto_center = await _calculate_optimal_center(processed_layers)
        if auto_center:
            default_map_config["center"] = auto_center
            if ctx:
                await ctx.info(f"自动计算地图中心点: {auto_center}")
    
    return default_map_config


def _summarize_layer_types(processed_layers: List[Dict[str, Any]]) -> Dict[str, int]:
    """统计图层类型"""
    type_counts = {}
    for layer in processed_layers:
        layer_type = layer.get("type", "unknown")
        type_counts[layer_type] = type_counts.get(layer_type, 0) + 1
    return type_counts


def _get_workspace_capabilities(workspace_type: str) -> List[str]:
    """获取工作台能力列表"""
    base_capabilities = [
        "交互式地图浏览",
        "图层控制和切换",
        "要素属性查看",
        "地图缩放和平移"
    ]
    
    if workspace_type == "layered":
        base_capabilities.extend([
            "多图层叠加显示",
            "图层透明度控制",
            "图层顺序调整"
        ])
    elif workspace_type == "comparison":
        base_capabilities.extend([
            "并排对比显示",
            "同步地图操作",
            "差异分析"
        ])
    elif workspace_type == "single":
        base_capabilities.extend([
            "专注单图层展示",
            "详细属性分析",
            "优化显示效果"
        ])
    
    return base_capabilities


def _get_workspace_features(workspace_type: str) -> List[str]:
    """获取工作台特性列表"""
    base_features = [
        "响应式地图界面",
        "多种图层类型支持",
        "智能样式配置"
    ]
    
    if workspace_type == "layered":
        base_features.extend([
            "分层地图可视化",
            "WMS底图和WFS数据图层叠加",
            "图层管理面板"
        ])
    elif workspace_type == "comparison":
        base_features.extend([
            "多图层对比视图",
            "并排显示界面",
            "同步操作控制"
        ])
    elif workspace_type == "single":
        base_features.extend([
            "单图层专注视图",
            "优化的显示效果",
            "详细信息展示"
        ])
    
    return base_features


def _calculate_geojson_stats(geojson_data: Dict[str, Any]) -> Dict[str, Any]:
    """计算GeoJSON统计信息"""
    try:
        features = geojson_data.get("features", [])
        
        if not features:
            return {"feature_count": 0}
        
        # 基本统计
        stats = {
            "feature_count": len(features),
            "geometry_types": {},
            "properties": {}
        }
        
        # 统计几何类型
        for feature in features:
            geometry = feature.get("geometry", {})
            geom_type = geometry.get("type", "Unknown")
            stats["geometry_types"][geom_type] = stats["geometry_types"].get(geom_type, 0) + 1
        
        # 统计属性字段（取第一个要素的属性作为示例）
        if features:
            first_feature = features[0]
            properties = first_feature.get("properties", {})
            stats["properties"] = {
                "field_count": len(properties),
                "sample_fields": list(properties.keys())[:10]  # 最多显示10个字段
            }
        
        return stats
        
    except Exception as e:
        logger.error(f"计算GeoJSON统计信息失败: {e}")
        return {"feature_count": 0, "error": str(e)}


async def _calculate_optimal_center(processed_layers: List[Dict[str, Any]]) -> Optional[List[float]]:
    """计算最优地图中心点"""
    try:
        # 收集所有GeoJSON数据的边界框
        all_bounds = []
        
        for layer in processed_layers:
            if layer.get("type") == "geojson":
                geojson_data = layer.get("geojson_data")
                if geojson_data:
                    bounds = _calculate_geojson_bounds(geojson_data)
                    if bounds:
                        all_bounds.append(bounds)
        
        if not all_bounds:
            return None
        
        # 计算总边界框
        min_lng = min(bounds[0] for bounds in all_bounds)
        min_lat = min(bounds[1] for bounds in all_bounds)
        max_lng = max(bounds[2] for bounds in all_bounds)
        max_lat = max(bounds[3] for bounds in all_bounds)
        
        # 计算中心点
        center_lat = (min_lat + max_lat) / 2
        center_lng = (min_lng + max_lng) / 2
        
        return [center_lat, center_lng]
        
    except Exception as e:
        logger.error(f"计算最优中心点失败: {e}")
        return None


def _calculate_geojson_bounds(geojson_data: Dict[str, Any]) -> Optional[List[float]]:
    """计算GeoJSON数据的边界框"""
    try:
        features = geojson_data.get("features", [])
        if not features:
            return None
        
        min_lng = float('inf')
        min_lat = float('inf')
        max_lng = float('-inf')
        max_lat = float('-inf')
        
        for feature in features:
            geometry = feature.get("geometry", {})
            coordinates = geometry.get("coordinates", [])
            
            # 递归处理不同类型的几何体
            coords_list = _flatten_coordinates(coordinates)
            
            for coord in coords_list:
                if len(coord) >= 2:
                    lng, lat = coord[0], coord[1]
                    min_lng = min(min_lng, lng)
                    min_lat = min(min_lat, lat)
                    max_lng = max(max_lng, lng)
                    max_lat = max(max_lat, lat)
        
        if min_lng == float('inf'):
            return None
        
        return [min_lng, min_lat, max_lng, max_lat]
        
    except Exception as e:
        logger.error(f"计算GeoJSON边界框失败: {e}")
        return None


def _flatten_coordinates(coordinates: Any) -> List[List[float]]:
    """递归展平坐标数组"""
    result = []
    
    if not coordinates:
        return result
    
    # 检查是否是坐标点 [lng, lat]
    if (isinstance(coordinates, list) and 
        len(coordinates) >= 2 and 
        isinstance(coordinates[0], (int, float)) and 
        isinstance(coordinates[1], (int, float))):
        return [coordinates]
    
    # 递归处理嵌套数组
    if isinstance(coordinates, list):
        for item in coordinates:
            result.extend(_flatten_coordinates(item))
    
    return result