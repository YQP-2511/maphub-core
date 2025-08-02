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
        '/gwc/service/wmts',  # GeoServer GWC WMTS端点（优先测试）
        '/ows',           # 通用OGC Web Services端点
        '/wms',           # WMS专用端点
        '/wfs',           # WFS专用端点
        '/wmts',          # WMTS专用端点
        '/geoserver/ows', # GeoServer标准端点
        '/geoserver/wms', # GeoServer WMS端点
        '/geoserver/wfs', # GeoServer WFS端点
        '/geoserver/wmts', # GeoServer WMTS端点
        '/geoserver/gwc/service/wmts', # GeoServer完整路径WMTS端点
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
    
    def extract_service_name_from_url(self, url: str) -> str:
        """从URL中提取服务名称
        
        根据URL的域名和路径提取有意义的服务名称，避免包含服务类型造成歧义
        
        处理规则：
        1. localhost/geoserver -> geoserver
        2. www.example.com -> example
        3. gisserver.tianditu.gov.cn -> tianditu
        4. ows.terrestris.de -> terrestris
        5. 如果路径包含特定服务名（如geoserver），优先使用
        
        Args:
            url: 服务URL
            
        Returns:
            提取的服务名称
        """
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or parsed.netloc
            path = parsed.path.strip('/')
            
            # 如果路径包含已知的服务名称，优先使用
            known_services = ['geoserver', 'mapserver', 'qgis', 'arcgis']
            for service in known_services:
                if service in path.lower():
                    return service
            
            # 处理localhost情况
            if hostname and hostname.lower() in ['localhost', '127.0.0.1']:
                # 从路径中提取服务名
                path_parts = [part for part in path.split('/') if part]
                if path_parts:
                    # 取第一个有意义的路径部分
                    first_part = path_parts[0].lower()
                    if first_part not in ['ows', 'wms', 'wfs', 'wmts', 'gwc', 'service']:
                        return first_part
                return 'localhost'
            
            # 处理域名
            if hostname:
                # 移除www前缀
                if hostname.startswith('www.'):
                    hostname = hostname[4:]
                
                # 分割域名部分
                domain_parts = hostname.split('.')
                
                # 提取主要域名部分
                if len(domain_parts) >= 2:
                    # 对于gov.cn, com.cn等，取倒数第三个部分
                    if len(domain_parts) >= 3 and domain_parts[-2] in ['gov', 'com', 'org', 'net']:
                        return domain_parts[-3]
                    # 一般情况取倒数第二个部分（主域名）
                    else:
                        return domain_parts[-2]
                else:
                    return domain_parts[0]
            
            # 如果无法提取，返回默认名称
            return 'unknown_service'
            
        except Exception as e:
            logger.warning(f"从URL提取服务名失败 {url}: {e}")
            return 'unknown_service'
    
    def normalize_service_url(self, url: str, service_type: str) -> str:
        """标准化服务URL（旧方法，保持向后兼容）
        
        Args:
            url: 原始URL
            service_type: 服务类型（WMS/WFS/WMTS）
            
        Returns:
            标准化后的URL
        """
        # 解析URL
        parsed = urlparse(url)
        
        # 如果URL中没有查询参数，添加基本参数
        if not parsed.query:
            if service_type.upper() in ['WMS', 'WFS', 'WMTS']:
                url += f'?service={service_type.upper()}&request=GetCapabilities'
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
            service_type: 服务类型（WMS/WFS/WMTS）
            
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
            service_type: 服务类型（WMS/WFS/WMTS）
            
        Returns:
            可用的完整服务URL，如果没有找到则返回None
        """
        # 清理基础URL，移除可能存在的查询参数
        clean_base_url = self.clean_base_url(base_url)
        
        # 根据服务类型过滤端点
        service_type_upper = service_type.upper()
        endpoints_to_test = []
        
        if service_type_upper == 'WMS':
            # WMS服务端点（排除WMTS专用端点）
            endpoints_to_test = [
                '/ows',           # 通用OGC Web Services端点
                '/wms',           # WMS专用端点
                '/geoserver/ows', # GeoServer标准端点
                '/geoserver/wms', # GeoServer WMS端点
                '/mapserver',     # MapServer端点
                '/cgi-bin/mapserv', # MapServer CGI端点
                '',               # 原始URL（可能已经包含端点）
            ]
        elif service_type_upper == 'WFS':
            # WFS服务端点
            endpoints_to_test = [
                '/ows',           # 通用OGC Web Services端点
                '/wfs',           # WFS专用端点
                '/geoserver/ows', # GeoServer标准端点
                '/geoserver/wfs', # GeoServer WFS端点
                '/mapserver',     # MapServer端点
                '/cgi-bin/mapserv', # MapServer CGI端点
                '',               # 原始URL（可能已经包含端点）
            ]
        elif service_type_upper == 'WMTS':
            # WMTS服务端点（优先测试GeoServer特定端点）
            endpoints_to_test = [
                '/gwc/service/wmts',  # GeoServer GWC WMTS端点（优先测试）
                '/geoserver/gwc/service/wmts', # GeoServer完整路径WMTS端点
                '/wmts',          # WMTS专用端点
                '/geoserver/wmts', # GeoServer WMTS端点
                '/ows',           # 通用OGC Web Services端点
                '',               # 原始URL（可能已经包含端点）
            ]
        else:
            # 未知服务类型，使用所有端点
            endpoints_to_test = self.COMMON_OGC_ENDPOINTS.copy()
        
        tested_urls = set()  # 避免重复测试相同的URL
        
        for endpoint in endpoints_to_test:
            try:
                # 构建完整的服务URL
                if endpoint:
                    # 更智能的路径拼接逻辑
                    if clean_base_url.endswith(endpoint):
                        # 如果基础URL已经包含该端点，直接使用
                        test_url = clean_base_url
                    elif endpoint.startswith('/geoserver/') and '/geoserver/' in clean_base_url:
                        # 如果基础URL已经包含geoserver路径，避免重复
                        endpoint_without_geoserver = endpoint.replace('/geoserver', '')
                        if endpoint_without_geoserver and not clean_base_url.endswith(endpoint_without_geoserver):
                            test_url = clean_base_url + endpoint_without_geoserver
                        else:
                            test_url = clean_base_url
                    else:
                        test_url = clean_base_url + endpoint
                else:
                    test_url = clean_base_url
                
                # 避免重复测试相同的URL
                if test_url in tested_urls:
                    continue
                tested_urls.add(test_url)
                
                # 使用新的方法构建能力文档URL
                capabilities_url = self.build_capabilities_url(test_url, service_type)
                
                logger.debug(f"测试{service_type}端点: {capabilities_url}")
                
                # 测试端点是否可用
                response = await self.http_client.get(capabilities_url)
                
                if response.status_code == 200:
                    # 检查响应内容是否包含OGC服务标识
                    content = response.text.lower()
                    if service_type.lower() in content and 'capabilities' in content:
                        logger.info(f"找到可用的{service_type}端点: {test_url}")
                        return test_url
                elif response.status_code == 302:
                    logger.debug(f"{service_type}端点返回重定向 {test_url}: {response.status_code}")
                else:
                    logger.debug(f"{service_type}端点返回错误状态码 {test_url}: {response.status_code}")
                
            except Exception as e:
                logger.debug(f"{service_type}端点测试失败 {test_url}: {e}")
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