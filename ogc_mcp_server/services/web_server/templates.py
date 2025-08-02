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
        """生成复合地图HTML
        
        Args:
            title: 地图标题
            layers: 图层列表
            map_config: 地图配置
            
        Returns:
            HTML内容
        """
        # 获取地图参数
        width = map_config.get('width', 1200)
        height = map_config.get('height', 800)
        zoom = map_config.get('zoom', 10)
        center = map_config.get('center', [39.9042, 116.4074])
        
        # 生成图层JavaScript代码
        layers_js = self._generate_layers_javascript(layers)
        
        # 生成图层信息HTML
        layers_info_html = self._generate_layers_info_html(layers)
        
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
    <title>{title}</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        {self._get_composite_map_styles(width, height)}
    </style>
</head>
<body>
    <div class="map-container">
        <div class="map-header">
            <div class="map-title">🗺️ {title}</div>
            <div class="map-info">
                <div class="info-item"><strong>图层数量:</strong> {len(layers)}</div>
                <div class="info-item"><strong>图层类型:</strong> {', '.join(set(layer_types))}</div>
                <div class="info-item"><strong>坐标系:</strong> EPSG:4326</div>
                <div class="info-item"><strong>服务类型:</strong> 复合可视化</div>
            </div>
        </div>
        
        {layers_info_html}
        
        <div id="map"></div>
        
        <div class="controls">
            <div class="control-group">
                <span class="control-label">🎯 中心点:</span>
                <span id="center-coords">{center[0]:.4f}, {center[1]:.4f}</span>
            </div>
            <div class="control-group">
                <span class="control-label">🔍 缩放级别:</span>
                <span id="zoom-level">{zoom}</span>
            </div>
            <div class="control-group">
                <span class="control-label">📍 鼠标位置:</span>
                <span id="mouse-coords">移动鼠标查看坐标</span>
            </div>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdn.jsdelivr.net/gh/alexandre-melard/leaflet.TileLayer.WMTS@master/leaflet-tilelayer-wmts.js"></script>
    <script>
        {self._get_composite_map_javascript(center, zoom, layers_js)}
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
        """生成图层信息HTML"""
        layers_info = '<div class="layer-info"><div class="layer-count">包含图层:</div>'
        for layer in layers:
            layer_type = 'WFS' if layer['type'] == 'geojson' else layer['type'].upper()
            layer_source = layer.get('layer_info', {}).get('service_name', '未知来源')
            layers_info += f'<div>• {layer["name"]} ({layer_type} - {layer_source})</div>'
        layers_info += '</div>'
        return layers_info
    
    def _get_composite_map_styles(self, width: int, height: int) -> str:
        """获取复合地图样式"""
        return f"""
        body {{ 
            margin: 0; 
            padding: 20px; 
            font-family: Arial, sans-serif; 
            background-color: #f5f5f5; 
        }}
        .map-container {{ 
            background: white; 
            border-radius: 8px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
            padding: 20px; 
        }}
        .map-header {{
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 1px solid #eee;
        }}
        .map-title {{
            font-size: 24px;
            font-weight: bold;
            color: #333;
            margin: 0 0 10px 0;
        }}
        .map-info {{
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            color: #666;
            font-size: 14px;
        }}
        .info-item {{
            background: #f8f9fa;
            padding: 5px 10px;
            border-radius: 4px;
        }}
        .layer-info {{
            background: #e8f4fd;
            border: 1px solid #bee5eb;
            border-radius: 4px;
            padding: 10px;
            margin-bottom: 10px;
        }}
        .layer-count {{
            font-weight: bold;
            color: #0c5460;
            margin-bottom: 5px;
        }}
        #map {{ 
            width: {width}px; 
            height: {height}px; 
            border-radius: 4px; 
            border: 1px solid #ddd; 
        }}
        .controls {{
            margin-top: 15px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 4px;
        }}
        .control-group {{
            margin-bottom: 10px;
        }}
        .control-label {{
            font-weight: bold;
            color: #555;
            margin-right: 10px;
        }}
        .leaflet-popup-content {{
            max-width: 300px;
        }}
        .popup-title {{
            font-weight: bold;
            margin-bottom: 8px;
            color: #333;
        }}
        .popup-properties {{
            font-size: 12px;
        }}
        .popup-property {{
            margin: 3px 0;
            padding: 2px 0;
            border-bottom: 1px solid #eee;
        }}
        .property-key {{
            font-weight: bold;
            color: #555;
        }}
        .property-value {{
            color: #777;
            margin-left: 5px;
        }}
        """
    
    def _get_composite_map_javascript(self, center: List[float], zoom: int, layers_js: str) -> str:
        """获取复合地图JavaScript - 修复多种坐标系统支持"""
        return f"""
        // 初始化地图 - 使用Web Mercator投影确保兼容性
        var map = L.map('map', {{
            crs: L.CRS.EPSG3857,  // 使用Web Mercator坐标系
            center: [{center[0]}, {center[1]}],
            zoom: {zoom},
            worldCopyJump: false,
            maxBoundsViscosity: 1.0,
            // 提高坐标转换精度
            zoomSnap: 0.25,
            zoomDelta: 0.5
        }});
        
        // 添加底图 - 确保使用相同的坐标系
        var osm = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors',
            crs: L.CRS.EPSG3857,
            tileSize: 256,
            zoomOffset: 0,
            continuousWorld: false,
            noWrap: false
        }});
        
        var satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}.png', {{
            attribution: '© Esri',
            crs: L.CRS.EPSG3857,
            tileSize: 256,
            zoomOffset: 0,
            continuousWorld: false,
            noWrap: false
        }});
        
        // 默认添加OSM底图
        osm.addTo(map);
        
        // 创建图层控制器
        var baseMaps = {{
            "OpenStreetMap": osm,
            "卫星影像": satellite
        }};
        
        var layerControl = L.control.layers(baseMaps, {{}}).addTo(map);
        
        // 坐标系统信息显示 - 增强版
        var coordSystemInfo = L.control({{position: 'bottomleft'}});
        coordSystemInfo.onAdd = function(map) {{
            var div = L.DomUtil.create('div', 'coord-system-info');
            div.innerHTML = '<div style="background: rgba(255,255,255,0.9); padding: 8px; border-radius: 4px; font-size: 11px; border: 1px solid #ccc;">' +
                           '<strong>地图坐标系:</strong> EPSG:3857<br>' +
                           '<strong>单位:</strong> 米<br>' +
                           '<div id="crs-status" style="margin-top: 4px; font-size: 10px; color: #666;"></div></div>';
            return div;
        }};
        coordSystemInfo.addTo(map);
        
        // 存储所有图层的边界框，用于自动缩放
        var allLayerBounds = [];
        
        // 添加图层 - 坐标对齐处理
        {layers_js}
        
        // 自动缩放到所有图层的边界框
        setTimeout(function() {{
            if (allLayerBounds.length > 0) {{
                var group = new L.featureGroup(allLayerBounds);
                if (group.getBounds().isValid()) {{
                    map.fitBounds(group.getBounds(), {{padding: [20, 20]}});
                    console.log('🎯 自动缩放到图层边界');
                }} else {{
                    console.log('📍 使用AI计算的中心点: [{center[0]}, {center[1]}], 缩放级别: {zoom}');
                }}
            }} else {{
                console.log('📍 使用AI计算的中心点: [{center[0]}, {center[1]}], 缩放级别: {zoom}');
            }}
        }}, 1000);
        
        // 添加比例尺
        L.control.scale({{
            metric: true,
            imperial: false,
            position: 'bottomright'
        }}).addTo(map);
        
        // 增强的鼠标坐标显示
        map.on('mousemove', function(e) {{
            var latlng = e.latlng;
            var webMercator = map.project(latlng, map.getZoom());
            
            document.getElementById('mouse-coords').innerHTML = 
                '<strong>WGS84:</strong> ' + latlng.lat.toFixed(6) + ', ' + latlng.lng.toFixed(6) + '<br>' +
                '<strong>Web Mercator:</strong> ' + webMercator.x.toFixed(2) + ', ' + webMercator.y.toFixed(2);
        }});
        
        // 地图事件监听 - 增强坐标系统检查
        map.on('moveend zoomend', function() {{
            var center = map.getCenter();
            var zoom = map.getZoom();
            var bounds = map.getBounds();
            
            document.getElementById('center-coords').textContent = 
                center.lat.toFixed(4) + ', ' + center.lng.toFixed(4);
            document.getElementById('zoom-level').textContent = zoom;
            
            // 更新坐标系统状态
            var activeLayerCount = 0;
            var crsInfo = [];
            
            map.eachLayer(function(layer) {{
                if (layer.options && layer.options.attribution && 
                    !layer.options.attribution.includes('OpenStreetMap') && 
                    !layer.options.attribution.includes('Esri')) {{
                    activeLayerCount++;
                    if (layer.options.attribution.includes('WMTS')) {{
                        var crsMatch = layer.options.attribution.match(/\\((.*?)\\)/);
                        if (crsMatch) {{
                            crsInfo.push(crsMatch[1]);
                        }}
                    }}
                }}
            }});
            
            var statusDiv = document.getElementById('crs-status');
            if (statusDiv) {{
                statusDiv.innerHTML = '活动图层: ' + activeLayerCount + 
                                    (crsInfo.length > 0 ? '<br>图层CRS: ' + crsInfo.join(', ') : '');
            }}
        }});
        
        // 点击地图显示坐标信息 - 增强版
        map.on('click', function(e) {{
            var latlng = e.latlng;
            var webMercator = map.project(latlng, map.getZoom());
            
            var popupContent = '<div style="min-width: 250px;">' +
                '<h4>坐标信息</h4>' +
                '<table style="width: 100%; font-size: 12px;">' +
                '<tr><td><strong>WGS84 (EPSG:4326):</strong></td></tr>' +
                '<tr><td>纬度: ' + latlng.lat.toFixed(8) + '</td></tr>' +
                '<tr><td>经度: ' + latlng.lng.toFixed(8) + '</td></tr>' +
                '<tr><td><strong>Web Mercator (EPSG:3857):</strong></td></tr>' +
                '<tr><td>X: ' + webMercator.x.toFixed(2) + ' 米</td></tr>' +
                '<tr><td>Y: ' + webMercator.y.toFixed(2) + ' 米</td></tr>' +
                '<tr><td><strong>地图信息:</strong></td></tr>' +
                '<tr><td>缩放级别: ' + map.getZoom() + '</td></tr>' +
                '<tr><td>地图CRS: EPSG:3857</td></tr>' +
                '</table></div>';
                
            L.popup()
                .setLatLng(e.latlng)
                .setContent(popupContent)
                .openOn(map);
        }});
        
        // 图层对齐检查和调试功能
        window.checkLayerAlignment = function() {{
            var activeLayers = [];
            var crsConflicts = [];
            
            map.eachLayer(function(layer) {{
                if (layer.options && layer.options.attribution && 
                    !layer.options.attribution.includes('OpenStreetMap') && 
                    !layer.options.attribution.includes('Esri')) {{
                    
                    var layerInfo = {{
                        name: layer.options.attribution || 'Unknown Layer',
                        crs: layer.options.crs ? layer.options.crs.code : 'Unknown CRS',
                        bounds: layer.getBounds ? layer.getBounds() : 'No bounds',
                        tileSize: layer.options.tileSize || 'Default',
                        zoomOffset: layer.options.zoomOffset || 0
                    }};
                    
                    activeLayers.push(layerInfo);
                    
                    // 检查CRS冲突
                    if (layerInfo.crs !== 'EPSG:3857' && layerInfo.crs !== 'Unknown CRS') {{
                        crsConflicts.push({{
                            layer: layerInfo.name,
                            crs: layerInfo.crs,
                            mapCrs: 'EPSG:3857'
                        }});
                    }}
                }}
            }});
            
            console.log('=== 图层对齐检查报告 ===');
            console.log('活动图层:', activeLayers);
            
            if (crsConflicts.length > 0) {{
                console.warn('⚠️ 发现坐标系冲突:');
                crsConflicts.forEach(function(conflict) {{
                    console.warn('- ' + conflict.layer + ': ' + conflict.crs + ' vs 地图: ' + conflict.mapCrs);
                }});
            }} else {{
                console.log('✅ 所有图层坐标系统兼容');
            }}
            
            return {{
                activeLayers: activeLayers,
                crsConflicts: crsConflicts,
                mapCrs: 'EPSG:3857'
            }};
        }};
        
        // 自动执行对齐检查
        setTimeout(function() {{
            console.log('执行自动图层对齐检查...');
            window.checkLayerAlignment();
        }}, 3000);
        """