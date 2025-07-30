"""
OGC服务解析器模块

负责解析WMS、WFS和WMTS服务的Capabilities文档，提取图层信息
"""

import logging
import re
from typing import List, Dict, Any

from .url_utils import URLUtils
from .wfs_schema import WFSSchemaParser
from .bbox_utils import BBoxUtils
from .capabilities_parser import CapabilitiesParser
from .layer_details import LayerDetailsParser
from .filter_builder import WFSFilterBuilder

logger = logging.getLogger(__name__)


class OGCServiceParser:
    """OGC服务解析器
    
    负责解析WMS、WFS和WMTS服务的能力文档，提取图层信息
    """
    
    def __init__(self, timeout: int = 30):
        """初始化解析器
        
        Args:
            timeout: HTTP请求超时时间（秒）
        """
        self.timeout = timeout
        
        # 初始化各个工具模块
        self.url_utils = URLUtils(timeout)
        self.wfs_schema_parser = WFSSchemaParser(self.url_utils, timeout)
        self.bbox_utils = BBoxUtils(self.url_utils, timeout)
        self.capabilities_parser = CapabilitiesParser(self.url_utils, timeout)
        self.layer_details_parser = LayerDetailsParser(
            self.url_utils, 
            self.bbox_utils, 
            self.wfs_schema_parser, 
            timeout
        )
        self.filter_builder = WFSFilterBuilder()
    
    async def close(self):
        """关闭所有HTTP客户端"""
        await self.url_utils.close()
        await self.wfs_schema_parser.close()
        await self.bbox_utils.close()
    
    # 过滤器构建方法（委托给filter_builder）
    def create_filter_builder(self) -> WFSFilterBuilder:
        """创建新的过滤器构建器实例
        
        Returns:
            WFS过滤器构建器实例
        """
        return WFSFilterBuilder()
    
    def build_property_filter(self, property_name: str, value, operator: str = "PropertyIsEqualTo") -> str:
        """构建属性过滤器（便捷方法）
        
        Args:
            property_name: 属性名称
            value: 属性值
            operator: 过滤操作符
            
        Returns:
            CQL过滤器字符串
        """
        builder = WFSFilterBuilder()
        builder.add_property_filter(property_name, value, operator)
        return builder.build_cql_filter()
    
    def build_like_filter(self, property_name: str, pattern: str) -> str:
        """构建模糊匹配过滤器（便捷方法）
        
        Args:
            property_name: 属性名称
            pattern: 匹配模式
            
        Returns:
            CQL过滤器字符串
        """
        builder = WFSFilterBuilder()
        builder.add_like_filter(property_name, pattern)
        return builder.build_cql_filter()
    
    def build_range_filter(self, property_name: str, min_value, max_value) -> str:
        """构建范围过滤器（便捷方法）
        
        Args:
            property_name: 属性名称
            min_value: 最小值
            max_value: 最大值
            
        Returns:
            CQL过滤器字符串
        """
        builder = WFSFilterBuilder()
        builder.add_range_filter(property_name, min_value, max_value)
        return builder.build_cql_filter()
    
    # URL处理方法（委托给url_utils）
    def _normalize_service_url(self, url: str, service_type: str) -> str:
        """标准化服务URL（旧方法，保持向后兼容）"""
        return self.url_utils.normalize_service_url(url, service_type)
    
    def _clean_base_url(self, url: str) -> str:
        """清理基础URL，移除查询参数"""
        return self.url_utils.clean_base_url(url)
    
    def _standardize_service_url(self, url: str) -> str:
        """标准化服务URL为基础URL格式"""
        return self.url_utils.standardize_service_url(url)
    
    def _build_capabilities_url(self, base_url: str, service_type: str) -> str:
        """根据基础URL构建能力文档请求URL"""
        return self.url_utils.build_capabilities_url(base_url, service_type)
    
    async def _find_working_endpoint(self, base_url: str, service_type: str):
        """查找可用的OGC服务端点"""
        return await self.url_utils.find_working_endpoint(base_url, service_type)
    
    async def test_service_availability(self, url: str) -> bool:
        """测试服务是否可用"""
        return await self.url_utils.test_service_availability(url)
    
    # 能力文档解析方法（委托给capabilities_parser）
    async def parse_wms_service(self, url: str, service_name: str = None):
        """解析WMS服务"""
        return await self.capabilities_parser.parse_wms_service(url, service_name)
    
    async def parse_wfs_service(self, url: str, service_name: str = None):
        """解析WFS服务"""
        return await self.capabilities_parser.parse_wfs_service(url, service_name)
    
    async def parse_wmts_service(self, url: str, service_name: str = None):
        """解析WMTS服务"""
        return await self.capabilities_parser.parse_wmts_service(url, service_name)
    
    async def parse_ogc_service(self, url: str, service_type: str = None, service_name: str = None):
        """解析OGC服务（自动检测服务类型或指定类型）"""
        if service_type:
            service_type = service_type.upper()
            if service_type == 'WMS':
                return await self.parse_wms_service(url, service_name)
            elif service_type == 'WFS':
                return await self.parse_wfs_service(url, service_name)
            elif service_type == 'WMTS':
                return await self.parse_wmts_service(url, service_name)
            else:
                raise ValueError(f"不支持的服务类型: {service_type}")
        
        # 自动检测服务类型
        return await self.capabilities_parser.parse_ogc_service(url, service_name)
    
    # 图层详细信息方法（委托给layer_details_parser）
    async def get_layer_details(self, service_url: str, service_type: str, layer_name: str, strict_mode: bool = False):
        """获取图层详细信息"""
        return await self.layer_details_parser.get_layer_details(service_url, service_type, layer_name, strict_mode)
    
    async def _get_wms_layer_details(self, service_url: str, layer_name: str):
        """获取WMS图层详细信息"""
        return await self.layer_details_parser._get_wms_layer_details(service_url, layer_name)
    
    async def _get_wfs_layer_details(self, service_url: str, layer_name: str):
        """获取WFS图层详细信息"""
        return await self.layer_details_parser._get_wfs_layer_details(service_url, layer_name)
    
    # WFS模式方法（委托给wfs_schema_parser）
    async def get_wfs_feature_schema(self, service_url: str, layer_name: str):
        """获取WFS要素类型的详细模式信息"""
        return await self.wfs_schema_parser.get_wfs_feature_schema(service_url, layer_name)
    
    # 边界框方法（委托给bbox_utils）
    async def get_dynamic_bbox_from_data(self, service_url: str, service_type: str, layer_name: str):
        """通过实际数据获取动态边界框"""
        return await self.bbox_utils.get_dynamic_bbox_from_data(service_url, service_type, layer_name)
    
    async def _get_wfs_dynamic_bbox(self, service_url: str, layer_name: str):
        """通过WFS GetFeature请求获取动态边界框"""
        return await self.bbox_utils._get_wfs_dynamic_bbox(service_url, layer_name)
    
    async def _get_wms_dynamic_bbox(self, service_url: str, layer_name: str):
        """通过WMS GetFeatureInfo或其他方式获取动态边界框"""
        return await self.bbox_utils._get_wms_dynamic_bbox(service_url, layer_name)
    
    def _calculate_bbox_from_geometry(self, geometry: Dict[str, Any]):
        """从GeoJSON几何对象计算边界框"""
        return self.bbox_utils._calculate_bbox_from_geometry(geometry)
    
    def _simplify_xsd_type(self, xsd_type: str) -> str:
        """简化XSD数据类型"""
        return self.wfs_schema_parser._simplify_xsd_type(xsd_type)
    
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


# 全局解析器实例
ogc_parser = OGCServiceParser()

async def get_ogc_parser() -> OGCServiceParser:
    """获取OGC解析器实例
    
    Returns:
        OGC解析器实例
    """
    return ogc_parser


# 为了保持向后兼容性，导出主要类和函数
__all__ = ['OGCServiceParser', 'ogc_parser', 'get_ogc_parser']