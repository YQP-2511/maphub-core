"""可视化管理工具模块

提供图层管理和复合可视化功能，充分利用现有的web_server服务
不包含具体的图层添加功能（已独立为单独的工具文件）

核心工具：
- clear_visualization_layers: 清空当前图层列表
- list_current_layers: 列出当前图层
- create_composite_visualization: 创建多图层复合可视化
"""

import json
import logging
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP, Context
from pydantic import Field
from typing_extensions import Annotated

from ..services.web_server.server import get_web_server

logger = logging.getLogger(__name__)

# 创建可视化管理工具服务器
visualization_server = FastMCP(name="可视化管理工具")

# 全局图层存储（在实际应用中可以考虑使用更持久的存储）
_current_layers: List[Dict[str, Any]] = []


@visualization_server.tool
async def clear_visualization_layers(
    ctx: Context = None
) -> Dict[str, Any]:
    """清空当前图层列表
    
    清除所有已添加的图层，为新的可视化做准备
    
    Args:
        ctx: MCP上下文对象
        
    Returns:
        清空操作结果
    """
    global _current_layers
    
    layer_count = len(_current_layers)
    _current_layers.clear()
    
    if ctx:
        await ctx.info(f"已清空 {layer_count} 个图层，可以开始新的可视化")
    
    return {
        "success": True,
        "cleared_layer_count": layer_count,
        "current_layer_count": 0,
        "message": f"已清空 {layer_count} 个图层，图层列表已重置"
    }


@visualization_server.tool
async def list_current_layers(
    ctx: Context = None
) -> Dict[str, Any]:
    """列出当前已添加的图层
    
    显示当前图层列表的状态，包括图层类型和增强信息
    
    Args:
        ctx: MCP上下文对象
        
    Returns:
        当前图层列表信息
    """
    if not _current_layers:
        return {
            "success": True,
            "layer_count": 0,
            "layers": [],
            "message": "当前没有图层，请使用独立的图层添加工具添加图层"
        }
    
    layer_summaries = []
    for layer in _current_layers:
        summary = _create_layer_summary(layer)
        layer_summaries.append(summary)
    
    if ctx:
        await ctx.info(f"当前有 {len(_current_layers)} 个图层待可视化")
    
    return {
        "success": True,
        "layer_count": len(_current_layers),
        "layers": layer_summaries,
        "enhanced_features": {
            "dynamic_bbox_count": sum(1 for layer in _current_layers if layer.get("dynamic_bbox")),
            "feature_schema_count": sum(1 for layer in _current_layers if layer.get("feature_schema")),
            "total_features": sum(len(layer.get("geojson_data", {}).get("features", [])) for layer in _current_layers if layer.get("type") == "wfs")
        },
        "message": f"当前有 {len(_current_layers)} 个图层待可视化"
    }


@visualization_server.tool
async def create_composite_visualization(
    title: Annotated[str, Field(description="可视化标题")] = "多图层复合可视化",
    visualization_type: Annotated[str, Field(description="可视化类型: overlay(叠加显示), comparison(对比显示)")] = "overlay",
    auto_fit_bounds: Annotated[bool, Field(description="是否自动适配边界框")] = True,
    ctx: Context = None
) -> Dict[str, Any]:
    """创建多图层复合可视化
    
    将当前添加的所有图层组合成一个可视化页面
    支持叠加显示和对比显示两种模式
    充分利用现有的web_server服务
    使用AI智能选择主要图层作为中心点参考
    
    Args:
        title: 可视化标题
        visualization_type: 可视化类型（overlay或comparison）
        auto_fit_bounds: 是否自动适配边界框
        ctx: MCP上下文对象
        
    Returns:
        可视化结果，包含访问URL
    """
    try:
        if not _current_layers:
            return {
                "success": False,
                "error": "没有可用的图层",
                "message": "请先使用独立的图层添加工具添加图层"
            }
        
        if ctx:
            await ctx.info(f"正在创建{visualization_type}模式的复合可视化，包含 {len(_current_layers)} 个图层")
        
        # 获取web服务器实例
        web_server = await get_web_server()
        
        # 计算智能地图配置
        map_config = _calculate_intelligent_map_config(_current_layers, auto_fit_bounds)
        
        # 显示AI选择的主要图层信息
        if ctx and map_config.get("primary_layer"):
            primary_info = map_config["primary_layer"]
            await ctx.info(f"🎯 AI选择主要图层: {primary_info['title']} ({primary_info['type'].upper()})")
            await ctx.info(f"📍 地图中心点: {map_config['center']}, 缩放级别: {map_config['zoom']}")
        elif ctx:
            await ctx.info(f"📍 使用合并边界框，地图中心点: {map_config['center']}, 缩放级别: {map_config['zoom']}")
        
        if visualization_type == "overlay":
            result = await _create_overlay_visualization(
                web_server, _current_layers, title, map_config, ctx
            )
        elif visualization_type == "comparison":
            result = await _create_comparison_visualization(
                web_server, _current_layers, title, map_config, ctx
            )
        else:
            raise ValueError(f"不支持的可视化类型: {visualization_type}")
        
        if ctx:
            await ctx.info(f"✅ 复合可视化创建成功")
            await ctx.info(f"🌐 访问地址: {result['visualization_url']}")
        
        return result
        
    except Exception as e:
        error_msg = f"创建复合可视化失败: {e}"
        logger.error(error_msg)
        if ctx:
            await ctx.error(error_msg)
        raise


# 辅助函数

def _create_layer_summary(layer: Dict[str, Any]) -> Dict[str, Any]:
    """创建图层摘要信息"""
    summary = {
        "name": layer.get("name"),
        "title": layer.get("title"),
        "type": layer.get("type"),
        "service_type": layer.get("service_type")
    }
    
    # 添加类型特定信息
    if layer.get("type") == "wms":
        summary.update({
            "wms_url": layer.get("wms_url"),
            "has_dynamic_bbox": bool(layer.get("dynamic_bbox")),
            "styles_count": len(layer.get("styles", []))
        })
    elif layer.get("type") == "wfs":
        geojson_data = layer.get("geojson_data", {})
        features = geojson_data.get("features", [])
        summary.update({
            "feature_count": len(features),
            "geometry_types": layer.get("stats", {}).get("geometry_types", []),
            "has_feature_schema": bool(layer.get("feature_schema")),
            "filter_applied": bool(layer.get("filter_info", {}).get("cql_filter"))
        })
    elif layer.get("type") == "wmts":
        summary.update({
            "wmts_url": layer.get("wmts_url"),
            "tile_matrix_sets": layer.get("tile_matrix_sets", []),
            "available_formats": layer.get("available_formats", [])
        })
    
    # 添加边界框信息
    if layer.get("bbox"):
        summary["bbox"] = layer["bbox"]
        summary["bbox_source"] = layer.get("bbox_source", "static")
    
    return summary


def _calculate_intelligent_map_config(
    layers: List[Dict[str, Any]], 
    auto_fit_bounds: bool
) -> Dict[str, Any]:
    """计算智能地图配置
    
    基于图层信息和AI智能分析计算最佳的地图中心点、缩放级别和边界框
    优先选择最重要的图层作为中心点参考
    """
    config = {
        "width": 1200,
        "height": 800,
        "center": [39.9042, 116.4074],  # 默认北京
        "zoom": 10,
        "bbox": None,
        "primary_layer": None
    }
    
    if not auto_fit_bounds or not layers:
        return config
    
    # AI智能选择主要图层
    primary_layer = _select_primary_layer_with_ai(layers)
    
    if primary_layer:
        config["primary_layer"] = {
            "name": primary_layer.get("name"),
            "title": primary_layer.get("title"),
            "type": primary_layer.get("type")
        }
        
        # 使用主要图层的边界框计算中心点
        primary_bbox = primary_layer.get("bbox")
        if primary_bbox and len(primary_bbox) == 4:
            if _is_valid_bbox(primary_bbox):
                center_config = _calculate_center_from_bbox(primary_bbox)
                config.update(center_config)
                
                # 根据主要图层类型调整缩放级别
                zoom_adjustment = _get_zoom_adjustment_for_layer(primary_layer)
                config["zoom"] = min(config["zoom"] + zoom_adjustment, 18)
                
                return config
    
    # 如果没有找到合适的主要图层，使用原有的合并逻辑
    return _calculate_fallback_map_config(layers)


def _select_primary_layer_with_ai(layers: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """AI智能选择主要图层
    
    基于多个因素评估图层重要性：
    1. 图层类型优先级（WFS > WMS > WMTS）
    2. 数据丰富度（要素数量、属性数量）
    3. 空间范围合理性
    4. 图层名称语义分析
    """
    if not layers:
        return None
    
    layer_scores = []
    
    for layer in layers:
        score = 0
        layer_info = {
            "layer": layer,
            "score": 0,
            "reasons": []
        }
        
        # 1. 图层类型评分（WFS最高，因为包含详细的矢量数据）
        layer_type = layer.get("type", "").lower()
        if layer_type == "wfs":
            score += 100
            layer_info["reasons"].append("WFS矢量图层(+100)")
        elif layer_type == "wms":
            score += 70
            layer_info["reasons"].append("WMS栅格图层(+70)")
        elif layer_type == "wmts":
            score += 50
            layer_info["reasons"].append("WMTS瓦片图层(+50)")
        
        # 2. 数据丰富度评分
        if layer_type == "wfs":
            # WFS图层：基于要素数量
            geojson_data = layer.get("geojson_data", {})
            feature_count = len(geojson_data.get("features", []))
            if feature_count > 0:
                # 要素数量评分：1-10个(+20), 11-100个(+40), 100+个(+60)
                if feature_count <= 10:
                    score += 20
                    layer_info["reasons"].append(f"要素数量适中({feature_count}个, +20)")
                elif feature_count <= 100:
                    score += 40
                    layer_info["reasons"].append(f"要素数量丰富({feature_count}个, +40)")
                else:
                    score += 60
                    layer_info["reasons"].append(f"要素数量很多({feature_count}个, +60)")
            
            # 属性丰富度
            attributes = layer.get("attributes", [])
            if len(attributes) > 5:
                score += 20
                layer_info["reasons"].append(f"属性丰富({len(attributes)}个属性, +20)")
        
        # 3. 边界框合理性评分
        bbox = layer.get("bbox")
        if bbox and _is_valid_bbox(bbox):
            bbox_area = abs((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
            
            # 面积合理性评分（避免过大或过小的区域）
            if 0.001 <= bbox_area <= 100:  # 合理的地理范围
                score += 30
                layer_info["reasons"].append(f"空间范围合理(面积:{bbox_area:.4f}, +30)")
            elif bbox_area < 0.001:
                score += 10  # 太小的区域
                layer_info["reasons"].append(f"空间范围较小(面积:{bbox_area:.6f}, +10)")
            else:
                score += 5   # 太大的区域
                layer_info["reasons"].append(f"空间范围较大(面积:{bbox_area:.2f}, +5)")
        
        # 4. 图层名称语义分析
        layer_name = layer.get("name", "").lower()
        layer_title = layer.get("title", "").lower()
        
        # 重要关键词检测
        important_keywords = [
            "states", "countries", "cities", "roads", "buildings", 
            "boundaries", "administrative", "population", "economic"
        ]
        
        for keyword in important_keywords:
            if keyword in layer_name or keyword in layer_title:
                score += 15
                layer_info["reasons"].append(f"包含重要关键词'{keyword}'(+15)")
                break
        
        # 5. 过滤器应用评分（有过滤器说明用户关注此图层）
        if layer.get("filter_info", {}).get("cql_filter"):
            score += 25
            layer_info["reasons"].append("应用了过滤器(+25)")
        
        # 6. 动态边界框评分（说明图层有实时数据）
        if layer.get("dynamic_bbox") or layer.get("bbox_source") == "dynamic":
            score += 15
            layer_info["reasons"].append("具有动态边界框(+15)")
        
        layer_info["score"] = score
        layer_scores.append(layer_info)
    
    # 按评分排序
    layer_scores.sort(key=lambda x: x["score"], reverse=True)
    
    # 返回评分最高的图层
    if layer_scores:
        best_layer_info = layer_scores[0]
        logger.info(f"AI选择主要图层: {best_layer_info['layer'].get('title', 'Unknown')} "
                   f"(评分: {best_layer_info['score']}, 原因: {', '.join(best_layer_info['reasons'])})")
        return best_layer_info["layer"]
    
    return None


def _is_valid_bbox(bbox: List[float]) -> bool:
    """验证边界框有效性"""
    if not bbox or len(bbox) != 4:
        return False
    
    return (bbox[0] < bbox[2] and bbox[1] < bbox[3] and 
            -180 <= bbox[0] <= 180 and -180 <= bbox[2] <= 180 and
            -90 <= bbox[1] <= 90 and -90 <= bbox[3] <= 90)


def _calculate_center_from_bbox(bbox: List[float]) -> Dict[str, Any]:
    """从边界框计算中心点和缩放级别"""
    center_lon = (bbox[0] + bbox[2]) / 2
    center_lat = (bbox[1] + bbox[3]) / 2
    
    # 计算智能缩放级别
    bbox_width = abs(bbox[2] - bbox[0])
    bbox_height = abs(bbox[3] - bbox[1])
    bbox_area = bbox_width * bbox_height
    
    if bbox_area < 0.001:
        zoom = 18
    elif bbox_area < 0.01:
        zoom = 15
    elif bbox_area < 0.1:
        zoom = 12
    elif bbox_area < 1:
        zoom = 10
    elif bbox_area < 10:
        zoom = 8
    elif bbox_area < 100:
        zoom = 6
    else:
        zoom = 4
    
    return {
        "center": [center_lat, center_lon],  # Leaflet使用[lat, lon]格式
        "zoom": zoom,
        "bbox": bbox
    }


def _get_zoom_adjustment_for_layer(layer: Dict[str, Any]) -> int:
    """根据图层类型获取缩放级别调整值"""
    layer_type = layer.get("type", "").lower()
    
    # WFS矢量数据通常需要更高的缩放级别来显示细节
    if layer_type == "wfs":
        feature_count = len(layer.get("geojson_data", {}).get("features", []))
        if feature_count <= 10:
            return 2  # 少量要素，放大更多
        elif feature_count <= 100:
            return 1  # 适量要素，稍微放大
        else:
            return 0  # 大量要素，保持原缩放
    
    # WMS栅格数据
    elif layer_type == "wms":
        return 0  # 保持原缩放
    
    # WMTS瓦片数据
    elif layer_type == "wmts":
        return -1  # 稍微缩小以显示更大范围
    
    return 0


def _calculate_fallback_map_config(layers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """备用的地图配置计算（原有逻辑）"""
    config = {
        "width": 1200,
        "height": 800,
        "center": [39.9042, 116.4074],  # 默认北京
        "zoom": 10,
        "bbox": None
    }
    
    # 收集有效的边界框
    valid_bboxes = []
    for layer in layers:
        bbox = layer.get("bbox")
        if bbox and _is_valid_bbox(bbox):
            valid_bboxes.append(bbox)
    
    if not valid_bboxes:
        return config
    
    # 计算合并边界框
    min_lon = min(bbox[0] for bbox in valid_bboxes)
    min_lat = min(bbox[1] for bbox in valid_bboxes)
    max_lon = max(bbox[2] for bbox in valid_bboxes)
    max_lat = max(bbox[3] for bbox in valid_bboxes)
    
    merged_bbox = [min_lon, min_lat, max_lon, max_lat]
    center_config = _calculate_center_from_bbox(merged_bbox)
    config.update(center_config)
    
    # 如果包含矢量数据，可以放大一级
    has_vector = any(layer.get("type") == "wfs" for layer in layers)
    if has_vector:
        config["zoom"] = min(config["zoom"] + 1, 18)
    
    return config


async def _create_overlay_visualization(
    web_server, 
    layers: List[Dict[str, Any]], 
    title: str, 
    map_config: Dict[str, Any], 
    ctx: Context
) -> Dict[str, Any]:
    """创建叠加可视化
    
    利用web_server的复合可视化功能
    """
    try:
        # 使用web_server的add_composite_visualization方法
        visualization_url = await web_server.add_composite_visualization(
            title=title,
            layers=layers,
            map_config=map_config
        )
        
        return {
            "success": True,
            "visualization_type": "overlay",
            "visualization_url": visualization_url,
            "layer_count": len(layers),
            "title": title,
            "map_config": map_config,
            "message": f"叠加可视化已创建，包含 {len(layers)} 个图层"
        }
        
    except Exception as e:
        logger.error(f"创建叠加可视化失败: {e}")
        raise


async def _create_comparison_visualization(
    web_server, 
    layers: List[Dict[str, Any]], 
    title: str, 
    map_config: Dict[str, Any], 
    ctx: Context
) -> Dict[str, Any]:
    """创建对比可视化
    
    利用web_server的复合可视化功能
    """
    try:
        # 使用web_server的add_composite_visualization方法
        visualization_url = await web_server.add_composite_visualization(
            title=title,
            layers=layers,
            map_config=map_config
        )
        
        return {
            "success": True,
            "visualization_type": "comparison", 
            "visualization_url": visualization_url,
            "layer_count": len(layers),
            "title": title,
            "map_config": map_config,
            "message": f"对比可视化已创建，包含 {len(layers)} 个图层"
        }
        
    except Exception as e:
        logger.error(f"创建对比可视化失败: {e}")
        raise


# 提供给其他工具使用的函数

def add_layer_to_visualization(layer: Dict[str, Any]) -> None:
    """添加图层到可视化列表
    
    供独立的图层添加工具调用
    """
    global _current_layers
    _current_layers.append(layer)


def get_current_layers() -> List[Dict[str, Any]]:
    """获取当前图层列表
    
    供其他模块查询使用
    """
    return _current_layers.copy()


def get_layer_count() -> int:
    """获取当前图层数量"""
    return len(_current_layers)