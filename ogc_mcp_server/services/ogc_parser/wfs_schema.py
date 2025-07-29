"""
WFS要素模式获取模块

负责获取WFS要素类型的详细模式信息
"""

import logging
import json
import xml.etree.ElementTree as ET
from typing import Dict, Any
import httpx

logger = logging.getLogger(__name__)


class WFSSchemaParser:
    """WFS模式解析器"""
    
    def __init__(self, url_utils, timeout: int = 30):
        """初始化WFS模式解析器
        
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
    
    async def get_wfs_feature_schema(self, service_url: str, layer_name: str) -> Dict[str, Any]:
        """获取WFS要素类型的详细模式信息（DescribeFeatureType）
        
        Args:
            service_url: WFS服务URL
            layer_name: 要素类型名称
            
        Returns:
            要素类型的详细模式信息
        """
        try:
            # 查找可用的WFS端点
            working_url = await self.url_utils.find_working_endpoint(service_url, 'WFS')
            if not working_url:
                working_url = service_url
            
            # 构建DescribeFeatureType请求URL
            clean_url = self.url_utils.clean_base_url(working_url)
            describe_url = f"{clean_url}?service=WFS&version=2.0.0&request=DescribeFeatureType&typeNames={layer_name}"
            
            logger.debug(f"发送DescribeFeatureType请求: {describe_url}")
            
            # 发送请求
            response = await self.http_client.get(describe_url)
            
            if response.status_code != 200:
                logger.warning(f"DescribeFeatureType请求失败: {response.status_code}")
                return {}
            
            # 解析XML响应
            try:
                root = ET.fromstring(response.text)
                
                # 查找命名空间
                namespaces = {
                    'xsd': 'http://www.w3.org/2001/XMLSchema',
                    'gml': 'http://www.opengis.net/gml',
                    'gml32': 'http://www.opengis.net/gml/3.2'
                }
                
                # 提取属性信息
                attributes = []
                geometry_type = None
                
                # 查找complexType元素
                for complex_type in root.findall('.//xsd:complexType', namespaces):
                    # 查找sequence中的element
                    for element in complex_type.findall('.//xsd:element', namespaces):
                        attr_name = element.get('name')
                        attr_type = element.get('type')
                        
                        if attr_name and attr_type:
                            # 检查是否为几何类型
                            if any(geom in attr_type.lower() for geom in ['geometry', 'point', 'line', 'polygon', 'multipoint', 'multiline', 'multipolygon']):
                                geometry_type = attr_type
                            else:
                                # 简化数据类型
                                simplified_type = self._simplify_xsd_type(attr_type)
                                attributes.append({
                                    'name': attr_name,
                                    'type': simplified_type,
                                    'original_type': attr_type
                                })
                
                return {
                    'attributes': attributes,
                    'geometry_type': geometry_type,
                    'schema_source': 'describe_feature_type'
                }
                
            except ET.ParseError as e:
                logger.warning(f"解析DescribeFeatureType响应失败: {e}")
                return {}
                
        except Exception as e:
            logger.warning(f"获取WFS要素模式失败 {service_url}/{layer_name}: {e}")
            return {}
    
    def _simplify_xsd_type(self, xsd_type: str) -> str:
        """简化XSD数据类型
        
        Args:
            xsd_type: XSD数据类型
            
        Returns:
            简化后的数据类型
        """
        if not xsd_type:
            return 'unknown'
        
        type_mapping = {
            'xsd:string': 'string',
            'xsd:int': 'integer',
            'xsd:integer': 'integer',
            'xsd:long': 'integer',
            'xsd:double': 'number',
            'xsd:float': 'number',
            'xsd:decimal': 'number',
            'xsd:boolean': 'boolean',
            'xsd:date': 'date',
            'xsd:dateTime': 'datetime',
            'xsd:time': 'time'
        }
        
        # 移除命名空间前缀
        simple_type = xsd_type.split(':')[-1].lower()
        
        # 查找映射
        for xsd_key, simple_value in type_mapping.items():
            if simple_type in xsd_key.lower():
                return simple_value
        
        return simple_type