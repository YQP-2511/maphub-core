"""
URL处理工具模块

负责OGC服务URL的标准化、清理和构建
"""

import logging
from typing import Optional
from urllib.parse import urlparse, parse_qs, urlunparse
import httpx

logger = logging.getLogger(__name__)


class URLUtils:
    """URL处理工具类"""
    
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
        """初始化URL工具
        
        Args:
            timeout: HTTP请求超时时间（秒）
        """
        self.timeout = timeout
        self.http_client = httpx.AsyncClient(timeout=timeout)
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.http_client.aclose()
    
    def normalize_service_url(self, url: str, service_type: str) -> str:
        """标准化服务URL（旧方法，保持向后兼容）
        
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
    
    def clean_base_url(self, url: str) -> str:
        """清理基础URL，移除查询参数
        
        Args:
            url: 原始URL
            
        Returns:
            清理后的基础URL
        """
        parsed = urlparse(url)
        # 只保留scheme, netloc, path，移除query和fragment
        clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
        return clean_url.rstrip('/')
    
    def standardize_service_url(self, url: str) -> str:
        """标准化服务URL为基础URL格式
        
        将各种格式的URL统一为基础服务URL格式，用于数据库存储
        
        处理的URL类型：
        1. 完整能力文档请求URL: http://example.com/geoserver/ows?service=WMS&request=GetCapabilities
        2. 包含端点的URL: http://example.com/geoserver/ows
        3. 基础网站URL: http://example.com/geoserver
        4. GeoServer/MapServer特定端点
        
        Args:
            url: 原始URL
            
        Returns:
            标准化后的基础服务URL（不包含查询参数）
        """
        # 解析URL
        parsed = urlparse(url)
        
        # 移除查询参数，只保留基础URL
        base_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
        base_url = base_url.rstrip('/')
        
        # 检查是否已经包含常见的OGC端点
        for endpoint in self.COMMON_OGC_ENDPOINTS:
            if endpoint and base_url.endswith(endpoint):
                # 如果URL已经包含端点，保持原样
                return base_url
        
        # 如果没有端点，返回基础URL
        return base_url
    
    def build_capabilities_url(self, base_url: str, service_type: str) -> str:
        """根据基础URL构建能力文档请求URL
        
        Args:
            base_url: 标准化的基础服务URL
            service_type: 服务类型（WMS/WFS）
            
        Returns:
            完整的能力文档请求URL
        """
        # 如果基础URL已经包含查询参数，说明是完整的能力文档URL
        if '?' in base_url and 'getcapabilities' in base_url.lower():
            return base_url
        
        # 构建能力文档请求URL
        capabilities_url = f"{base_url}?service={service_type.upper()}&request=GetCapabilities"
        return capabilities_url
    
    async def find_working_endpoint(self, base_url: str, service_type: str) -> Optional[str]:
        """查找可用的OGC服务端点
        
        Args:
            base_url: 基础URL
            service_type: 服务类型（WMS/WFS）
            
        Returns:
            可用的完整服务URL，如果没有找到则返回None
        """
        # 清理基础URL，移除可能存在的查询参数
        clean_base_url = self.clean_base_url(base_url)
        
        for endpoint in self.COMMON_OGC_ENDPOINTS:
            try:
                # 构建完整的服务URL
                if endpoint:
                    # 检查基础URL是否已经包含该端点路径，避免重复
                    if clean_base_url.endswith(endpoint):
                        test_url = clean_base_url
                    else:
                        test_url = clean_base_url + endpoint
                else:
                    test_url = clean_base_url
                
                # 使用新的方法构建能力文档URL
                capabilities_url = self.build_capabilities_url(test_url, service_type)
                
                logger.debug(f"测试OGC端点: {capabilities_url}")
                
                # 测试端点是否可用
                response = await self.http_client.get(capabilities_url)
                
                if response.status_code == 200:
                    # 检查响应内容是否包含OGC服务标识
                    content = response.text.lower()
                    if service_type.lower() in content and 'capabilities' in content:
                        logger.info(f"找到可用的{service_type}端点: {test_url}")
                        return test_url
                
            except Exception as e:
                logger.debug(f"端点测试失败 {test_url}: {e}")
                continue
        
        logger.warning(f"未找到可用的{service_type}端点: {clean_base_url}")
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