"""
边界框处理工具模块

负责获取和处理动态边界框信息
"""

import logging
import json
from typing import Dict, Any, Optional, List
import httpx

logger = logging.getLogger(__name__)


class BBoxUtils:
    """边界框处理工具类"""
    
    def __init__(self, url_utils, timeout: int = 30):
        """初始化边界框工具
        
        Args:
            url_utils: URL工具实例
            timeout: HTTP请求超时时间（秒）
        """
        self.url_utils = url_utils
        self.timeout = timeout
        self.http_client = httpx.AsyncClient(timeout=timeout)
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.http_client.aclose()
    
    async def get_dynamic_bbox_from_data(self, service_url: str, service_type: str, layer_name: str) -> Optional[Dict[str, Any]]:
        """通过实际数据获取动态边界框
        
        Args:
            service_url: 服务URL
            service_type: 服务类型（WMS/WFS）
            layer_name: 图层名称
            
        Returns:
            动态边界框信息，如果获取失败则返回None
        """
        try:
            if service_type.upper() == 'WFS':
                return await self._get_wfs_dynamic_bbox(service_url, layer_name)
            elif service_type.upper() == 'WMS':
                return await self._get_wms_dynamic_bbox(service_url, layer_name)
            else:
                logger.warning(f"不支持的服务类型用于动态边界框获取: {service_type}")
                return None
                
        except Exception as e:
            logger.warning(f"获取动态边界框失败 {service_url}/{layer_name}: {e}")
            return None
    
    async def _get_wfs_dynamic_bbox(self, service_url: str, layer_name: str) -> Optional[Dict[str, Any]]:
        """通过WFS GetFeature请求获取动态边界框
        
        Args:
            service_url: WFS服务URL
            layer_name: 要素类型名称
            
        Returns:
            动态边界框信息
        """
        try:
            # 查找可用的WFS端点
            working_url = await self.url_utils.find_working_endpoint(service_url, 'WFS')
            if not working_url:
                working_url = service_url
            
            # 构建GetFeature请求URL（只获取边界框，不获取具体要素）
            clean_url = self.url_utils.clean_base_url(working_url)
            getfeature_url = f"{clean_url}?service=WFS&version=2.0.0&request=GetFeature&typeNames={layer_name}&maxFeatures=1&outputFormat=application/json"
            
            logger.debug(f"发送WFS GetFeature请求获取边界框: {getfeature_url}")
            
            # 发送请求
            response = await self.http_client.get(getfeature_url)
            
            if response.status_code != 200:
                logger.warning(f"WFS GetFeature请求失败: {response.status_code}")
                return None
            
            # 解析JSON响应
            try:
                data = response.json()
                
                # 检查是否有要素
                if 'features' in data and len(data['features']) > 0:
                    # 从第一个要素获取边界框信息
                    feature = data['features'][0]
                    
                    if 'bbox' in data:
                        # 如果响应中直接包含bbox
                        bbox = data['bbox']
                        return {
                            'wgs84': bbox,
                            'crs': 'EPSG:4326',
                            'source': 'wfs_getfeature_response_bbox'
                        }
                    elif 'geometry' in feature and feature['geometry']:
                        # 从几何对象计算边界框
                        geometry = feature['geometry']
                        bbox = self._calculate_bbox_from_geometry(geometry)
                        if bbox:
                            return {
                                'wgs84': bbox,
                                'crs': 'EPSG:4326',
                                'source': 'wfs_getfeature_geometry_calculation'
                            }
                
                logger.debug(f"WFS响应中未找到有效的边界框信息")
                return None
                
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"解析WFS GetFeature响应失败: {e}")
                return None
                
        except Exception as e:
            logger.warning(f"获取WFS动态边界框失败 {service_url}/{layer_name}: {e}")
            return None
    
    async def _get_wms_dynamic_bbox(self, service_url: str, layer_name: str) -> Optional[Dict[str, Any]]:
        """通过WMS GetFeatureInfo或其他方式获取动态边界框
        
        Args:
            service_url: WMS服务URL
            layer_name: 图层名称
            
        Returns:
            动态边界框信息
        """
        try:
            from owslib.wms import WebMapService
            
            # 查找可用的WMS端点
            working_url = await self.url_utils.find_working_endpoint(service_url, 'WMS')
            if not working_url:
                working_url = service_url
            
            # 标准化URL
            normalized_url = self.url_utils.normalize_service_url(working_url, 'WMS')
            
            # 创建WMS服务对象
            wms = WebMapService(normalized_url, timeout=self.timeout)
            
            # 查找指定图层
            if layer_name not in wms.contents:
                return None
            
            layer = wms.contents[layer_name]
            
            # 提取边界框信息
            bbox_info = {}
            
            # 优先使用WGS84边界框
            if hasattr(layer, 'boundingBoxWGS84') and layer.boundingBoxWGS84:
                bbox_wgs84 = layer.boundingBoxWGS84
                bbox_info = {
                    'wgs84': [bbox_wgs84[0], bbox_wgs84[1], bbox_wgs84[2], bbox_wgs84[3]],
                    'crs': 'EPSG:4326',
                    'source': 'wms_capabilities_wgs84'
                }
            
            # 如果有其他CRS的边界框，也包含进来
            if hasattr(layer, 'boundingBox') and layer.boundingBox:
                # 检查boundingBox的类型，确保它是字典格式
                if isinstance(layer.boundingBox, dict):
                    for bbox_crs, bbox_coords in layer.boundingBox.items():
                        if bbox_crs != 'EPSG:4326' and bbox_coords:
                            bbox_info[f'bbox_{bbox_crs.lower().replace(":", "_")}'] = {
                                'bbox': bbox_coords,
                                'crs': bbox_crs,
                                'source': 'wms_capabilities_native'
                            }
                elif isinstance(layer.boundingBox, (list, tuple)) and len(layer.boundingBox) >= 4:
                    # 如果boundingBox是列表或元组格式，假设是默认CRS的边界框
                    bbox_info['bbox_native'] = {
                        'bbox': list(layer.boundingBox[:4]),
                        'crs': getattr(layer, 'crs', 'EPSG:4326'),
                        'source': 'wms_capabilities_native_tuple'
                    }
                else:
                    logger.debug(f"未知的boundingBox格式: {type(layer.boundingBox)}")
            
            return bbox_info if bbox_info else None
            
        except Exception as e:
            logger.warning(f"获取WMS动态边界框失败 {service_url}/{layer_name}: {e}")
            return None
    
    def _calculate_bbox_from_geometry(self, geometry: Dict[str, Any]) -> Optional[List[float]]:
        """从GeoJSON几何对象计算边界框
        
        Args:
            geometry: GeoJSON几何对象
            
        Returns:
            边界框 [min_lon, min_lat, max_lon, max_lat]，如果计算失败则返回None
        """
        try:
            if not geometry or 'coordinates' not in geometry:
                return None
            
            coordinates = geometry['coordinates']
            geom_type = geometry.get('type', '').lower()
            
            # 提取所有坐标点
            all_coords = []
            
            if geom_type == 'point':
                all_coords = [coordinates]
            elif geom_type in ['linestring', 'multipoint']:
                all_coords = coordinates
            elif geom_type == 'polygon':
                # 只考虑外环
                if coordinates and len(coordinates) > 0:
                    all_coords = coordinates[0]
            elif geom_type in ['multilinestring', 'multipolygon']:
                # 展开多重几何
                for part in coordinates:
                    if geom_type == 'multilinestring':
                        all_coords.extend(part)
                    elif geom_type == 'multipolygon':
                        # 只考虑每个多边形的外环
                        if part and len(part) > 0:
                            all_coords.extend(part[0])
            
            if not all_coords:
                return None
            
            # 计算边界框
            lons = [coord[0] for coord in all_coords if len(coord) >= 2]
            lats = [coord[1] for coord in all_coords if len(coord) >= 2]
            
            if not lons or not lats:
                return None
            
            return [min(lons), min(lats), max(lons), max(lats)]
            
        except Exception as e:
            logger.warning(f"计算几何边界框失败: {e}")
            return None