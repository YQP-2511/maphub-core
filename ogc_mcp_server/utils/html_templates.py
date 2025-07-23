"""HTML模板生成模块

提供地图可视化的HTML模板生成功能
"""

import json
from typing import Dict, Any


def generate_geojson_map_html(
    layer_name: str, layer_info: Dict[str, Any], geojson_data: Dict[str, Any],
    stats: Dict[str, Any], style_options: Dict[str, Any],
    center_lat: float, center_lng: float, width: int, height: int, initial_zoom: int
) -> str:
    """生成GeoJSON交互式地图HTML内容
    
    Args:
        layer_name: 图层名称
        layer_info: 图层信息
        geojson_data: GeoJSON数据
        stats: 统计信息
        style_options: 样式选项
        center_lat: 中心纬度
        center_lng: 中心经度
        width: 宽度
        height: 高度
        initial_zoom: 初始缩放级别
        
    Returns:
        HTML内容字符串
    """
    # 将GeoJSON数据转换为JavaScript字符串
    geojson_str = json.dumps(geojson_data, ensure_ascii=False)
    style_str = json.dumps(style_options, ensure_ascii=False)
    
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WFS GeoJSON地图 - {layer_name}</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        {_get_map_styles(width, height)}
    </style>
</head>
<body>
    <div class="map-container">
        <div class="map-header">
            <h1 class="map-title">WFS GeoJSON地图 - {layer_info.get('layer_title', layer_name)}</h1>
            <div class="map-info">
                <div class="info-item">要素数量: {stats['feature_count']}</div>
                <div class="info-item">几何类型: {', '.join(stats['geometry_types'])}</div>
                <div class="info-item">服务类型: WFS</div>
                <div class="info-item">坐标系: {layer_info.get('crs', 'EPSG:4326')}</div>
            </div>
        </div>
        <div id="map"></div>
    </div>
    
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        {_get_map_javascript(layer_name, layer_info, geojson_str, style_str, center_lat, center_lng, initial_zoom)}
    </script>
</body>
</html>"""
    
    return html_content


def _get_map_styles(width: int, height: int) -> str:
    """获取地图样式CSS
    
    Args:
        width: 地图宽度
        height: 地图高度
        
    Returns:
        CSS样式字符串
    """
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
            padding-bottom: 10px;
            border-bottom: 1px solid #eee;
        }}
        .map-title {{
            margin: 0 0 10px 0;
            color: #333;
            font-size: 24px;
        }}
        .map-info {{
            color: #666;
            font-size: 14px;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }}
        .info-item {{
            background: #f8f9fa;
            padding: 5px 10px;
            border-radius: 4px;
        }}
        #map {{ 
            width: {width}px; 
            height: {height}px; 
            border-radius: 4px; 
            border: 1px solid #ddd; 
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


def _get_map_javascript(
    layer_name: str, layer_info: Dict[str, Any], geojson_str: str, 
    style_str: str, center_lat: float, center_lng: float, initial_zoom: int
) -> str:
    """获取地图JavaScript代码
    
    Args:
        layer_name: 图层名称
        layer_info: 图层信息
        geojson_str: GeoJSON数据字符串
        style_str: 样式配置字符串
        center_lat: 中心纬度
        center_lng: 中心经度
        initial_zoom: 初始缩放级别
        
    Returns:
        JavaScript代码字符串
    """
    return f"""
        // 初始化地图
        var map = L.map('map').setView([{center_lat}, {center_lng}], {initial_zoom});
        
        // 添加底图
        var osm = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors'
        }});
        
        var satellite = L.tileLayer('https://{{s}}.google.com/vt/lyrs=s&x={{x}}&y={{y}}&z={{z}}', {{
            maxZoom: 20,
            subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
            attribution: '© Google'
        }});
        
        osm.addTo(map);
        
        // GeoJSON数据
        var geojsonData = {geojson_str};
        var styleOptions = {style_str};
        
        // 创建GeoJSON图层
        var geojsonLayer = L.geoJSON(geojsonData, {{
            style: function(feature) {{
                return styleOptions;
            }},
            pointToLayer: function(feature, latlng) {{
                return L.circleMarker(latlng, styleOptions);
            }},
            onEachFeature: function(feature, layer) {{
                // 创建弹窗内容
                var popupContent = '<div class="popup-title">要素属性</div>';
                popupContent += '<div class="popup-properties">';
                
                if (feature.properties) {{
                    for (var key in feature.properties) {{
                        var value = feature.properties[key];
                        if (value !== null && value !== undefined) {{
                            popupContent += '<div class="popup-property">';
                            popupContent += '<span class="property-key">' + key + ':</span>';
                            popupContent += '<span class="property-value">' + value + '</span>';
                            popupContent += '</div>';
                        }}
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
                    geojsonLayer.resetStyle(e.target);
                }});
            }}
        }});
        
        geojsonLayer.addTo(map);
        
        // 图层控制
        var baseMaps = {{
            "OpenStreetMap": osm,
            "卫星影像": satellite
        }};
        
        var overlayMaps = {{
            "{layer_info.get('layer_title', layer_name)}": geojsonLayer
        }};
        
        L.control.layers(baseMaps, overlayMaps).addTo(map);
        
        // 比例尺
        L.control.scale().addTo(map);
        
        // 鼠标坐标显示
        var coordsControl = L.control({{position: 'bottomleft'}});
        coordsControl.onAdd = function(map) {{
            var div = L.DomUtil.create('div', 'coords-control');
            div.style.background = 'rgba(255,255,255,0.8)';
            div.style.padding = '5px';
            div.style.borderRadius = '3px';
            div.style.fontSize = '12px';
            div.innerHTML = '坐标: 0.000, 0.000';
            return div;
        }};
        coordsControl.addTo(map);
        
        map.on('mousemove', function(e) {{
            var coords = e.latlng;
            document.querySelector('.coords-control').innerHTML = 
                '坐标: ' + coords.lat.toFixed(6) + ', ' + coords.lng.toFixed(6);
        }});
        
        // 自动缩放到要素范围
        if (geojsonLayer.getBounds().isValid()) {{
            map.fitBounds(geojsonLayer.getBounds(), {{padding: [20, 20]}});
        }}
    """