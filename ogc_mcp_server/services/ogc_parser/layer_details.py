"""
图层详细信息获取模块

负责获取WMS和WFS图层的详细信息
"""

import logging
import re
from typing import Dict, Any
from owslib.wms import WebMapService
from owslib.wfs import WebFeatureService
from owslib.util import ServiceException

logger = logging.getLogger(__name__)


class LayerDetailsParser:
    """图层详细信息解析器"""
    
    def __init__(self, url_utils, bbox_utils, wfs_schema_parser, timeout: int = 30):
        """初始化图层详细信息解析器
        
        Args:
            url_utils: URL工具实例
            bbox_utils: 边界框工具实例
            wfs_schema_parser: WFS模式解析器实例
            timeout: HTTP请求超时时间（秒）
        """
        self.url_utils = url_utils
        self.bbox_utils = bbox_utils
        self.wfs_schema_parser = wfs_schema_parser
        self.timeout = timeout
    
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
            epsg_match = re.search(r'EPSG::?(\d+)', crs_str)
            if epsg_match:
                return f"EPSG:{epsg_match.group(1)}"
        
        # 如果无法解析，返回字符串形式
        return crs_str
    
    async def get_layer_details(self, service_url: str, service_type: str, layer_name: str) -> Dict[str, Any]:
        """获取图层详细信息
        
        支持WMS、WFS和BOTH类型的图层
        对于BOTH类型，优先尝试WMS，失败后尝试WFS
        
        Args:
            service_url: 服务URL（标准化的基础URL）
            service_type: 服务类型（WMS/WFS/BOTH）
            layer_name: 图层名称
            
        Returns:
            图层详细信息字典
        """
        if service_type.upper() == 'WMS':
            return await self._get_wms_layer_details(service_url, layer_name)
        elif service_type.upper() == 'WFS':
            return await self._get_wfs_layer_details(service_url, layer_name)
        elif service_type.upper() == 'BOTH':
            # 优先尝试WMS
            wms_error = None
            wfs_error = None
            
            try:
                return await self._get_wms_layer_details(service_url, layer_name)
            except Exception as e:
                wms_error = str(e)
                logger.debug(f"WMS获取失败，尝试WFS: {e}")
                
                # WMS失败，尝试WFS
                try:
                    return await self._get_wfs_layer_details(service_url, layer_name)
                except Exception as e:
                    wfs_error = str(e)
                    logger.debug(f"WFS获取也失败: {e}")
                    
                    # 如果两种方式都失败，抛出详细错误
                    if wms_error and wfs_error:
                        logger.error(f"WMS和WFS都获取失败: WMS={wms_error}, WFS={wfs_error}")
                        raise ValueError(f"无法从WMS或WFS获取图层详细信息: {layer_name}")
        else:
            raise ValueError(f"不支持的服务类型: {service_type}")
    
    async def _get_wms_layer_details(self, service_url: str, layer_name: str) -> Dict[str, Any]:
        """获取WMS图层详细信息
        
        Args:
            service_url: WMS服务URL（标准化的基础URL）
            layer_name: 图层名称
            
        Returns:
            WMS图层详细信息
        """
        # 从标准化的URL重新发现可用端点
        working_url = await self.url_utils.find_working_endpoint(service_url, 'WMS')
        if not working_url:
            # 如果发现失败，尝试直接使用标准化URL构建能力文档URL
            working_url = service_url
        
        # 构建能力文档URL
        capabilities_url = self.url_utils.build_capabilities_url(working_url, 'WMS')
        
        # 创建WMS服务对象
        wms = WebMapService(capabilities_url, timeout=self.timeout)
        
        # 查找指定图层
        if layer_name not in wms.contents:
            raise ValueError(f"图层 '{layer_name}' 在WMS服务中不存在")
        
        layer = wms.contents[layer_name]
        
        # 构建详细信息
        details = {
            "service_type": "WMS",
            "layer_name": layer_name,
            "title": getattr(layer, 'title', layer_name),
            "abstract": getattr(layer, 'abstract', None),
            "keywords": getattr(layer, 'keywords', []),
            "bbox": None,
            "crs_list": [],
            "default_crs": "EPSG:4326",
            "styles": [],
            "queryable": getattr(layer, 'queryable', False),
            "opaque": getattr(layer, 'opaque', False),
            "cascaded": getattr(layer, 'cascaded', 0),
            "dynamic_bbox": None  # 新增：动态边界框信息
        }
        
        # 提取边界框信息（从Capabilities）
        if hasattr(layer, 'boundingBoxWGS84') and layer.boundingBoxWGS84:
            bbox_wgs84 = layer.boundingBoxWGS84
            details["bbox"] = {
                "wgs84": [bbox_wgs84[0], bbox_wgs84[1], bbox_wgs84[2], bbox_wgs84[3]],
                "crs": "EPSG:4326",
                "source": "capabilities"
            }
        
        # 提取支持的坐标系
        if hasattr(layer, 'crsOptions') and layer.crsOptions:
            details["crs_list"] = list(layer.crsOptions)
            # 优先使用EPSG:4326，如果不支持则使用第一个
            if 'EPSG:4326' in layer.crsOptions:
                details["default_crs"] = 'EPSG:4326'
            elif layer.crsOptions:
                details["default_crs"] = list(layer.crsOptions)[0]
        
        # 提取样式信息
        if hasattr(layer, 'styles') and layer.styles:
            styles = []
            for style_name, style in layer.styles.items():
                style_info = {
                    "name": style_name,
                    "title": getattr(style, 'title', style_name),
                    "abstract": getattr(style, 'abstract', None)
                }
                if hasattr(style, 'legend') and style.legend:
                    style_info["legend_url"] = style.legend
                styles.append(style_info)
            details["styles"] = styles
        
        # 尝试获取动态边界框
        try:
            dynamic_bbox = await self.bbox_utils.get_dynamic_bbox_from_data(working_url, 'WMS', layer_name)
            if dynamic_bbox:
                details["dynamic_bbox"] = dynamic_bbox
                # 如果没有静态边界框，使用动态边界框作为主要边界框
                if not details["bbox"] and 'wgs84' in dynamic_bbox:
                    details["bbox"] = {
                        "wgs84": dynamic_bbox['wgs84'],
                        "crs": dynamic_bbox.get('crs', 'EPSG:4326'),
                        "source": "dynamic"
                    }
        except Exception as e:
            logger.debug(f"获取WMS动态边界框失败: {e}")
        
        return details
    
    async def _get_wfs_layer_details(self, service_url: str, layer_name: str) -> Dict[str, Any]:
        """获取WFS图层详细信息
        
        Args:
            service_url: WFS服务URL（标准化的基础URL）
            layer_name: 图层名称
            
        Returns:
            WFS图层详细信息
        """
        # 从标准化的URL重新发现可用端点
        working_url = await self.url_utils.find_working_endpoint(service_url, 'WFS')
        if not working_url:
            # 如果发现失败，尝试直接使用标准化URL构建能力文档URL
            working_url = service_url
        
        # 构建能力文档URL
        capabilities_url = self.url_utils.build_capabilities_url(working_url, 'WFS')
        
        # 创建WFS服务对象
        wfs = WebFeatureService(capabilities_url, timeout=self.timeout)
        
        # 查找指定要素类型
        if layer_name not in wfs.contents:
            raise ValueError(f"要素类型 '{layer_name}' 在WFS服务中不存在")
        
        feature_type = wfs.contents[layer_name]
        
        # 构建详细信息
        details = {
            "service_type": "WFS",
            "layer_name": layer_name,
            "title": getattr(feature_type, 'title', layer_name),
            "abstract": getattr(feature_type, 'abstract', None),
            "keywords": getattr(feature_type, 'keywords', []),
            "bbox": None,
            "crs_list": [],
            "default_crs": "EPSG:4326",
            "geometry_type": None,
            "attributes": [],
            "feature_schema": None,  # 新增：DescribeFeatureType信息
            "dynamic_bbox": None    # 新增：动态边界框信息
        }
        
        # 提取边界框信息（从Capabilities）
        if hasattr(feature_type, 'boundingBoxWGS84') and feature_type.boundingBoxWGS84:
            bbox_wgs84 = feature_type.boundingBoxWGS84
            details["bbox"] = {
                "wgs84": [bbox_wgs84[0], bbox_wgs84[1], bbox_wgs84[2], bbox_wgs84[3]],
                "crs": "EPSG:4326",
                "source": "capabilities"
            }
        
        # 获取要素模式信息（DescribeFeatureType）
        try:
            feature_schema = await self.wfs_schema_parser.get_wfs_feature_schema(working_url, layer_name)
            if feature_schema:
                details["feature_schema"] = feature_schema
                details["attributes"] = feature_schema.get('attributes', [])
                details["geometry_type"] = feature_schema.get('geometry_type', None)
        except Exception as e:
            logger.debug(f"获取WFS要素模式失败: {e}")
        
        # 提取CRS信息
        if hasattr(feature_type, 'crsOptions') and feature_type.crsOptions:
            details["crs_list"] = [self._normalize_crs(crs) for crs in feature_type.crsOptions]
            # 优先使用EPSG:4326
            normalized_crs_list = details["crs_list"]
            if 'EPSG:4326' in normalized_crs_list:
                details["default_crs"] = 'EPSG:4326'
            elif normalized_crs_list:
                details["default_crs"] = normalized_crs_list[0]
        
        # 尝试获取动态边界框
        try:
            dynamic_bbox = await self.bbox_utils.get_dynamic_bbox_from_data(working_url, 'WFS', layer_name)
            if dynamic_bbox:
                details["dynamic_bbox"] = dynamic_bbox
                # 如果没有静态边界框，使用动态边界框作为主要边界框
                if not details["bbox"] and 'wgs84' in dynamic_bbox:
                    details["bbox"] = {
                        "wgs84": dynamic_bbox['wgs84'],
                        "crs": dynamic_bbox.get('crs', 'EPSG:4326'),
                        "source": "dynamic"
                    }
        except Exception as e:
            logger.debug(f"获取WFS动态边界框失败: {e}")
        
        return details