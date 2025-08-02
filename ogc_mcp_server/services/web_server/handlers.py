"""Web可视化处理器模块

提供不同类型可视化的处理器，整合了原utils中的功能
"""

import json
import logging
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)


class MapHandler:
    """WMS地图处理器"""
    
    async def generate_wms_map(self, layer_name: str, layer_info: Dict[str, Any], 
                              map_config: Dict[str, Any]) -> str:
        """生成WMS地图HTML
        
        Args:
            layer_name: 图层名称
            layer_info: 图层信息
            map_config: 地图配置
            
        Returns:
            HTML内容
        """
        # 获取地图参数
        width = map_config.get('width', 1000)
        height = map_config.get('height', 700)
        zoom = map_config.get('zoom', 10)
        center = map_config.get('center', [39.9042, 116.4074])
        bbox = map_config.get('bbox')
        
        # 生成HTML内容
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WMS地图 - {layer_info.get('layer_title', layer_name)}</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        {self._get_common_styles(width, height)}
    </style>
</head>
<body>
    <div class="map-container">
        <div class="map-header">
            <div class="map-title">🗺️ WMS交互式地图</div>
            <div class="map-info">
                <div class="info-item"><strong>图层:</strong> {layer_info.get('layer_title', layer_name)}</div>
                <div class="info-item"><strong>服务:</strong> {layer_info.get('service_name', 'N/A')}</div>
                <div class="info-item"><strong>坐标系:</strong> {layer_info.get('crs', 'EPSG:4326')}</div>
                <div class="info-item"><strong>服务类型:</strong> WMS</div>
            </div>
        </div>
        
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
    <script>
        {self._get_wms_javascript(layer_info, center, zoom)}
    </script>
</body>
</html>"""
        
        return html_content
    
    def _get_wms_javascript(self, layer_info: Dict[str, Any], center: List[float], zoom: int) -> str:
        """生成WMS地图的JavaScript代码"""
        return f"""
        // 初始化地图
        var map = L.map('map').setView([{center[0]}, {center[1]}], {zoom});
        
        // 添加底图
        var osm = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors'
        }});
        
        var satellite = L.tileLayer('https://{{s}}.tile.opentopomap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenTopoMap contributors'
        }});
        
        // 添加WMS图层
        var wmsLayer = L.tileLayer.wms('{layer_info['service_url']}', {{
            layers: '{layer_info['layer_name']}',
            format: 'image/png',
            transparent: true,
            attribution: 'WMS Layer: {layer_info.get('layer_title', layer_info['layer_name'])}'
        }});
        
        // 默认显示底图和WMS图层
        osm.addTo(map);
        wmsLayer.addTo(map);
        
        // 图层控制
        var baseMaps = {{
            "OpenStreetMap": osm,
            "地形图": satellite
        }};
        
        var overlayMaps = {{
            "{layer_info.get('layer_title', layer_info['layer_name'])}": wmsLayer
        }};
        
        L.control.layers(baseMaps, overlayMaps).addTo(map);
        
        // 比例尺
        L.control.scale().addTo(map);
        
        // 鼠标坐标显示
        map.on('mousemove', function(e) {{
            document.getElementById('mouse-coords').textContent = 
                e.latlng.lat.toFixed(6) + ', ' + e.latlng.lng.toFixed(6);
        }});
        
        // 地图移动和缩放事件
        map.on('moveend zoomend', function() {{
            var center = map.getCenter();
            var zoom = map.getZoom();
            document.getElementById('center-coords').textContent = 
                center.lat.toFixed(4) + ', ' + center.lng.toFixed(4);
            document.getElementById('zoom-level').textContent = zoom;
        }});
        
        // 点击地图显示坐标
        map.on('click', function(e) {{
            L.popup()
                .setLatLng(e.latlng)
                .setContent('坐标: ' + e.latlng.lat.toFixed(6) + ', ' + e.latlng.lng.toFixed(6))
                .openOn(map);
        }});
        """
    
    def _get_common_styles(self, width: int, height: int) -> str:
        """获取通用样式"""
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


class GeoJSONHandler:
    """GeoJSON地图处理器，整合了geojson_utils的功能"""
    
    async def generate_geojson_map(self, layer_name: str, layer_info: Dict[str, Any],
                                  geojson_data: Dict[str, Any], stats: Dict[str, Any],
                                  map_config: Dict[str, Any]) -> str:
        """生成GeoJSON地图HTML
        
        Args:
            layer_name: 图层名称
            layer_info: 图层信息
            geojson_data: GeoJSON数据
            stats: 统计信息
            map_config: 地图配置
            
        Returns:
            HTML内容
        """
        # 获取地图参数
        width = map_config.get('width', 1000)
        height = map_config.get('height', 700)
        zoom = map_config.get('zoom', 10)
        center = map_config.get('center', [39.9042, 116.4074])
        style_options = map_config.get('style', self._get_default_style())
        
        # 如果没有提供中心点，计算GeoJSON的中心点
        if center == [39.9042, 116.4074]:  # 默认值
            center = self._calculate_map_center(geojson_data, layer_info)
        
        # 将数据转换为JavaScript字符串
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
        {MapHandler()._get_common_styles(width, height)}
    </style>
</head>
<body>
    <div class="map-container">
        <div class="map-header">
            <div class="map-title">🌍 WFS GeoJSON地图</div>
            <div class="map-info">
                <div class="info-item"><strong>图层:</strong> {layer_info.get('layer_title', layer_name)}</div>
                <div class="info-item"><strong>要素数量:</strong> {stats['feature_count']}</div>
                <div class="info-item"><strong>几何类型:</strong> {', '.join(stats['geometry_types'])}</div>
                <div class="info-item"><strong>服务类型:</strong> WFS</div>
                <div class="info-item"><strong>坐标系:</strong> {layer_info.get('crs', 'EPSG:4326')}</div>
            </div>
        </div>
        
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
    <script>
        {self._get_geojson_javascript(layer_name, layer_info, geojson_str, style_str, center, zoom)}
    </script>
</body>
</html>"""
        
        return html_content
    
    def _get_geojson_javascript(self, layer_name: str, layer_info: Dict[str, Any], 
                               geojson_str: str, style_str: str, 
                               center: List[float], zoom: int) -> str:
        """生成GeoJSON地图的JavaScript代码"""
        return f"""
        // 初始化地图
        var map = L.map('map').setView([{center[0]}, {center[1]}], {zoom});
        
        // 添加底图
        var osm = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors'
        }});
        
        var satellite = L.tileLayer('https://{{s}}.tile.opentopomap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenTopoMap contributors'
        }});
        
        osm.addTo(map);
        
        // GeoJSON数据和样式
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
            "地形图": satellite
        }};
        
        var overlayMaps = {{
            "{layer_info.get('layer_title', layer_name)}": geojsonLayer
        }};
        
        L.control.layers(baseMaps, overlayMaps).addTo(map);
        
        // 比例尺
        L.control.scale().addTo(map);
        
        // 鼠标坐标显示
        map.on('mousemove', function(e) {{
            document.getElementById('mouse-coords').textContent = 
                e.latlng.lat.toFixed(6) + ', ' + e.latlng.lng.toFixed(6);
        }});
        
        // 地图移动和缩放事件
        map.on('moveend zoomend', function() {{
            var center = map.getCenter();
            var zoom = map.getZoom();
            document.getElementById('center-coords').textContent = 
                center.lat.toFixed(4) + ', ' + center.lng.toFixed(4);
            document.getElementById('zoom-level').textContent = zoom;
        }});
        
        // 自动缩放到要素范围
        if (geojsonLayer.getBounds().isValid()) {{
            map.fitBounds(geojsonLayer.getBounds(), {{padding: [20, 20]}});
        }}
        """
    
    def _get_default_style(self) -> Dict[str, Any]:
        """获取默认样式"""
        return {
            "color": "#3388ff",
            "weight": 3,
            "opacity": 0.8,
            "fillColor": "#3388ff",
            "fillOpacity": 0.2,
            "radius": 6
        }
    
    def _calculate_map_center(self, geojson_data: Dict[str, Any], layer_info: Dict[str, Any]) -> List[float]:
        """计算地图中心点"""
        # 默认中心点（北京）
        default_center = [39.9042, 116.4074]
        
        try:
            features = geojson_data.get("features", [])
            if not features:
                return default_center
            
            # 计算所有要素的边界框
            min_lat = min_lng = float('inf')
            max_lat = max_lng = float('-inf')
            
            for feature in features:
                geometry = feature.get("geometry", {})
                if not geometry:
                    continue
                
                coords = self._extract_coordinates(geometry)
                for coord in coords:
                    lng, lat = coord[0], coord[1]
                    min_lat = min(min_lat, lat)
                    max_lat = max(max_lat, lat)
                    min_lng = min(min_lng, lng)
                    max_lng = max(max_lng, lng)
            
            if min_lat != float('inf'):
                center_lat = (min_lat + max_lat) / 2
                center_lng = (min_lng + max_lng) / 2
                return [center_lat, center_lng]
            
        except Exception as e:
            logger.warning(f"计算地图中心点失败: {e}")
        
        return default_center
    
    def _extract_coordinates(self, geometry: Dict[str, Any]) -> List[List[float]]:
        """提取几何对象的坐标"""
        coords = []
        geometry_type = geometry.get("type", "")
        coordinates = geometry.get("coordinates", [])
        
        if geometry_type == "Point":
            coords.append(coordinates)
        elif geometry_type in ["LineString", "MultiPoint"]:
            coords.extend(coordinates)
        elif geometry_type in ["Polygon", "MultiLineString"]:
            for ring in coordinates:
                coords.extend(ring)
        elif geometry_type == "MultiPolygon":
            for polygon in coordinates:
                for ring in polygon:
                    coords.extend(ring)
        
        return coords
    
    def parse_style_config(self, style_config: Optional[str]) -> Dict[str, Any]:
        """解析样式配置"""
        default_style = self._get_default_style()
        
        if not style_config:
            return default_style
        
        try:
            custom_style = json.loads(style_config)
            default_style.update(custom_style)
            return default_style
        except json.JSONDecodeError:
            logger.warning("样式配置JSON解析失败，使用默认样式")
            return default_style


class CompositeHandler:
    """复合可视化处理器"""
    
    def __init__(self, templates):
        """初始化复合处理器
        
        Args:
            templates: WebTemplates实例
        """
        self.templates = templates
        self.map_handler = MapHandler()
        self.geojson_handler = GeoJSONHandler()
    
    async def generate_composite_map(self, title: str, layers: List[Dict[str, Any]], 
                                   map_config: Dict[str, Any]) -> str:
        """生成复合地图HTML
        
        Args:
            title: 地图标题
            layers: 图层列表
            map_config: 地图配置
            
        Returns:
            HTML内容
        """
        return self.templates.generate_composite_map(title, layers, map_config)
    
    def process_layer_data(self, layer_config: Dict[str, Any]) -> Dict[str, Any]:
        """处理图层数据
        
        Args:
            layer_config: 图层配置
            
        Returns:
            处理后的图层数据
        """
        layer_type = layer_config.get("type", "").lower()
        
        if layer_type == "wms":
            return self._process_wms_layer(layer_config)
        elif layer_type == "wmts":
            return self._process_wmts_layer(layer_config)
        elif layer_type == "wfs":
            # WFS图层包含GeoJSON数据，按GeoJSON方式处理
            return self._process_wfs_layer(layer_config)
        elif layer_type == "geojson":
            return self._process_geojson_layer(layer_config)
        else:
            raise ValueError(f"不支持的图层类型: {layer_type}")

    def _process_wms_layer(self, layer_config: Dict[str, Any]) -> Dict[str, Any]:
        """处理WMS图层配置
        
        Args:
            layer_config: WMS图层配置
            
        Returns:
            处理后的WMS图层数据
        """
        layer_info = layer_config.get("layer_info", {})
        style = layer_config.get("style", {})
        
        return {
            "type": "wms",
            "name": layer_info.get("layer_name", "WMS图层"),
            "title": layer_config.get("title", layer_info.get("layer_title", "")),
            "service_url": layer_info.get("service_url", ""),
            "layer_name": layer_info.get("layer_name", ""),
            "format": layer_config.get("format", "image/png"),
            "transparent": layer_config.get("transparent", True),
            "opacity": layer_config.get("opacity", 0.8),
            "visible": layer_config.get("visible", True),
            "crs": layer_info.get("crs", "EPSG:4326"),
            "bbox": layer_info.get("bbox"),
            "style": style,
            "layer_info": layer_info
        }

    def _process_wmts_layer(self, layer_config: Dict[str, Any]) -> Dict[str, Any]:
        """处理WMTS图层配置
        
        Args:
            layer_config: WMTS图层配置
            
        Returns:
            处理后的WMTS图层数据
        """
        layer_info = layer_config.get("layer_info", {})
        service_url = layer_config.get("wmts_url", layer_info.get("service_url", ""))
        
        # 确保service_url是WMTS服务的基础URL，不包含具体的GetTile参数
        # 如果URL已经包含GetTile参数，提取基础URL
        if "REQUEST=GetTile" in service_url:
            # 提取基础URL（去除GetTile相关参数）
            if "?" in service_url:
                base_url = service_url.split("?")[0]
                # 保留SERVICE=WMTS参数（如果存在）
                if "SERVICE=WMTS" in service_url:
                    service_url = f"{base_url}?SERVICE=WMTS"
                else:
                    service_url = base_url
        
        return {
            "type": "wmts",
            "name": layer_config.get("name", layer_info.get("layer_name", "WMTS图层")),
            "title": layer_config.get("title", layer_info.get("layer_title", "")),
            "service_url": service_url,
            "layer_name": layer_info.get("layer_name", ""),
            # 正确传递WMTS特有参数
            "tile_matrix_set": layer_config.get("tile_matrix_set", "EPSG:4326"),
            "style": layer_config.get("style", "default"),
            "format": layer_config.get("format", "image/png"),
            "opacity": layer_config.get("opacity", 0.8),
            "visible": layer_config.get("visible", True),
            "crs": layer_info.get("crs", "EPSG:4326"),
            "bbox": layer_config.get("bbox", layer_info.get("bbox")),
            "layer_info": layer_info,
            # 传递增强信息
            "available_matrix_sets": layer_config.get("available_matrix_sets", []),
            "available_styles": layer_config.get("available_styles", []),
            "available_formats": layer_config.get("available_formats", [])
        }

    def _process_wfs_layer(self, layer_config: Dict[str, Any]) -> Dict[str, Any]:
        """处理WFS图层配置
        
        WFS图层包含GeoJSON数据，按GeoJSON方式处理但保留WFS标识
        """
        layer_info = layer_config.get("layer_info", {})
        geojson_data = layer_config.get("geojson_data", {})
        style = layer_config.get("style", {})
        
        # 使用GeoJSONHandler的默认样式
        default_style = self.geojson_handler._get_default_style()
        default_style.update(style)
        
        return {
            "type": "geojson",  # 在前端按GeoJSON处理
            "source_type": "wfs",  # 保留原始类型标识
            "name": layer_info.get("layer_name", "WFS图层"),
            "title": layer_config.get("title", layer_info.get("layer_title", "")),
            "geojson_data": geojson_data,
            "style": default_style,
            "opacity": layer_config.get("opacity", 0.8),
            "visible": layer_config.get("visible", True),
            "layer_info": layer_info,
            "feature_count": len(geojson_data.get("features", []))
        }
    
    def _process_geojson_layer(self, layer_config: Dict[str, Any]) -> Dict[str, Any]:
        """处理GeoJSON图层配置"""
        layer_info = layer_config.get("layer_info", {})
        geojson_data = layer_config.get("geojson_data", {})
        style = layer_config.get("style", {})
        
        # 使用GeoJSONHandler的默认样式
        default_style = self.geojson_handler._get_default_style()
        default_style.update(style)
        
        return {
            "type": "geojson",
            "name": layer_info.get("layer_name", "GeoJSON图层"),
            "title": layer_info.get("layer_title", ""),
            "geojson_data": geojson_data,
            "style": default_style,
            "opacity": layer_config.get("opacity", 0.8),
            "visible": layer_config.get("visible", True),
            "layer_info": layer_info
        }
    
    def calculate_map_bounds(self, layers: List[Dict[str, Any]]) -> Optional[Dict[str, float]]:
        """计算地图边界
        
        Args:
            layers: 图层列表
            
        Returns:
            地图边界信息，包含north、south、east、west
        """
        bounds = {"north": -90, "south": 90, "east": -180, "west": 180}
        has_bounds = False
        
        for layer in layers:
            layer_bounds = self._get_layer_bounds(layer)
            if layer_bounds:
                bounds["west"] = min(bounds["west"], layer_bounds["west"])
                bounds["south"] = min(bounds["south"], layer_bounds["south"])
                bounds["east"] = max(bounds["east"], layer_bounds["east"])
                bounds["north"] = max(bounds["north"], layer_bounds["north"])
                has_bounds = True
        
        # 验证边界的有效性
        if has_bounds and self._is_valid_bounds(bounds):
            return bounds
        
        return None
    
    def _get_layer_bounds(self, layer: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """获取单个图层的边界
        
        Args:
            layer: 图层信息
            
        Returns:
            图层边界信息
        """
        layer_type = layer.get("type", "")
        
        if layer_type in ["wms", "wmts"]:
            return self._get_ogc_layer_bounds(layer)
        elif layer_type == "geojson":
            return self._get_geojson_bounds(layer)
        
        return None
    
    def _get_ogc_layer_bounds(self, layer: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """获取OGC图层（WMS/WMTS）的边界
        
        Args:
            layer: OGC图层信息
            
        Returns:
            图层边界信息
        """
        # 优先使用动态边界框
        layer_info = layer.get("layer_info", {})
        dynamic_bbox = layer_info.get("dynamic_bbox")
        
        if dynamic_bbox and len(dynamic_bbox) == 4:
            return {
                "west": dynamic_bbox[0],
                "south": dynamic_bbox[1], 
                "east": dynamic_bbox[2],
                "north": dynamic_bbox[3]
            }
        
        # 使用静态边界框
        bbox = layer.get("bbox") or layer_info.get("bbox")
        if bbox and len(bbox) == 4:
            return {
                "west": bbox[0],
                "south": bbox[1],
                "east": bbox[2], 
                "north": bbox[3]
            }
        
        return None
    
    def _get_geojson_bounds(self, layer: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """获取GeoJSON图层的边界
        
        Args:
            layer: GeoJSON图层信息
            
        Returns:
            图层边界信息
        """
        geojson_data = layer.get("geojson_data", {})
        if not geojson_data.get("features"):
            return None
        
        bounds = {"north": -90, "south": 90, "east": -180, "west": 180}
        has_coords = False
        
        for feature in geojson_data["features"]:
            geometry = feature.get("geometry", {})
            if geometry.get("coordinates"):
                coords = self._extract_coordinates(geometry["coordinates"])
                for coord in coords:
                    if len(coord) >= 2:
                        lon, lat = coord[0], coord[1]
                        # 验证坐标有效性
                        if -180 <= lon <= 180 and -90 <= lat <= 90:
                            bounds["west"] = min(bounds["west"], lon)
                            bounds["east"] = max(bounds["east"], lon)
                            bounds["south"] = min(bounds["south"], lat)
                            bounds["north"] = max(bounds["north"], lat)
                            has_coords = True
        
        return bounds if has_coords else None
    
    def _is_valid_bounds(self, bounds: Dict[str, float]) -> bool:
        """验证边界的有效性
        
        Args:
            bounds: 边界信息
            
        Returns:
            边界是否有效
        """
        try:
            # 检查边界值的合理性
            if (bounds["west"] >= bounds["east"] or 
                bounds["south"] >= bounds["north"]):
                return False
            
            # 检查坐标范围
            if (bounds["west"] < -180 or bounds["east"] > 180 or
                bounds["south"] < -90 or bounds["north"] > 90):
                return False
            
            # 检查边界大小是否合理（不能太小或太大）
            width = bounds["east"] - bounds["west"]
            height = bounds["north"] - bounds["south"]
            
            if width < 0.0001 or height < 0.0001:  # 太小
                return False
            
            if width > 360 or height > 180:  # 太大
                return False
            
            return True
            
        except (KeyError, TypeError, ValueError):
            return False


class LayerHandler:
    """图层管理处理器"""
    
    def generate_layer_list(self, layers: List[Dict[str, Any]]) -> str:
        """生成图层列表HTML"""
        # 这里可以实现图层管理界面
        return "<h1>图层管理</h1>"