"""Web模板模块

提供Web页面模板生成功能
"""

import json
import logging
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class WebTemplates:
    """Web模板生成器"""
    def generate_index_page(self, visualizations: Dict[str, Any], 
                           server_info: Dict[str, Any]) -> str:
        """生成首页HTML
        
        Args:
            visualizations: 可视化列表
            server_info: 服务器信息
            
        Returns:
            首页HTML内容
        """
        # 统计信息
        total_viz = len(visualizations)
        wms_count = len([v for v in visualizations.values() if v['type'] == 'wms'])
        wfs_count = len([v for v in visualizations.values() if v['type'] == 'geojson'])
        composite_count = len([v for v in visualizations.values() if v['type'] == 'composite'])
        
        # 计算图层总数（包括复合可视化中的图层）
        total_layers = 0
        for viz in visualizations.values():
            if viz['type'] == 'composite':
                total_layers += len(viz.get('layers', []))
            else:
                total_layers += 1
        
        # 生成可视化列表HTML
        viz_list_html = ""
        if visualizations:
            # 按创建时间排序，最新的在前
            sorted_viz = sorted(
                visualizations.items(), 
                key=lambda x: x[1].get('created_at', 0), 
                reverse=True
            )
            
            viz_list_html = "<div class='visualization-grid'>"
            for viz_id, viz_info in sorted_viz:
                viz_list_html += self._generate_viz_card(viz_id, viz_info)
            viz_list_html += "</div>"
        else:
            viz_list_html = """
            <div class='empty-state'>
                <div class='empty-icon'>🗺️</div>
                <h3>暂无可视化内容</h3>
                <p>使用MCP工具生成复合地图可视化后，结果将在这里显示</p>
                <div class='empty-actions'>
                    <p class='empty-hint'>支持的图层类型：WMS、WMTS、WFS、GeoJSON</p>
                </div>
            </div>
            """
        
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OGC 复合地图可视化服务器</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 300;
        }}
        
        .header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
        }}
        
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }}
        
        .stat-card:hover {{
            transform: translateY(-2px);
        }}
        
        .stat-number {{
            font-size: 2.5em;
            font-weight: bold;
            color: #3498db;
            margin-bottom: 5px;
        }}
        
        .stat-label {{
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .content {{
            padding: 30px;
        }}
        
        .section-title {{
            font-size: 1.8em;
            color: #2c3e50;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #3498db;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .section-title::before {{
            content: "🗺️";
            font-size: 0.8em;
        }}
        
        .visualization-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
            gap: 25px;
            margin-top: 20px;
        }}
        
        .viz-card {{
            background: white;
            border: 1px solid #e1e8ed;
            border-radius: 12px;
            overflow: hidden;
            transition: all 0.3s;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        
        .viz-card:hover {{
            transform: translateY(-6px);
            box-shadow: 0 12px 30px rgba(0,0,0,0.15);
        }}
        
        .viz-header {{
            padding: 20px;
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            position: relative;
        }}
        
        .viz-type {{
            display: inline-block;
            background: rgba(255,255,255,0.25);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.75em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 12px;
            font-weight: 600;
        }}
        
        .viz-title {{
            font-size: 1.3em;
            font-weight: bold;
            margin-bottom: 8px;
            line-height: 1.3;
        }}
        
        .viz-subtitle {{
            opacity: 0.9;
            font-size: 0.9em;
            line-height: 1.4;
        }}
        
        .viz-body {{
            padding: 20px;
        }}
        
        .viz-info {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 20px;
        }}
        
        .info-item {{
            background: #f8f9fa;
            padding: 12px;
            border-radius: 6px;
            border-left: 3px solid #3498db;
        }}
        
        .info-label {{
            font-size: 0.75em;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 6px;
            font-weight: 600;
        }}
        
        .info-value {{
            font-weight: bold;
            color: #2c3e50;
            font-size: 0.95em;
        }}
        
        .viz-actions {{
            display: flex;
            gap: 12px;
        }}
        
        .btn {{
            flex: 1;
            padding: 12px 20px;
            border: none;
            border-radius: 6px;
            text-decoration: none;
            text-align: center;
            font-weight: 600;
            transition: all 0.2s;
            cursor: pointer;
            font-size: 0.9em;
        }}
        
        .btn-primary {{
            background: #3498db;
            color: white;
        }}
        
        .btn-primary:hover {{
            background: #2980b9;
            transform: translateY(-1px);
        }}
        
        .btn-secondary {{
            background: #95a5a6;
            color: white;
        }}
        
        .btn-secondary:hover {{
            background: #7f8c8d;
        }}
        
        .empty-state {{
            text-align: center;
            padding: 60px 20px;
            color: #666;
        }}
        
        .empty-icon {{
            font-size: 4em;
            margin-bottom: 20px;
            opacity: 0.5;
        }}
        
        .empty-state h3 {{
            font-size: 1.5em;
            margin-bottom: 10px;
            color: #2c3e50;
        }}
        
        .empty-state p {{
            font-size: 1.1em;
            margin-bottom: 20px;
        }}
        
        .empty-actions {{
            margin-top: 30px;
        }}
        
        .empty-hint {{
            background: #e8f4fd;
            color: #2980b9;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #3498db;
            font-size: 0.95em !important;
            margin: 0 !important;
        }}
        
        .layer-count {{
            background: rgba(255,255,255,0.2);
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.8em;
            margin-left: 8px;
        }}
        
        .composite-layers {{
            grid-column: 1 / -1;
            background: #e8f4fd;
            padding: 12px;
            border-radius: 6px;
            border-left: 3px solid #3498db;
        }}
        
        .composite-layers .info-label {{
            color: #2980b9;
        }}
        
        .composite-layers .info-value {{
            color: #2c3e50;
            font-size: 0.9em;
        }}
        
        @media (max-width: 768px) {{
            .visualization-grid {{
                grid-template-columns: 1fr;
            }}
            
            .stats {{
                grid-template-columns: repeat(2, 1fr);
            }}
            
            .viz-info {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>OGC 复合地图可视化</h1>
            <p>多图层地理信息可视化平台 - 支持 WMS、WMTS、WFS、GeoJSON</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{total_viz}</div>
                <div class="stat-label">可视化总数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{composite_count}</div>
                <div class="stat-label">复合地图</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{total_layers}</div>
                <div class="stat-label">图层总数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{server_info.get('port', 8080)}</div>
                <div class="stat-label">服务端口</div>
            </div>
        </div>
        
        <div class="content">
            <h2 class="section-title">可视化列表</h2>
            {viz_list_html}
        </div>
    </div>
    
    <script>
        // 自动刷新页面（每30秒）
        setTimeout(() => {{
            location.reload();
        }}, 30000);
        
        // 删除可视化
        function deleteVisualization(vizId) {{
            if (confirm('确定要删除这个可视化吗？')) {{
                fetch(`/api/visualizations/${{vizId}}`, {{
                    method: 'DELETE'
                }})
                .then(response => response.json())
                .then(data => {{
                    alert('删除成功');
                    location.reload();
                }})
                .catch(error => {{
                    alert('删除失败: ' + error);
                }});
            }}
        }}
    </script>
</body>
</html>"""
        
        return html_content
    
    def generate_composite_map(self, title: str, layers: List[Dict[str, Any]], 
                              map_config: Dict[str, Any]) -> str:
        """生成复合地图HTML - 全屏优化版本，调整布局：图层面板左侧，操作框右侧，无顶部标题"""
        # 获取地图参数
        zoom = map_config.get('zoom', 10)
        center = map_config.get('center', [39.9042, 116.4074])
        
        # 生成图层JavaScript代码
        layers_js = self._generate_layers_javascript(layers)
        
        # 生成左侧图层信息HTML
        layers_info_html = self._generate_layers_info_html_left(layers)
        
        # 优化图层类型显示
        layer_types = []
        for layer in layers:
            if layer['type'] == 'geojson':
                layer_types.append('WFS')
            else:
                layer_types.append(layer['type'].upper())
        
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - 全屏地理可视化</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        {self._get_composite_map_styles_modified(1920, 1080)}
    </style>
</head>
<body>
    <div class="map-container">
        {layers_info_html}
        
        <!-- 右侧工具栏 -->
        <div class="toolbar-right">
            <div class="tool-button" onclick="toggleFullscreen()" title="全屏切换">
                🔳
            </div>
            <div class="tool-button" onclick="fitToLayers()" title="缩放到图层">
                🎯
            </div>
            <div class="tool-button" onclick="toggleMeasure()" title="测量工具">
                📏
            </div>
        </div>
        
        <div id="map"></div>
        
        <div class="controls">
            <div class="control-group">
                <span class="control-label">🎯 中心点:</span>
                <span class="control-value" id="center-coords">{center[0]:.4f}, {center[1]:.4f}</span>
            </div>
            <div class="control-group">
                <span class="control-label">🔍 缩放级别:</span>
                <span class="control-value" id="zoom-level">{zoom}</span>
            </div>
            <div class="control-group">
                <span class="control-label">📍 鼠标位置:</span>
                <span class="control-value" id="mouse-coords">移动鼠标查看坐标</span>
            </div>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdn.jsdelivr.net/gh/alexandre-melard/leaflet.TileLayer.WMTS@master/leaflet-tilelayer-wmts.js"></script>
    <script>
        {self._get_enhanced_map_javascript(center, zoom, layers_js)}
    </script>
</body>
</html>"""
        
        return html_content
    
    def _generate_viz_card(self, viz_id: str, viz_info: Dict[str, Any]) -> str:
        """生成可视化卡片HTML
        
        Args:
            viz_id: 可视化ID
            viz_info: 可视化信息
            
        Returns:
            可视化卡片HTML
        """
        viz_type = viz_info.get('type', 'unknown')
        layer_name = viz_info.get('layer_name', '未知图层')
        layer_info = viz_info.get('layer_info', {})
        created_at = viz_info.get('created_at_formatted', '未知时间')
        
        # 根据类型设置不同的显示信息
        if viz_type == 'composite':
            layers = viz_info.get('layers', [])
            layer_count = len(layers)
            type_display = f"复合地图 ({layer_count} 图层)"
            
            # 统计不同类型的图层
            layer_types = {}
            for layer in layers:
                layer_type = layer.get('type', 'unknown')
                layer_types[layer_type] = layer_types.get(layer_type, 0) + 1
            
            layer_summary = ", ".join([f"{count}个{type_name.upper()}" 
                                     for type_name, count in layer_types.items()])
            
            info_items = f"""
                <div class="info-item">
                    <div class="info-label">图层数量</div>
                    <div class="info-value">{layer_count} 个</div>
                </div>
                <div class="info-item">
                    <div class="info-label">创建时间</div>
                    <div class="info-value">{created_at}</div>
                </div>
                <div class="composite-layers">
                    <div class="info-label">图层组成</div>
                    <div class="info-value">{layer_summary}</div>
                </div>
            """
        else:
            type_display = viz_type.upper()
            service_name = layer_info.get('service_name', '未知服务')
            crs = layer_info.get('crs', 'EPSG:4326')
            
            info_items = f"""
                <div class="info-item">
                    <div class="info-label">服务名称</div>
                    <div class="info-value">{service_name}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">坐标系统</div>
                    <div class="info-value">{crs}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">创建时间</div>
                    <div class="info-value">{created_at}</div>
                </div>
            """
        
        return f"""
        <div class="viz-card">
            <div class="viz-header">
                <div class="viz-type">{type_display}</div>
                <div class="viz-title">{layer_name}</div>
                <div class="viz-subtitle">{layer_info.get('layer_title', '')}</div>
            </div>
            <div class="viz-body">
                <div class="viz-info">
                    {info_items}
                </div>
                <div class="viz-actions">
                    <a href="{viz_info['url']}" class="btn btn-primary" target="_blank">查看地图</a>
                    <button onclick="deleteVisualization('{viz_id}')" class="btn btn-secondary">删除</button>
                </div>
            </div>
        </div>
        """
    
    def _generate_layers_javascript(self, layers: List[Dict[str, Any]]) -> str:
        """生成图层JavaScript代码"""
        layers_js = []
        
        for i, layer in enumerate(layers):
            if layer["type"] == "wms":
                # 修复WMS图层显示问题
                service_url = layer["service_url"]
                layer_name = layer["layer_name"]
                styles = layer.get("styles", [""])
                style = styles[0] if styles else ""
                
                # 确保使用正确的WMS服务URL
                if "gwc/service/wmts" in service_url:
                    # 如果是WMTS URL，替换为WMS URL
                    service_url = service_url.replace("gwc/service/wmts", "ows")
                elif "ows" not in service_url and "wms" not in service_url.lower():
                    # 确保使用正确的WMS端点
                    service_url = service_url.rstrip('/') + '/ows'
                
                layer_js = f"""
                var wmsLayer{i} = L.tileLayer.wms('{service_url}', {{
                    layers: '{layer_name}',
                    format: 'image/png',
                    transparent: true,
                    opacity: {layer.get("opacity", 0.8)},
                    styles: '{style}',
                    crs: L.CRS.EPSG3857,
                    // 确保与地图坐标系一致
                    version: '1.3.0',
                    // 添加调试信息
                    attribution: 'WMS Layer'
                }});
                
                // WMS图层加载监控
                wmsLayer{i}.on('load', function() {{
                    console.log('✅ WMS图层加载成功: {layer["name"]}');
                }});
                
                wmsLayer{i}.on('loading', function() {{
                    console.log('🔄 WMS图层加载中: {layer["name"]}');
                }});
                
                wmsLayer{i}.on('tileerror', function(error) {{
                    console.warn('❌ WMS瓦片加载失败: {layer["name"]}');
                    console.warn('服务URL:', '{service_url}');
                    console.warn('图层名称:', '{layer_name}');
                }});
                
                layerControl.addOverlay(wmsLayer{i}, '{layer["name"]} (WMS)');
                if ({str(layer.get("visible", True)).lower()}) {{
                    wmsLayer{i}.addTo(map);
                }}
                """
                
            elif layer["type"] == "wmts":
                # 智能WMTS坐标系匹配 - 优先使用Web Mercator
                tile_matrix_set = layer.get("tile_matrix_set", "EPSG:4326")
                style = layer.get("style", "default")
                format_type = layer.get("format", "image/png")
                service_url = layer["service_url"]
                
                # 智能选择最佳瓦片矩阵集
                # 优先使用Web Mercator兼容的瓦片矩阵集
                if "EPSG:900913" in tile_matrix_set or "GoogleMapsCompatible" in tile_matrix_set:
                    # 使用Web Mercator瓦片矩阵集
                    wmts_crs = "L.CRS.EPSG3857"
                    actual_matrix_set = "EPSG:900913"  # 强制使用Web Mercator矩阵集
                    origin_config = ""
                    tile_size = 256
                    zoom_offset = 0
                    min_zoom = 0
                    max_zoom = 18
                elif "EPSG:3857" in tile_matrix_set:
                    # 标准Web Mercator
                    wmts_crs = "L.CRS.EPSG3857"
                    actual_matrix_set = tile_matrix_set
                    origin_config = ""
                    tile_size = 256
                    zoom_offset = 0
                    min_zoom = 0
                    max_zoom = 18
                else:
                    # EPSG:4326或其他坐标系 - 尝试转换到Web Mercator
                    wmts_crs = "L.CRS.EPSG3857"
                    # 如果服务支持EPSG:900913，优先使用它
                    actual_matrix_set = "EPSG:900913"  # 假设服务支持，如果不支持会在错误处理中显示
                    origin_config = ""
                    tile_size = 256
                    zoom_offset = 0
                    min_zoom = 0
                    max_zoom = 18
                
                base_url = service_url.rstrip('?').rstrip('&')
                
                layer_js = f"""
                var wmtsLayer{i} = new L.TileLayer.WMTS('{base_url}', {{
                    layer: '{layer["layer_name"]}',
                    style: '{style}',
                    tilematrixSet: '{actual_matrix_set}',
                    format: '{format_type}',
                    opacity: {layer.get("opacity", 0.8)},
                    attribution: 'WMTS Layer ({actual_matrix_set})',
                    minZoom: {min_zoom},
                    maxZoom: {max_zoom},
                    // 使用Web Mercator坐标系确保与底图对齐
                    crs: {wmts_crs},
                    // 瓦片配置
                    tileSize: {tile_size},
                    zoomOffset: {zoom_offset},
                    // 禁用动画确保对齐
                    fadeAnimation: false,
                    zoomAnimation: false,
                    // 错误瓦片处理
                    errorTileUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVQIHWNgAAIAAAUAAY27m/MAAAAASUVORK5CYII=',
                    // 优化瓦片加载
                    keepBuffer: 2,
                    updateWhenIdle: false,
                    updateWhenZooming: true,
                    // 确保连续显示
                    continuousWorld: false,
                    noWrap: false
                }});
                
                // 坐标系统兼容性检查
                wmtsLayer{i}.on('add', function() {{
                    var mapCRS = map.options.crs.code || 'EPSG:3857';
                    var layerCRS = '{actual_matrix_set}';
                    
                    console.log('=== WMTS图层坐标系检查 ===');
                    console.log('地图CRS:', mapCRS);
                    console.log('WMTS瓦片矩阵集:', layerCRS);
                    console.log('图层名称:', '{layer["layer_name"]}');
                    
                    // 检查坐标系兼容性
                    var isOptimal = false;
                    if ((mapCRS === 'EPSG:3857' || mapCRS === 'EPSG:900913') && 
                        (layerCRS === 'EPSG:3857' || layerCRS === 'EPSG:900913')) {{
                        console.log('✅ 坐标系完全匹配 - 最佳性能');
                        isOptimal = true;
                    }} else if (mapCRS === 'EPSG:3857' && layerCRS.includes('4326')) {{
                        console.warn('⚠️ 坐标系不匹配，但已启用自动转换');
                        console.warn('建议使用EPSG:900913瓦片矩阵集以获得最佳性能');
                    }}
                    
                    // 显示瓦片矩阵集信息
                    console.log('可用缩放级别: {min_zoom}-{max_zoom}');
                    console.log('瓦片大小: {tile_size}x{tile_size}');
                }});
                
                // 增强的瓦片加载监控
                var tileLoadCount{i} = 0;
                var tileErrorCount{i} = 0;
                var lastSuccessTime{i} = 0;
                var lastErrorTime{i} = 0;
                
                wmtsLayer{i}.on('tileload', function(event) {{
                    tileLoadCount{i}++;
                    var now = Date.now();
                    
                    // 每15秒记录一次成功统计
                    if (now - lastSuccessTime{i} > 15000) {{
                        console.log('✅ WMTS瓦片加载统计 [{layer["name"]}]:');
                        console.log('  - 成功: ' + tileLoadCount{i} + ' 个瓦片');
                        console.log('  - 失败: ' + tileErrorCount{i} + ' 个瓦片');
                        console.log('  - 成功率: ' + ((tileLoadCount{i} / (tileLoadCount{i} + tileErrorCount{i}) * 100) || 0).toFixed(1) + '%');
                        lastSuccessTime{i} = now;
                    }}
                }});
                
                wmtsLayer{i}.on('tileerror', function(error) {{
                    tileErrorCount{i}++;
                    var currentZoom = map.getZoom();
                    var now = Date.now();
                    
                    // 限制错误日志频率，避免刷屏
                    if (now - lastErrorTime{i} > 5000) {{
                        console.warn('❌ WMTS瓦片加载失败 [{layer["name"]}]:');
                        console.warn('  - 当前缩放级别: Z' + currentZoom);
                        console.warn('  - 累计失败: ' + tileErrorCount{i} + ' 次');
                        console.warn('  - 瓦片矩阵集: {actual_matrix_set}');
                        
                        // 提供解决建议
                        if ('{actual_matrix_set}' === 'EPSG:4326') {{
                            console.warn('  💡 建议: 尝试使用EPSG:900913瓦片矩阵集');
                        }} else if (currentZoom > 18) {{
                            console.warn('  💡 建议: 当前缩放级别可能超出数据范围');
                        }}
                        
                        lastErrorTime{i} = now;
                    }}
                }});
                
                // 图层加载完成事件
                wmtsLayer{i}.on('load', function() {{
                    console.log('🎯 WMTS图层加载完成: {layer["name"]}');
                    console.log('  - 瓦片矩阵集: {actual_matrix_set}');
                    console.log('  - 坐标系: {wmts_crs}');
                }});
                
                // 添加到图层控制器
                layerControl.addOverlay(wmtsLayer{i}, '{layer["name"]} (WMTS-{actual_matrix_set})');
                if ({str(layer.get("visible", True)).lower()}) {{
                    wmtsLayer{i}.addTo(map);
                }}
                """
                
            elif layer["type"] == "geojson":
                geojson_str = json.dumps(layer["geojson_data"])
                style_str = json.dumps(layer["style"])
                
                layer_js = f"""
                var geojsonData{i} = {geojson_str};
                var geojsonLayer{i} = L.geoJSON(geojsonData{i}, {{
                    style: {style_str},
                    pointToLayer: function(feature, latlng) {{
                        return L.circleMarker(latlng, {style_str});
                    }},
                    onEachFeature: function(feature, layer) {{
                        if (feature.properties) {{
                            var popupContent = '<div class="popup-title">要素属性</div>';
                            popupContent += '<div class="popup-properties">';
                            for (var key in feature.properties) {{
                                var value = feature.properties[key];
                                if (value !== null && value !== undefined) {{
                                    popupContent += '<div class="popup-property">';
                                    popupContent += '<span class="property-key">' + key + ':</span>';
                                    popupContent += '<span class="property-value">' + value + '</span>';
                                    popupContent += '</div>';
                                }}
                            }}
                            popupContent += '</div>';
                            layer.bindPopup(popupContent);
                            
                            // 鼠标悬停高亮
                            layer.on('mouseover', function(e) {{
                                var layer = e.target;
                                if (layer.setStyle) {{
                                    layer.setStyle({{
                                        weight: 5,
                                        color: '#ff7800',
                                        fillOpacity: 0.5
                                    }});
                                }}
                            }});
                            
                            layer.on('mouseout', function(e) {{
                                geojsonLayer{i}.resetStyle(e.target);
                            }});
                        }}
                    }}
                }});
                
                // 将图层添加到边界框数组中，用于自动缩放
                if (geojsonLayer{i}.getBounds && geojsonLayer{i}.getBounds().isValid()) {{
                    allLayerBounds.push(geojsonLayer{i});
                }}
                
                layerControl.addOverlay(geojsonLayer{i}, '{layer["name"]} (WFS)');
                if ({str(layer.get("visible", True)).lower()}) {{
                    geojsonLayer{i}.addTo(map);
                }}
                """
            
            layers_js.append(layer_js)
        
        return '\n'.join(layers_js)
    
    def _generate_layers_info_html(self, layers: List[Dict[str, Any]]) -> str:
        """生成图层信息HTML - 移除服务地址显示和工具栏"""
        layers_html = '''
        <div class="layers-panel" id="layersPanel">
            <div class="panel-header" onclick="toggleLayersPanel()">
                <div class="panel-title">🗂️ 图层信息</div>
                <div class="panel-toggle">▼</div>
            </div>
            <div class="panel-content">
        '''
        
        for i, layer in enumerate(layers):
            layer_type = 'WFS' if layer['type'] == 'geojson' else layer['type'].upper()
            layer_source = layer.get('layer_info', {}).get('service_name', '未知来源')
            layer_title = layer.get('layer_info', {}).get('layer_title', layer['name'])
            
            # 生成图层缩略图
            thumbnail_text = self._get_layer_thumbnail(layer['type'])
            thumbnail_color = self._get_layer_color(layer['type'])
            
            # 获取图层详细信息（不包含服务地址）
            layer_details = self._get_layer_details_without_url(layer)
            
            layers_html += f'''
            <div class="layer-card" data-layer-index="{i}">
                <div class="layer-header">
                    <div class="layer-thumbnail" style="background: {thumbnail_color};">
                        {thumbnail_text}
                    </div>
                    <div class="layer-info">
                        <div class="layer-name" title="{layer['name']}">{layer['name']}</div>
                        <div class="layer-type">{layer_type}</div>
                    </div>
                </div>
                <div class="layer-details">
                    <div><strong>标题:</strong> {layer_title}</div>
                    <div><strong>来源:</strong> {layer_source}</div>
                    {layer_details}
                </div>
            </div>
            '''
        
        layers_html += '''
            </div>
        </div>
        '''
        
        return layers_html
    
    def _get_layer_thumbnail(self, layer_type: str) -> str:
        """获取图层缩略图文本"""
        thumbnails = {
            'wms': 'WMS',
            'wmts': 'WMTS', 
            'geojson': 'WFS',
            'wfs': 'WFS'
        }
        return thumbnails.get(layer_type.lower(), 'UNK')
    
    def _get_layer_color(self, layer_type: str) -> str:
        """获取图层颜色"""
        colors = {
            'wms': 'linear-gradient(135deg, #e74c3c, #c0392b)',
            'wmts': 'linear-gradient(135deg, #9b59b6, #8e44ad)',
            'geojson': 'linear-gradient(135deg, #2ecc71, #27ae60)',
            'wfs': 'linear-gradient(135deg, #2ecc71, #27ae60)'
        }
        return colors.get(layer_type.lower(), 'linear-gradient(135deg, #95a5a6, #7f8c8d)')
    
    def _get_layer_details(self, layer: Dict[str, Any]) -> str:
        """获取图层详细信息"""
        details = []
        
        if layer['type'] == 'geojson':
            feature_count = len(layer.get('geojson_data', {}).get('features', []))
            details.append(f"<div><strong>要素数量:</strong> {feature_count}</div>")
            
            # 几何类型统计
            geom_types = {}
            for feature in layer.get('geojson_data', {}).get('features', []):
                geom_type = feature.get('geometry', {}).get('type', 'Unknown')
                geom_types[geom_type] = geom_types.get(geom_type, 0) + 1
            
            if geom_types:
                geom_summary = ', '.join([f"{count}个{gtype}" for gtype, count in geom_types.items()])
                details.append(f"<div><strong>几何类型:</strong> {geom_summary}</div>")
        
        elif layer['type'] in ['wms', 'wmts']:
            layer_info = layer.get('layer_info', {})
            if 'bbox' in layer_info:
                bbox = layer_info['bbox']
                details.append(f"<div><strong>边界框:</strong> {bbox[:2]} 到 {bbox[2:]}</div>")
            
            if 'styles' in layer and layer['styles']:
                styles_text = ', '.join(layer['styles'][:2])  # 只显示前2个样式
                if len(layer['styles']) > 2:
                    styles_text += f" (+{len(layer['styles'])-2}个)"
                details.append(f"<div><strong>样式:</strong> {styles_text}</div>")
        
        opacity = layer.get('opacity', 0.8)
        details.append(f"<div><strong>透明度:</strong> {int(opacity * 100)}%</div>")
        
        return layers_html
    
    def _get_layer_details_without_url(self, layer: Dict[str, Any]) -> str:
        """获取图层详细信息 - 不包含服务地址"""
        details = []
        
        if layer['type'] == 'geojson':
            feature_count = len(layer.get('geojson_data', {}).get('features', []))
            details.append(f"<div><strong>要素数量:</strong> {feature_count}</div>")
            
            # 几何类型统计
            geom_types = {}
            for feature in layer.get('geojson_data', {}).get('features', []):
                geom_type = feature.get('geometry', {}).get('type', 'Unknown')
                geom_types[geom_type] = geom_types.get(geom_type, 0) + 1
            
            if geom_types:
                geom_summary = ', '.join([f"{count}个{gtype}" for gtype, count in geom_types.items()])
                details.append(f"<div><strong>几何类型:</strong> {geom_summary}</div>")
        
        elif layer['type'] in ['wms', 'wmts']:
            layer_info = layer.get('layer_info', {})
            if 'bbox' in layer_info:
                bbox = layer_info['bbox']
                details.append(f"<div><strong>边界框:</strong> {bbox[:2]} 到 {bbox[2:]}</div>")
            
            if 'styles' in layer and layer['styles']:
                styles_text = ', '.join(layer['styles'][:2])  # 只显示前2个样式
                if len(layer['styles']) > 2:
                    styles_text += f" (+{len(layer['styles'])-2}个)"
                details.append(f"<div><strong>样式:</strong> {styles_text}</div>")
        
        opacity = layer.get('opacity', 0.8)
        details.append(f"<div><strong>透明度:</strong> {int(opacity * 100)}%</div>")
        
        return '\n'.join(details)
    
    def _generate_layers_info_html_left(self, layers: List[Dict[str, Any]]) -> str:
        """生成左侧图层信息HTML - 按钮始终吸附在面板右上角外部"""
        layers_html = '''
        <!-- 弹簧式图层信息面板 - 默认完全隐藏 -->
        <div class="layers-panel-left collapsed" id="layersPanel">
            <div class="panel-header">
                <div class="panel-title">🗂️ 图层信息</div>
            </div>
            <div class="panel-content">
        '''
        
        for i, layer in enumerate(layers):
            layer_type = 'WFS' if layer['type'] == 'geojson' else layer['type'].upper()
            layer_source = layer.get('layer_info', {}).get('service_name', '未知来源')
            layer_title = layer.get('layer_info', {}).get('layer_title', layer['name'])
            
            # 生成图层缩略图
            thumbnail_text = self._get_layer_thumbnail(layer['type'])
            thumbnail_color = self._get_layer_color(layer['type'])
            
            # 获取图层详细信息（不包含服务地址）
            layer_details = self._get_layer_details_without_url(layer)
            
            layers_html += f'''
            <div class="layer-card" data-layer-index="{i}">
                <div class="layer-header">
                    <div class="layer-thumbnail" style="background: {thumbnail_color};">
                        {thumbnail_text}
                    </div>
                    <div class="layer-info">
                        <div class="layer-name" title="{layer['name']}">{layer['name']}</div>
                        <div class="layer-type">{layer_type}</div>
                    </div>
                </div>
                <div class="layer-details">
                    <div><strong>标题:</strong> {layer_title}</div>
                    <div><strong>来源:</strong> {layer_source}</div>
                    {layer_details}
                </div>
            </div>
            '''
        
        layers_html += '''
            </div>
        </div>
        
        <!-- 弹簧式控制按钮 - 独立定位，始终吸附在面板右上角外部 -->
        <div class="spring-toggle-button" id="springToggleBtn" onclick="toggleLayersPanel()">
            <span class="spring-icon">▶</span>
        </div>
        '''
        
        return layers_html
    
    def _get_composite_map_styles(self, width: int, height: int) -> str:
        """获取复合地图样式 - 修复图层控制器遮挡问题"""
        return f"""
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{ 
            margin: 0; 
            padding: 0; 
            font-family: 'Microsoft YaHei', Arial, sans-serif; 
            background-color: #f5f5f5;
            overflow: hidden;
            height: 100vh;
        }}
        
        .map-container {{ 
            position: relative;
            width: 100vw;
            height: 100vh;
            background: #fff;
        }}
        
        /* 全屏地图 */
        #map {{ 
            width: 100vw !important; 
            height: 100vh !important; 
            border: none;
            z-index: 1;
        }}
        
        /* 顶部标题栏 */
        .map-header {{
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            background: linear-gradient(135deg, rgba(255,255,255,0.95) 0%, rgba(240,240,240,0.95) 100%);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(0,0,0,0.1);
            padding: 15px 20px;
            z-index: 1000;
            transition: transform 0.3s ease;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        .map-header.hidden {{
            transform: translateY(-100%);
        }}
        
        .map-title {{
            font-size: 20px;
            font-weight: 600;
            color: #2c3e50;
            margin: 0 0 8px 0;
            text-shadow: 0 1px 2px rgba(255,255,255,0.8);
        }}
        
        .map-info {{
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            color: #555;
            font-size: 13px;
        }}
        
        .info-item {{
            background: rgba(255,255,255,0.8);
            padding: 4px 10px;
            border-radius: 15px;
            border: 1px solid rgba(0,0,0,0.1);
            backdrop-filter: blur(5px);
        }}
        
        /* 可收缩图层面板 - 调整位置避免遮挡Leaflet控件 */
        .layers-panel {{
            position: absolute;
            top: 100px;
            right: 20px;
            width: 320px;
            max-height: calc(100vh - 200px);
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(15px);
            border: 1px solid rgba(0,0,0,0.2);
            border-radius: 12px;
            z-index: 500;  /* 降低z-index，避免遮挡Leaflet控件 */
            transition: all 0.3s ease;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }}
        
        .layers-panel.collapsed {{
            width: 60px;
            height: 60px;
        }}
        
        .layers-panel.collapsed .panel-content {{
            display: none;
        }}
        
        .panel-header {{
            background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
            color: #fff;
            padding: 12px 15px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255,255,255,0.2);
            user-select: none;
        }}
        
        .panel-title {{
            font-weight: 600;
            font-size: 14px;
        }}
        
        .panel-toggle {{
            font-size: 16px;
            transition: transform 0.3s ease;
        }}
        
        .layers-panel.collapsed .panel-toggle {{
            transform: rotate(180deg);
        }}
        
        .panel-content {{
            max-height: calc(100vh - 300px);
            overflow-y: auto;
            padding: 0;
        }}
        
        /* 图层卡片 */
        .layer-card {{
            background: rgba(0,0,0,0.02);
            border-bottom: 1px solid rgba(0,0,0,0.1);
            padding: 15px;
            transition: all 0.3s ease;
        }}
        
        .layer-card:hover {{
            background: rgba(0,0,0,0.05);
        }}
        
        .layer-card:last-child {{
            border-bottom: none;
        }}
        
        .layer-header {{
            display: flex;
            align-items: center;
            margin-bottom: 10px;
        }}
        
        .layer-thumbnail {{
            width: 40px;
            height: 40px;
            border-radius: 6px;
            margin-right: 12px;
            background: linear-gradient(135deg, #3498db, #2980b9);
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
            font-weight: bold;
            font-size: 12px;
            flex-shrink: 0;
            border: 2px solid rgba(255,255,255,0.3);
        }}
        
        .layer-info {{
            flex: 1;
            min-width: 0;
        }}
        
        .layer-name {{
            color: #2c3e50;
            font-weight: 600;
            font-size: 13px;
            margin-bottom: 4px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        .layer-type {{
            color: #7f8c8d;
            font-size: 11px;
            background: rgba(52, 152, 219, 0.1);
            padding: 2px 6px;
            border-radius: 10px;
            display: inline-block;
        }}
        
        .layer-details {{
            color: #555;
            font-size: 11px;
            margin-top: 8px;
            line-height: 1.4;
        }}
        
        /* 控制面板 */
        .controls {{
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(15px);
            border: 1px solid rgba(0,0,0,0.2);
            border-radius: 12px;
            padding: 15px;
            color: #2c3e50;
            z-index: 1000;
            min-width: 280px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }}
        
        .control-group {{
            margin-bottom: 8px;
            display: flex;
            align-items: center;
        }}
        
        .control-group:last-child {{
            margin-bottom: 0;
        }}
        
        .control-label {{
            font-weight: 600;
            color: #555;
            margin-right: 10px;
            min-width: 80px;
            font-size: 12px;
        }}
        
        .control-value {{
            color: #3498db;
            font-family: 'Consolas', monospace;
            font-size: 12px;
        }}
        
        /* 工具栏 */
        .toolbar {{
            position: absolute;
            top: 50%;
            left: 20px;
            transform: translateY(-50%);
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(15px);
            border: 1px solid rgba(0,0,0,0.2);
            border-radius: 12px;
            padding: 10px;
            z-index: 1000;
            display: flex;
            flex-direction: column;
            gap: 10px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }}
        
        .tool-button {{
            width: 40px;
            height: 40px;
            background: rgba(255,255,255,0.8);
            border: 1px solid rgba(0,0,0,0.2);
            border-radius: 8px;
            color: #2c3e50;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
            font-size: 16px;
        }}
        
        .tool-button:hover {{
            background: rgba(52, 152, 219, 0.1);
            transform: scale(1.05);
            border-color: #3498db;
        }}
        
        .tool-button.active {{
            background: #3498db;
            border-color: #2980b9;
            color: #fff;
        }}
        
        /* 弹出框样式优化 */
        .leaflet-popup-content {{
            background: rgba(255,255,255,0.95);
            color: #2c3e50;
            border-radius: 8px;
            max-width: 300px;
        }}
        
        .popup-title {{
            font-weight: 600;
            margin-bottom: 8px;
            color: #3498db;
            border-bottom: 1px solid rgba(0,0,0,0.1);
            padding-bottom: 4px;
        }}
        
        .popup-properties {{
            font-size: 12px;
        }}
        
        .popup-property {{
            margin: 4px 0;
            padding: 3px 0;
            border-bottom: 1px solid rgba(0,0,0,0.05);
        }}
        
        .property-key {{
            font-weight: 600;
            color: #555;
        }}
        
        .property-value {{
            color: #777;
            margin-left: 8px;
        }}
        
        /* Leaflet控件样式优化 - 确保在最上层 */
        .leaflet-control-layers {{
            background: rgba(255,255,255,0.95) !important;
            color: #2c3e50 !important;
            border: 1px solid rgba(0,0,0,0.2) !important;
            border-radius: 8px !important;
            backdrop-filter: blur(10px);
            box-shadow: 0 4px 20px rgba(0,0,0,0.15) !important;
            z-index: 1001 !important;  /* 确保在图层面板之上 */
        }}
        
        .leaflet-control-layers-toggle {{
            background-color: rgba(255,255,255,0.95) !important;
            color: #2c3e50 !important;
        }}
        
        .leaflet-control-zoom {{
            z-index: 1001 !important;  /* 确保在图层面板之上 */
        }}
        
        .leaflet-control-zoom a {{
            background-color: rgba(255,255,255,0.95) !important;
            color: #2c3e50 !important;
            border: 1px solid rgba(0,0,0,0.2) !important;
        }}
        
        .leaflet-control-scale {{
            background: rgba(255,255,255,0.95) !important;
            color: #2c3e50 !important;
            border: 1px solid rgba(0,0,0,0.2) !important;
            border-radius: 6px !important;
        }}
        
        /* 坐标系统信息 */
        .coord-system-info {{
            background: rgba(255,255,255,0.95) !important;
            color: #2c3e50 !important;
            border: 1px solid rgba(0,0,0,0.2) !important;
            border-radius: 8px !important;
            backdrop-filter: blur(10px);
            box-shadow: 0 2px 10px rgba(0,0,0,0.1) !important;
        }}
        
        /* 响应式设计 */
        @media (max-width: 768px) {{
            .layers-panel {{
                width: 280px;
                right: 10px;
                top: 80px;
            }}
            
            .controls {{
                left: 10px;
                bottom: 10px;
                min-width: 250px;
            }}
            
            .toolbar {{
                left: 10px;
            }}
            
            .map-header {{
                padding: 10px 15px;
            }}
            
            .map-title {{
                font-size: 18px;
            }}
        }}
        
        /* 滚动条样式 */
        .panel-content::-webkit-scrollbar {{
            width: 6px;
        }}
        
        .panel-content::-webkit-scrollbar-track {{
            background: rgba(0,0,0,0.1);
            border-radius: 3px;
        }}
        
        .panel-content::-webkit-scrollbar-thumb {{
            background: rgba(0,0,0,0.3);
            border-radius: 3px;
        }}
        
        .panel-content::-webkit-scrollbar-thumb:hover {{
            background: rgba(0,0,0,0.5);
        }}
        """
        
    def _get_composite_map_styles_modified(self, width: int, height: int) -> str:
        """获取修改后的复合地图样式 - 按钮跟随面板移动"""
        return f"""
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{ 
            margin: 0; 
            padding: 0; 
            font-family: 'Microsoft YaHei', Arial, sans-serif; 
            background-color: #f5f5f5;
            overflow: hidden;
            height: 100vh;
        }}
        
        .map-container {{ 
            position: relative;
            width: 100vw;
            height: 100vh;
            background: #fff;
        }}
        
        /* 全屏地图 */
        #map {{ 
            width: 100vw !important; 
            height: 100vh !important; 
            border: none;
            z-index: 1;
        }}
        
        /* 弹簧式左侧图层面板 - 默认完全隐藏 */
        .layers-panel-left {{
            position: absolute;
            top: 50%;
            left: 0;
            transform: translateY(-50%) translateX(-100%);
            width: 350px;
            height: 500px;
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(15px);
            border: 1px solid rgba(0,0,0,0.2);
            border-left: none;
            border-radius: 0 12px 12px 0;
            z-index: 500;
            transition: all 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55);
            overflow: hidden;
            box-shadow: 2px 0 25px rgba(0,0,0,0.15);
        }}
        
        /* 面板展开状态 - 弹簧式滑入 */
        .layers-panel-left:not(.collapsed) {{
            transform: translateY(-50%) translateX(0);
        }}
        
        /* 弹簧式控制按钮 - 独立定位，跟随面板移动 */
        .spring-toggle-button {{
            position: absolute;
            top: calc(50% - 250px + 15px); /* 对应面板顶部位置 */
            left: 360px; /* 面板展开时的位置：面板宽度350px + 10px间距 */
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
            backdrop-filter: blur(10px);
            border: 2px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55);
            box-shadow: 0 4px 15px rgba(52, 152, 219, 0.4);
            z-index: 501;
        }}
        
        /* 面板收缩时按钮位置 - 停留在左边界 */
        .layers-panel-left.collapsed ~ .spring-toggle-button {{
            left: 10px; /* 停留在左边界 */
            background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
        }}
        
        /* 面板展开时按钮位置和样式 */
        .layers-panel-left:not(.collapsed) ~ .spring-toggle-button {{
            left: 360px; /* 跟随面板移动到右侧 */
            background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
            box-shadow: 0 4px 15px rgba(231, 76, 60, 0.4);
        }}
        
        .spring-toggle-button:hover {{
            transform: scale(1.1) rotate(5deg);
            box-shadow: 0 6px 20px rgba(52, 152, 219, 0.6);
        }}
        
        .layers-panel-left:not(.collapsed) ~ .spring-toggle-button:hover {{
            box-shadow: 0 6px 20px rgba(231, 76, 60, 0.6);
        }}
        
        .spring-icon {{
            color: #fff;
            font-size: 18px;
            font-weight: bold;
            transition: all 0.3s ease;
        }}
        
        /* 面板展开时按钮图标变为向左箭头 */
        .layers-panel-left:not(.collapsed) ~ .spring-toggle-button .spring-icon {{
            transform: rotate(180deg);
        }}
        
        .panel-header {{
            background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
            color: #fff;
            padding: 15px 20px;
            display: flex;
            align-items: center;
            justify-content: flex-start;
            border-bottom: 1px solid rgba(255,255,255,0.2);
            user-select: none;
            position: relative;
        }}
        
        .panel-title {{
            font-weight: 600;
            font-size: 16px;
            flex: 1;
        }}
        
        /* 面板内容区域 - 固定高度，支持滚动 */
        .panel-content {{
            height: calc(500px - 60px);
            overflow-y: auto;
            padding: 0;
        }}
        
        .panel-content::-webkit-scrollbar {{
            width: 8px;
        }}
        
        .panel-content::-webkit-scrollbar-track {{
            background: rgba(0,0,0,0.1);
            border-radius: 4px;
            margin: 5px;
        }}
        
        .panel-content::-webkit-scrollbar-thumb {{
            background: rgba(52, 152, 219, 0.6);
            border-radius: 4px;
        }}
        
        .panel-content::-webkit-scrollbar-thumb:hover {{
            background: rgba(52, 152, 219, 0.8);
        }}
        
        /* 图层卡片 */
        .layer-card {{
            background: rgba(0,0,0,0.02);
            border-bottom: 1px solid rgba(0,0,0,0.1);
            padding: 18px;
            transition: all 0.3s ease;
        }}
        
        .layer-card:hover {{
            background: rgba(52, 152, 219, 0.05);
        }}
        
        .layer-card:last-child {{
            border-bottom: none;
        }}
        
        .layer-header {{
            display: flex;
            align-items: center;
            margin-bottom: 12px;
        }}
        
        .layer-thumbnail {{
            width: 45px;
            height: 45px;
            border-radius: 8px;
            margin-right: 15px;
            background: linear-gradient(135deg, #3498db, #2980b9);
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
            font-weight: bold;
            font-size: 14px;
            flex-shrink: 0;
            border: 2px solid rgba(255,255,255,0.3);
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        .layer-info {{
            flex: 1;
            min-width: 0;
        }}
        
        .layer-name {{
            color: #2c3e50;
            font-weight: 600;
            font-size: 14px;
            margin-bottom: 5px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        .layer-type {{
            color: #7f8c8d;
            font-size: 12px;
            background: rgba(52, 152, 219, 0.1);
            padding: 3px 8px;
            border-radius: 12px;
            display: inline-block;
        }}
        
        .layer-details {{
            color: #555;
            font-size: 12px;
            margin-top: 10px;
            line-height: 1.5;
        }}
        
        .layer-details div {{
            margin-bottom: 4px;
        }}
        
        .layer-details strong {{
            color: #2c3e50;
        }}
        
        /* 右侧工具栏 */
        .toolbar-right {{
            position: absolute;
            top: 50%;
            right: 20px;
            transform: translateY(-50%);
            display: flex;
            flex-direction: column;
            gap: 12px;
            z-index: 600;
        }}
        
        .tool-button {{
            width: 50px;
            height: 50px;
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(0,0,0,0.2);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            font-size: 20px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}
        
        .tool-button:hover {{
            background: rgba(52, 152, 219, 0.9);
            color: #fff;
            transform: scale(1.1);
            box-shadow: 0 6px 20px rgba(0,0,0,0.2);
        }}
        
        /* 左下角控制面板 */
        .controls {{
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(15px);
            border: 1px solid rgba(0,0,0,0.2);
            border-radius: 12px;
            padding: 15px;
            z-index: 500;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            min-width: 280px;
        }}
        
        .control-group {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            font-size: 12px;
        }}
        
        .control-group:last-child {{
            margin-bottom: 0;
        }}
        
        .control-label {{
            color: #555;
            font-weight: 600;
        }}
        
        .control-value {{
            color: #2c3e50;
            font-family: 'Courier New', monospace;
            background: rgba(52, 152, 219, 0.1);
            padding: 2px 6px;
            border-radius: 4px;
        }}
        
        /* Leaflet控件样式优化 */
        .leaflet-control-container .leaflet-control {{
            background: rgba(255,255,255,0.95) !important;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(0,0,0,0.2) !important;
            border-radius: 8px !important;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1) !important;
            z-index: 1001 !important;
        }}
        
        /* 响应式设计 */
        @media (max-width: 768px) {{
            .layers-panel-left {{
                width: 300px;
                height: 400px;
            }}
            
            .spring-toggle-button {{
                width: 35px;
                height: 35px;
                top: calc(50% - 200px + 15px);
            }}
            
            .layers-panel-left.collapsed ~ .spring-toggle-button {{
                left: 8px;
            }}
            
            .layers-panel-left:not(.collapsed) ~ .spring-toggle-button {{
                left: 310px;
            }}
            
            .spring-icon {{
                font-size: 16px;
            }}
            
            .controls {{
                left: 15px;
                bottom: 15px;
                min-width: 250px;
            }}
            
            .toolbar-right {{
                right: 15px;
            }}
        }}
        """
    def _get_enhanced_map_javascript(self, center: List[float], zoom: int, layers_js: str) -> str:
        """获取增强的地图JavaScript代码 - 弹簧式面板控制"""
        return f"""
        // 创建地图实例
        var map = L.map('map', {{
            center: {center},
            zoom: {zoom},
            zoomControl: true,
            attributionControl: true
        }});
        
        // 添加Esri卫星底图
        var satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}.png', {{
            attribution: '© Esri',
            crs: L.CRS.EPSG3857,
            tileSize: 256,
            zoomOffset: 0,
            continuousWorld: false,
            noWrap: false,
            maxZoom: 19
        }});
        
        // 默认使用Esri卫星图层
        satellite.addTo(map);
        
        // 创建图层控制器 - 修复图层不可见问题
        var baseMaps = {{
            "卫星影像": satellite
        }};
        
        var overlayMaps = {{}};
        
        var layerControl = L.control.layers(baseMaps, overlayMaps, {{
            position: 'topright',
            collapsed: false
        }}).addTo(map);
        
        // 存储所有图层边界用于自动缩放
        var allLayerBounds = [];
        
        {layers_js}
        
        // 自动缩放到所有图层
        setTimeout(function() {{
            fitToLayers();
        }}, 1000);
        
        // 实时更新坐标信息
        map.on('mousemove', function(e) {{
            var latlng = e.latlng;
            document.getElementById('mouse-coords').innerHTML = 
                latlng.lat.toFixed(6) + ', ' + latlng.lng.toFixed(6);
        }});
        
        // 实时更新地图中心和缩放级别
        map.on('moveend zoomend', function() {{
            var center = map.getCenter();
            var zoom = map.getZoom();
            
            document.getElementById('center-coords').textContent = 
                center.lat.toFixed(4) + ', ' + center.lng.toFixed(4);
            document.getElementById('zoom-level').textContent = zoom;
        }});
        
        // 点击地图显示详细坐标信息
        map.on('click', function(e) {{
            var latlng = e.latlng;
            var webMercator = map.project(latlng, map.getZoom());
            
            var popupContent = '<div style="min-width: 250px;">' +
                '<h4 style="color: #3498db; margin: 0 0 10px 0;">坐标信息</h4>' +
                '<table style="width: 100%; font-size: 12px; color: #2c3e50;">' +
                '<tr><td><strong>WGS84 (EPSG:4326):</strong></td></tr>' +
                '<tr><td>纬度: ' + latlng.lat.toFixed(8) + '</td></tr>' +
                '<tr><td>经度: ' + latlng.lng.toFixed(8) + '</td></tr>' +
                '<tr><td><strong>Web Mercator (EPSG:3857):</strong></td></tr>' +
                '<tr><td>X: ' + webMercator.x.toFixed(2) + ' 米</td></tr>' +
                '<tr><td>Y: ' + webMercator.y.toFixed(2) + ' 米</td></tr>' +
                '<tr><td><strong>地图信息:</strong></td></tr>' +
                '<tr><td>缩放级别: ' + map.getZoom() + '</td></tr>' +
                '</table></div>';
                
            L.popup()
                .setLatLng(e.latlng)
                .setContent(popupContent)
                .openOn(map);
        }});
        
        // 弹簧式图层面板切换功能
        function toggleLayersPanel() {{
            var panel = document.getElementById('layersPanel');
            var button = document.getElementById('springToggleBtn');
            
            panel.classList.toggle('collapsed');
            
            // 添加弹簧动画效果
            if (panel.classList.contains('collapsed')) {{
                console.log('🔄 面板收缩 - 弹簧式隐藏');
            }} else {{
                console.log('🔄 面板展开 - 弹簧式显示');
            }}
        }}
        
        function toggleFullscreen() {{
            if (!document.fullscreenElement) {{
                document.documentElement.requestFullscreen();
            }} else {{
                document.exitFullscreen();
            }}
        }}
        
        function fitToLayers() {{
            if (allLayerBounds.length > 0) {{
                var group = new L.featureGroup(allLayerBounds);
                if (group.getBounds().isValid()) {{
                    map.fitBounds(group.getBounds(), {{padding: [20, 20]}});
                    console.log('🎯 缩放到所有图层边界');
                }}
            }}
        }}
        
        var measureMode = false;
        var measurePath = null;
        var measureMarkers = [];
        
        function toggleMeasure() {{
            measureMode = !measureMode;
            var button = event.target;
            
            if (measureMode) {{
                button.classList.add('active');
                button.innerHTML = '📐';
                map.getContainer().style.cursor = 'crosshair';
                
                // 清除之前的测量
                if (measurePath) {{
                    map.removeLayer(measurePath);
                }}
                measureMarkers.forEach(marker => map.removeLayer(marker));
                measureMarkers = [];
                
                // 开始测量
                measurePath = L.polyline([], {{color: '#e74c3c', weight: 3}}).addTo(map);
                
                map.on('click', onMeasureClick);
            }} else {{
                button.classList.remove('active');
                button.innerHTML = '📏';
                map.getContainer().style.cursor = '';
                map.off('click', onMeasureClick);
            }}
        }}
        
        function onMeasureClick(e) {{
            if (!measureMode) return;
            
            var latlng = e.latlng;
            measurePath.addLatLng(latlng);
            
            // 添加测量点标记
            var marker = L.circleMarker(latlng, {{
                color: '#e74c3c',
                fillColor: '#e74c3c',
                fillOpacity: 0.8,
                radius: 4
            }}).addTo(map);
            measureMarkers.push(marker);
            
            // 计算距离
            var latlngs = measurePath.getLatLngs();
            if (latlngs.length > 1) {{
                var totalDistance = 0;
                for (var i = 1; i < latlngs.length; i++) {{
                    totalDistance += latlngs[i-1].distanceTo(latlngs[i]);
                }}
                
                var distanceText = totalDistance > 1000 ? 
                    (totalDistance / 1000).toFixed(2) + ' km' : 
                    totalDistance.toFixed(2) + ' m';
                
                marker.bindPopup('总距离: ' + distanceText).openPopup();
            }}
        }}
        
        // 键盘快捷键
        document.addEventListener('keydown', function(e) {{
            switch(e.key) {{
                case 'f':
                case 'F':
                    if (e.ctrlKey) {{
                        e.preventDefault();
                        toggleFullscreen();
                    }}
                    break;
                case 'l':
                case 'L':
                    toggleLayersPanel();
                    break;
                case 'Escape':
                    if (measureMode) {{
                        toggleMeasure();
                    }}
                    break;
            }}
        }});
        
        // 自动隐藏鼠标指针（全屏模式下）
        var mouseTimer;
        document.addEventListener('mousemove', function() {{
            document.body.style.cursor = 'default';
            clearTimeout(mouseTimer);
            mouseTimer = setTimeout(function() {{
                if (document.fullscreenElement) {{
                    document.body.style.cursor = 'none';
                }}
            }}, 3000);
        }});
        
        console.log('🚀 全屏地理可视化界面已加载');
        console.log('💡 快捷键: Ctrl+F(全屏), L(图层面板), Esc(退出测量)');
        console.log('🗺️ 底图: Esri卫星影像');
        console.log('📍 坐标信息: 实时更新鼠标位置和地图中心');
        console.log('🎛️ 弹簧式面板: 默认隐藏，按钮在面板右上角外部');
        """