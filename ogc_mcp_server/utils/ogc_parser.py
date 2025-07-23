"""
OGC服务解析工具

使用OWSLib解析WMS和WFS服务的能力文档，提取图层信息
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse, parse_qs, urljoin
import httpx
from owslib.wms import WebMapService
from owslib.wfs import WebFeatureService
from owslib.util import ServiceException

from ..database.models import LayerResourceCreate, BoundingBox

logger = logging.getLogger(__name__)


class OGCServiceParser:
    """OGC服务解析器
    
    负责解析WMS和WFS服务的能力文档，提取图层信息
    """
    
    # 常见的OGC服务端点路径
    COMMON_OGC_ENDPOINTS = [
        '/ows',           # 通用OGC Web Services端点
        '/wms',           # WMS专用端点
        '/wfs',           # WFS专用端点
        '/geoserver/ows', # GeoServer标准端点
        '/geoserver/wms', # GeoServer WMS端点
        '/geoserver/wfs', # GeoServer WFS端点
        '/mapserver',     # MapServer端点
        '/cgi-bin/mapserv', # MapServer CGI端点
        '',               # 原始URL（可能已经包含端点）
    ]
    
    def __init__(self, timeout: int = 30):
        """初始化解析器
        
        Args:
            timeout: HTTP请求超时时间（秒）
        """
        self.timeout = timeout
        self.http_client = httpx.AsyncClient(timeout=timeout)
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.http_client.aclose()
    
    def _normalize_service_url(self, url: str, service_type: str) -> str:
        """标准化服务URL
        
        Args:
            url: 原始URL
            service_type: 服务类型（WMS/WFS）
            
        Returns:
            标准化后的URL
        """
        # 解析URL
        parsed = urlparse(url)
        
        # 如果URL中没有查询参数，添加基本参数
        if not parsed.query:
            if service_type.upper() == 'WMS':
                url += '?service=WMS&request=GetCapabilities'
            elif service_type.upper() == 'WFS':
                url += '?service=WFS&request=GetCapabilities'
        else:
            # 检查是否包含必要的参数
            query_params = parse_qs(parsed.query)
            if 'service' not in query_params:
                url += f'&service={service_type.upper()}'
            if 'request' not in query_params:
                url += '&request=GetCapabilities'
        
        return url
    
    async def _find_working_endpoint(self, base_url: str, service_type: str) -> Optional[str]:
        """查找可用的OGC服务端点
        
        Args:
            base_url: 基础URL
            service_type: 服务类型（WMS/WFS）
            
        Returns:
            可用的完整服务URL，如果没有找到则返回None
        """
        # 确保base_url不以/结尾
        base_url = base_url.rstrip('/')
        
        for endpoint in self.COMMON_OGC_ENDPOINTS:
            try:
                # 构建完整的服务URL
                if endpoint:
                    test_url = base_url + endpoint
                else:
                    test_url = base_url
                
                # 标准化URL（添加GetCapabilities参数）
                normalized_url = self._normalize_service_url(test_url, service_type)
                
                logger.debug(f"测试OGC端点: {normalized_url}")
                
                # 测试端点是否可用
                response = await self.http_client.get(normalized_url)
                
                if response.status_code == 200:
                    # 检查响应内容是否包含OGC服务标识
                    content = response.text.lower()
                    if service_type.lower() in content and 'capabilities' in content:
                        logger.info(f"找到可用的{service_type}端点: {test_url}")
                        return test_url
                
            except Exception as e:
                logger.debug(f"端点测试失败 {test_url}: {e}")
                continue
        
        logger.warning(f"未找到可用的{service_type}端点: {base_url}")
        return None
    
    async def test_service_availability(self, url: str) -> bool:
        """测试服务是否可用
        
        Args:
            url: 服务URL
            
        Returns:
            服务是否可用
        """
        try:
            response = await self.http_client.get(url)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"服务不可用 {url}: {e}")
            return False
    
    async def parse_wms_service(self, url: str, service_name: str = None) -> List[LayerResourceCreate]:
        """解析WMS服务
        
        Args:
            url: WMS服务URL
            service_name: 服务名称（可选）
            
        Returns:
            图层资源创建对象列表
            
        Raises:
            ValueError: 当服务解析失败时
        """
        try:
            # 尝试查找可用的WMS端点
            working_url = await self._find_working_endpoint(url, 'WMS')
            if not working_url:
                # 如果没有找到，尝试使用原始URL
                working_url = url
            
            # 标准化URL
            normalized_url = self._normalize_service_url(working_url, 'WMS')
            
            # 最后一次测试服务可用性
            if not await self.test_service_availability(normalized_url):
                raise ValueError(f"WMS服务不可用: {url}")
            
            # 创建WMS服务对象
            wms = WebMapService(normalized_url, timeout=self.timeout)
            
            # 提取服务信息
            if not service_name:
                service_name = getattr(wms.identification, 'title', 'Unknown WMS Service')
            
            layers = []
            
            # 遍历所有图层
            for layer_name, layer in wms.contents.items():
                try:
                    # 提取边界框信息
                    bbox = None
                    if hasattr(layer, 'boundingBoxWGS84') and layer.boundingBoxWGS84:
                        bbox_coords = layer.boundingBoxWGS84
                        bbox = BoundingBox(
                            min_x=bbox_coords[0],
                            min_y=bbox_coords[1],
                            max_x=bbox_coords[2],
                            max_y=bbox_coords[3],
                            crs="EPSG:4326"
                        )
                    
                    # 获取默认CRS
                    default_crs = None
                    if hasattr(layer, 'crsOptions') and layer.crsOptions:
                        default_crs = layer.crsOptions[0]
                    
                    # 创建图层资源对象（使用找到的工作URL）
                    layer_resource = LayerResourceCreate(
                        service_name=service_name,
                        service_url=working_url,
                        service_type='WMS',
                        layer_name=layer_name,
                        layer_title=getattr(layer, 'title', layer_name),
                        layer_abstract=getattr(layer, 'abstract', None),
                        crs=default_crs,
                        bbox=bbox
                    )
                    
                    layers.append(layer_resource)
                    logger.debug(f"解析WMS图层: {layer_name}")
                    
                except Exception as e:
                    logger.warning(f"解析WMS图层失败 {layer_name}: {e}")
                    continue
            
            logger.info(f"WMS服务解析完成: {working_url}, 共解析 {len(layers)} 个图层")
            return layers
            
        except ServiceException as e:
            logger.error(f"WMS服务异常 {url}: {e}")
            raise ValueError(f"WMS服务异常: {e}")
        except Exception as e:
            logger.error(f"解析WMS服务失败 {url}: {e}")
            raise ValueError(f"解析WMS服务失败: {e}")
    
    def _normalize_crs(self, crs_obj) -> str:
        """将CRS对象标准化为字符串格式
        
        Args:
            crs_obj: CRS对象或字符串
            
        Returns:
            标准化的CRS字符串
        """
        if crs_obj is None:
            return None
            
        # 如果已经是字符串，直接返回
        if isinstance(crs_obj, str):
            return crs_obj
            
        # 处理CRS对象
        crs_str = str(crs_obj)
        
        # 提取EPSG代码
        if 'EPSG' in crs_str:
            # 匹配 urn:ogc:def:crs:EPSG::4326 格式
            import re
            epsg_match = re.search(r'EPSG::?(\d+)', crs_str)
            if epsg_match:
                return f"EPSG:{epsg_match.group(1)}"
        
        # 如果无法解析，返回字符串形式
        return crs_str

    async def parse_wfs_service(self, url: str, service_name: str = None) -> List[LayerResourceCreate]:
        """解析WFS服务
        
        Args:
            url: WFS服务URL
            service_name: 服务名称（可选）
            
        Returns:
            图层资源创建对象列表
            
        Raises:
            ValueError: 当服务解析失败时
        """
        try:
            # 尝试查找可用的WFS端点
            working_url = await self._find_working_endpoint(url, 'WFS')
            if not working_url:
                # 如果没有找到，尝试使用原始URL
                working_url = url
            
            # 标准化URL
            normalized_url = self._normalize_service_url(working_url, 'WFS')
            
            # 最后一次测试服务可用性
            if not await self.test_service_availability(normalized_url):
                raise ValueError(f"WFS服务不可用: {url}")
            
            # 创建WFS服务对象
            wfs = WebFeatureService(normalized_url, timeout=self.timeout)
            
            # 提取服务信息
            if not service_name:
                service_name = getattr(wfs.identification, 'title', 'Unknown WFS Service')
            
            layers = []
            
            # 遍历所有要素类型
            for feature_type_name, feature_type in wfs.contents.items():
                try:
                    # 提取边界框信息
                    bbox = None
                    if hasattr(feature_type, 'boundingBoxWGS84') and feature_type.boundingBoxWGS84:
                        bbox_coords = feature_type.boundingBoxWGS84
                        bbox = BoundingBox(
                            min_x=bbox_coords[0],
                            min_y=bbox_coords[1],
                            max_x=bbox_coords[2],
                            max_y=bbox_coords[3],
                            crs="EPSG:4326"
                        )
                    
                    # 获取默认CRS并标准化
                    default_crs = None
                    if hasattr(feature_type, 'crsOptions') and feature_type.crsOptions:
                        raw_crs = feature_type.crsOptions[0]
                        default_crs = self._normalize_crs(raw_crs)
                        logger.debug(f"WFS要素类型 {feature_type_name} CRS: {raw_crs} -> {default_crs}")
                    
                    # 创建图层资源对象（使用找到的工作URL）
                    layer_resource = LayerResourceCreate(
                        service_name=service_name,
                        service_url=working_url,
                        service_type='WFS',
                        layer_name=feature_type_name,
                        layer_title=getattr(feature_type, 'title', feature_type_name),
                        layer_abstract=getattr(feature_type, 'abstract', None),
                        crs=default_crs,
                        bbox=bbox
                    )
                    
                    layers.append(layer_resource)
                    logger.debug(f"解析WFS要素类型: {feature_type_name}")
                    
                except Exception as e:
                    logger.warning(f"解析WFS要素类型失败 {feature_type_name}: {e}")
                    continue
            
            logger.info(f"WFS服务解析完成: {working_url}, 共解析 {len(layers)} 个要素类型")
            return layers
            
        except ServiceException as e:
            logger.error(f"WFS服务异常 {url}: {e}")
            raise ValueError(f"WFS服务异常: {e}")
        except Exception as e:
            logger.error(f"解析WFS服务失败 {url}: {e}")
            raise ValueError(f"解析WFS服务失败: {e}")

    async def parse_ogc_service(self, url: str, service_type: str = None, service_name: str = None) -> List[LayerResourceCreate]:
        """解析OGC服务（自动检测服务类型）
        
        Args:
            url: 服务URL
            service_type: 服务类型（可选，如果不提供则自动检测）
            service_name: 服务名称（可选）
            
        Returns:
            图层资源创建对象列表
            
        Raises:
            ValueError: 当服务解析失败时
        """
        if service_type:
            service_type = service_type.upper()
            if service_type == 'WMS':
                return await self.parse_wms_service(url, service_name)
            elif service_type == 'WFS':
                return await self.parse_wfs_service(url, service_name)
            else:
                raise ValueError(f"不支持的服务类型: {service_type}")
        
        # 自动检测服务类型
        layers = []
        
        # 尝试解析为WMS
        try:
            wms_layers = await self.parse_wms_service(url, service_name)
            layers.extend(wms_layers)
            logger.info(f"检测到WMS服务: {url}")
        except Exception as e:
            logger.debug(f"不是WMS服务 {url}: {e}")
        
        # 尝试解析为WFS
        try:
            wfs_layers = await self.parse_wfs_service(url, service_name)
            layers.extend(wfs_layers)
            logger.info(f"检测到WFS服务: {url}")
        except Exception as e:
            logger.debug(f"不是WFS服务 {url}: {e}")
        
        if not layers:
            raise ValueError(f"无法解析OGC服务: {url}")
        
        return layers
    
    def _clean_base_url(self, url: str) -> str:
        """清理基础URL，移除查询参数
        
        Args:
            url: 原始URL
            
        Returns:
            清理后的基础URL（不包含查询参数）
        """
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        # 重新构建URL，只保留scheme, netloc, path
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return clean_url
    
    def _is_geographic_crs(self, crs: str) -> bool:
        """判断CRS是否为地理坐标系
        
        Args:
            crs: 坐标参考系统
            
        Returns:
            True如果是地理坐标系，False如果是投影坐标系
        """
        # 地理坐标系列表（使用经纬度）
        geographic_crs = [
            'EPSG:4326',  # WGS84
            'EPSG:4269',  # NAD83
            'EPSG:4267',  # NAD27
            'EPSG:4019',  # GRS 1980
            'EPSG:4258',  # ETRS89
            'CRS:84'      # WGS84 (OGC)
        ]
        
        return crs.upper() in [c.upper() for c in geographic_crs]
    
    def _validate_bbox_for_crs(self, bbox: Tuple[float, float, float, float], crs: str) -> bool:
        """验证bbox是否适用于指定的CRS
        
        Args:
            bbox: 边界框 (min_x, min_y, max_x, max_y)
            crs: 坐标参考系统
            
        Returns:
            True如果bbox适用于CRS，False否则
        """
        min_x, min_y, max_x, max_y = bbox
        
        if self._is_geographic_crs(crs):
            # 地理坐标系：经度范围[-180,180]，纬度范围[-90,90]
            return (-180 <= min_x <= 180 and -180 <= max_x <= 180 and
                    -90 <= min_y <= 90 and -90 <= max_y <= 90)
        else:
            # 投影坐标系：通常使用米为单位，值范围较大
            # 简单检查：投影坐标通常绝对值较大（>1000）
            return (abs(min_x) > 1000 or abs(max_x) > 1000 or
                    abs(min_y) > 1000 or abs(max_y) > 1000)
    
    def _get_default_bbox_for_crs(self, crs: str) -> Tuple[float, float, float, float]:
        """获取CRS的默认边界框
        
        Args:
            crs: 坐标参考系统
            
        Returns:
            默认边界框
        """
        if self._is_geographic_crs(crs):
            # 地理坐标系：全球范围
            return (-180, -90, 180, 90)
        else:
            # 投影坐标系：根据具体CRS返回适当的范围
            # 这里提供一些常见投影坐标系的默认范围
            crs_upper = crs.upper()
            
            # Web Mercator (EPSG:3857)
            if crs_upper == 'EPSG:3857':
                return (-20037508.34, -20037508.34, 20037508.34, 20037508.34)
            
            # UTM zones (EPSG:32601-32660, EPSG:32701-32760)
            if crs_upper.startswith('EPSG:326') or crs_upper.startswith('EPSG:327'):
                return (166021.44, 0, 833978.56, 9329005.18)
            
            # Australian MGA zones (EPSG:7850-7859等)
            if crs_upper.startswith('EPSG:785'):
                return (166021.44, 1116915.04, 833978.56, 9329005.18)
            
            # 默认投影坐标范围（米）
            return (-1000000, -1000000, 1000000, 1000000)

    def _fix_bbox_axis_order(self, bbox: Tuple[float, float, float, float], crs: str) -> Tuple[float, float, float, float]:
        """修复边界框的坐标轴顺序和坐标系统兼容性
        
        在WMS 1.3.0中，某些CRS（如EPSG:4326）需要使用纬度,经度的顺序
        
        Args:
            bbox: 原始边界框 (min_x, min_y, max_x, max_y)
            crs: 坐标参考系统
            
        Returns:
            修复后的边界框
        """
        # 检查bbox是否适用于指定的CRS
        if not self._validate_bbox_for_crs(bbox, crs):
            logger.warning(f"提供的bbox {bbox} 可能不适用于CRS {crs}，使用默认范围")
            bbox = self._get_default_bbox_for_crs(crs)
        
        # WMS 1.3.0中需要轴序调整的地理坐标系列表
        lat_lon_crs = [
            'EPSG:4326',  # WGS84地理坐标系
            'EPSG:4269',  # NAD83地理坐标系
            'EPSG:4267',  # NAD27地理坐标系
            'CRS:84'      # WGS84地理坐标系（OGC标准）
        ]
        
        if crs.upper() in [c.upper() for c in lat_lon_crs]:
            # 对于地理坐标系，WMS 1.3.0要求使用纬度,经度顺序
            # 输入: (min_lon, min_lat, max_lon, max_lat)
            # 输出: (min_lat, min_lon, max_lat, max_lon)
            return (bbox[1], bbox[0], bbox[3], bbox[2])
        
        # 投影坐标系保持原有顺序（通常是东向,北向）
        return bbox

    def get_wms_map_url(self, base_url: str, layer_name: str, 
                       bbox: Tuple[float, float, float, float] = None,
                       width: int = 800, height: int = 600,
                       crs: str = "EPSG:4326", format: str = "image/png") -> str:
        """生成WMS GetMap请求URL
        
        Args:
            base_url: WMS服务基础URL
            layer_name: 图层名称
            bbox: 边界框 (min_x, min_y, max_x, max_y) - 输入格式始终为经度,纬度
            width: 图像宽度
            height: 图像高度
            crs: 坐标参考系统
            format: 图像格式
            
        Returns:
            GetMap请求URL
        """
        # 清理基础URL，移除现有的查询参数
        clean_url = self._clean_base_url(base_url)
        
        # 默认边界框（全球范围，经度,纬度格式）
        if not bbox:
            bbox = (-180, -90, 180, 90)
        
        # 根据CRS调整坐标轴顺序
        adjusted_bbox = self._fix_bbox_axis_order(bbox, crs)
        
        # 构建GetMap参数
        params = {
            'service': 'WMS',
            'version': '1.3.0',
            'request': 'GetMap',
            'layers': layer_name,
            'styles': '',
            'crs': crs,
            'bbox': f"{adjusted_bbox[0]},{adjusted_bbox[1]},{adjusted_bbox[2]},{adjusted_bbox[3]}",
            'width': str(width),
            'height': str(height),
            'format': format
        }
        
        # 构建URL
        url = clean_url + '?' + '&'.join([f"{k}={v}" for k, v in params.items()])
        
        return url
    
    def get_wfs_feature_url(self, base_url: str, type_name: str,
                           max_features: int = 100, output_format: str = "application/json") -> str:
        """生成WFS GetFeature请求URL
        
        Args:
            base_url: WFS服务基础URL
            type_name: 要素类型名称
            max_features: 最大要素数量
            output_format: 输出格式
            
        Returns:
            GetFeature请求URL
        """
        # 清理基础URL，移除现有的查询参数
        clean_url = self._clean_base_url(base_url)
        
        # 构建GetFeature参数
        params = {
            'service': 'WFS',
            'version': '2.0.0',
            'request': 'GetFeature',
            'typeNames': type_name,
            'maxFeatures': str(max_features),
            'outputFormat': output_format
        }
        
        # 构建URL
        url = clean_url + '?' + '&'.join([f"{k}={v}" for k, v in params.items()])
        
        return url


# 全局解析器实例
ogc_parser = OGCServiceParser()


async def get_ogc_parser() -> OGCServiceParser:
    """获取OGC服务解析器实例
    
    用于依赖注入
    
    Returns:
        OGC服务解析器实例
    """
    return ogc_parser