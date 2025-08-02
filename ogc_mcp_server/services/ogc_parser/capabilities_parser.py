"""
OGC服务能力文档解析模块

负责解析WMS、WFS和WMTS服务的Capabilities文档，提取图层信息
"""

import logging
from typing import List, Dict, Any, Optional
from owslib.wms import WebMapService
from owslib.wfs import WebFeatureService
from owslib.wmts import WebMapTileService
from owslib.util import ServiceException

from ...database.models import LayerResourceCreate

logger = logging.getLogger(__name__)


class CapabilitiesParser:
    """能力文档解析器"""
    
    def __init__(self, url_utils, timeout: int = 30):
        """初始化能力文档解析器
        
        Args:
            url_utils: URL工具实例
            timeout: HTTP请求超时时间（秒）
        """
        self.url_utils = url_utils
        self.timeout = timeout
    
    def _generate_service_name(self, service_obj, url: str, default_title: str) -> str:
        """生成服务名称
        
        优先使用从URL提取的域名作为服务名，避免包含服务类型造成歧义
        
        Args:
            service_obj: OWS服务对象
            url: 服务URL
            default_title: 默认标题
            
        Returns:
            生成的服务名称
        """
        try:
            # 首先尝试从URL提取服务名
            url_based_name = self.url_utils.extract_service_name_from_url(url)
            if url_based_name and url_based_name != 'unknown_service':
                return url_based_name
            
            # 如果URL提取失败，尝试从服务信息中获取标题
            if hasattr(service_obj, 'identification') and service_obj.identification:
                identification = service_obj.identification
                if hasattr(identification, 'title') and identification.title:
                    title = identification.title.strip()
                    # 移除服务类型相关的词汇，避免歧义
                    title_lower = title.lower()
                    service_types = ['wms', 'wfs', 'wmts', 'web map service', 'web feature service', 'web map tile service']
                    for service_type in service_types:
                        if service_type in title_lower:
                            # 移除服务类型词汇
                            title = title_lower.replace(service_type, '').strip()
                            break
                    
                    if title and len(title) > 2:  # 确保标题有意义
                        return title.title()  # 首字母大写
            
        except Exception as e:
            logger.debug(f"生成服务名称失败: {e}")
        
        # 最后使用默认标题，但移除服务类型
        default_clean = default_title.replace('WMS', '').replace('WFS', '').replace('WMTS', '').replace('Service', '').strip()
        return default_clean if default_clean else 'Unknown Service'
    
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
            # 查找可用的WMS端点
            working_url = await self.url_utils.find_working_endpoint(url, 'WMS')
            if not working_url:
                working_url = url
            
            # 标准化URL用于数据库存储
            standardized_url = self.url_utils.standardize_service_url(working_url)
            
            # 构建能力文档URL
            capabilities_url = self.url_utils.build_capabilities_url(working_url, 'WMS')
            
            logger.info(f"解析WMS服务: {capabilities_url}")
            
            # 添加预检查机制
            try:
                # 先测试URL是否可访问
                import httpx
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(capabilities_url)
                    if response.status_code != 200:
                        raise ValueError(f"WMS服务返回错误状态码: {response.status_code}")
                    
                    # 检查响应内容
                    content = response.text
                    if not content or 'capabilities' not in content.lower():
                        raise ValueError("响应内容不包含有效的WMS能力文档")
                    
                    # 检查是否是WMTS服务被误用
                    if 'wmts' in content.lower() and 'wms' not in content.lower():
                        raise ValueError("检测到WMTS服务，但请求的是WMS能力文档")
                    
                    logger.debug(f"WMS能力文档长度: {len(content)} 字符")
                    
            except Exception as e:
                logger.error(f"WMS服务访问测试失败: {e}")
                raise ValueError(f"无法访问WMS服务: {e}")
            
            # 创建WMS服务对象，添加更详细的错误处理
            try:
                wms = WebMapService(capabilities_url, timeout=self.timeout)
                logger.debug(f"WMS服务对象创建成功")
                
                # 检查服务对象是否有效
                if not hasattr(wms, 'contents') or wms.contents is None:
                    raise ValueError("WMS服务对象无效：缺少contents属性")
                
            except Exception as e:
                logger.error(f"创建WMS服务对象失败: {e}")
                # 尝试获取更详细的错误信息
                if "NoneType" in str(e) and ("find" in str(e) or "findall" in str(e)):
                    raise ValueError(f"WMS能力文档解析失败：文档格式可能不兼容OWSLib解析器。错误详情: {e}")
                else:
                    raise ValueError(f"WMS服务解析失败: {e}")
            
            # 生成服务名称
            if not service_name:
                service_name = self._generate_service_name(wms, url, 'Unknown Service')
            
            layers = []
            
            # 检查是否有图层内容
            if not wms.contents:
                logger.warning("WMS服务没有找到任何图层")
                return layers
            
            # 遍历所有图层
            for layer_name, layer in wms.contents.items():
                try:
                    # 创建图层资源对象（只保存基础元数据）
                    layer_resource = LayerResourceCreate(
                        service_name=service_name,
                        service_url=standardized_url,  # 使用标准化的URL
                        service_type='WMS',
                        layer_name=layer_name,
                        layer_title=getattr(layer, 'title', layer_name),
                        layer_abstract=getattr(layer, 'abstract', None)
                    )
                    
                    layers.append(layer_resource)
                    logger.debug(f"解析WMS图层: {layer_name}")
                    
                except Exception as e:
                    logger.warning(f"解析WMS图层失败 {layer_name}: {e}")
                    continue
            
            logger.info(f"成功解析WMS服务，共找到 {len(layers)} 个图层")
            return layers
            
        except ServiceException as e:
            logger.error(f"WMS服务异常: {e}")
            raise ValueError(f"WMS服务解析失败: {e}")
        except Exception as e:
            logger.error(f"解析WMS服务失败: {e}")
            raise ValueError(f"无法解析WMS服务: {e}")
    
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
            # 查找可用的WFS端点
            working_url = await self.url_utils.find_working_endpoint(url, 'WFS')
            if not working_url:
                working_url = url
            
            # 标准化URL用于数据库存储
            standardized_url = self.url_utils.standardize_service_url(working_url)
            
            # 构建能力文档URL
            capabilities_url = self.url_utils.build_capabilities_url(working_url, 'WFS')
            
            logger.info(f"解析WFS服务: {capabilities_url}")
            
            # 创建WFS服务对象
            wfs = WebFeatureService(capabilities_url, timeout=self.timeout)
            
            # 生成服务名称
            if not service_name:
                service_name = self._generate_service_name(wfs, url, 'Unknown Service')
            
            layers = []
            
            # 遍历所有要素类型
            for feature_type_name, feature_type in wfs.contents.items():
                try:
                    # 创建图层资源对象（只保存基础元数据）
                    layer_resource = LayerResourceCreate(
                        service_name=service_name,
                        service_url=standardized_url,  # 使用标准化的URL
                        service_type='WFS',
                        layer_name=feature_type_name,
                        layer_title=getattr(feature_type, 'title', feature_type_name),
                        layer_abstract=getattr(feature_type, 'abstract', None)
                    )
                    
                    layers.append(layer_resource)
                    logger.debug(f"解析WFS要素类型: {feature_type_name}")
                    
                except Exception as e:
                    logger.warning(f"解析WFS要素类型失败 {feature_type_name}: {e}")
                    continue
            
            logger.info(f"成功解析WFS服务，共找到 {len(layers)} 个要素类型")
            return layers
            
        except ServiceException as e:
            logger.error(f"WFS服务异常: {e}")
            raise ValueError(f"WFS服务解析失败: {e}")
        except Exception as e:
            logger.error(f"解析WFS服务失败: {e}")
            raise ValueError(f"无法解析WFS服务: {e}")
    
    async def parse_wmts_service(self, url: str, service_name: str = None) -> List[LayerResourceCreate]:
        """解析WMTS服务
        
        Args:
            url: WMTS服务URL
            service_name: 服务名称（可选）
            
        Returns:
            图层资源创建对象列表
            
        Raises:
            ValueError: 当服务解析失败时
        """
        try:
            # 查找可用的WMTS端点
            working_url = await self.url_utils.find_working_endpoint(url, 'WMTS')
            if not working_url:
                working_url = url
            
            # 标准化URL用于数据库存储
            standardized_url = self.url_utils.standardize_service_url(working_url)
            
            # 构建能力文档URL
            capabilities_url = self.url_utils.build_capabilities_url(working_url, 'WMTS')
            
            logger.info(f"解析WMTS服务: {capabilities_url}")
            
            # 添加预检查机制
            try:
                # 先测试URL是否可访问
                import httpx
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(capabilities_url)
                    if response.status_code != 200:
                        raise ValueError(f"WMTS服务返回错误状态码: {response.status_code}")
                    
                    # 检查响应内容
                    content = response.text
                    if not content or 'capabilities' not in content.lower():
                        raise ValueError("响应内容不包含有效的WMTS能力文档")
                    
                    logger.debug(f"WMTS能力文档长度: {len(content)} 字符")
                    
            except Exception as e:
                logger.error(f"WMTS服务访问测试失败: {e}")
                raise ValueError(f"无法访问WMTS服务: {e}")
            
            # 创建WMTS服务对象，添加更详细的错误处理
            try:
                wmts = WebMapTileService(capabilities_url, timeout=self.timeout)
                logger.debug(f"WMTS服务对象创建成功")
                
                # 检查服务对象是否有效
                if not hasattr(wmts, 'contents') or wmts.contents is None:
                    raise ValueError("WMTS服务对象无效：缺少contents属性")
                
            except Exception as e:
                logger.error(f"创建WMTS服务对象失败: {e}")
                raise ValueError(f"WMTS服务解析失败: {e}")
            
            # 生成服务名称
            if not service_name:
                service_name = self._generate_service_name(wmts, url, 'Unknown Service')
            
            layers = []
            
            # 检查是否有图层内容
            if not wmts.contents:
                logger.warning("WMTS服务没有找到任何图层")
                return layers
            
            # 遍历所有图层
            for layer_name, layer in wmts.contents.items():
                try:
                    # 创建图层资源对象（只保存基础元数据）
                    layer_resource = LayerResourceCreate(
                        service_name=service_name,
                        service_url=standardized_url,  # 使用标准化的URL
                        service_type='WMTS',
                        layer_name=layer_name,
                        layer_title=getattr(layer, 'title', layer_name),
                        layer_abstract=getattr(layer, 'abstract', None)
                    )
                    
                    layers.append(layer_resource)
                    logger.debug(f"解析WMTS图层: {layer_name}")
                    
                except Exception as e:
                    logger.warning(f"解析WMTS图层失败 {layer_name}: {e}")
                    continue
            
            logger.info(f"成功解析WMTS服务，共找到 {len(layers)} 个图层")
            return layers
            
        except ServiceException as e:
            logger.error(f"WMTS服务异常: {e}")
            raise ValueError(f"WMTS服务解析失败: {e}")
        except Exception as e:
            logger.error(f"解析WMTS服务失败: {e}")
            raise ValueError(f"无法解析WMTS服务: {e}")
    
    async def parse_ogc_service(self, url: str, service_type: str = None, service_name: str = None) -> List[LayerResourceCreate]:
        """解析OGC服务（自动检测服务类型或解析指定类型）
        
        Args:
            url: OGC服务URL
            service_type: 指定的服务类型（可选，如果不指定则自动检测所有类型）
            service_name: 服务名称（可选）
            
        Returns:
            图层资源创建对象列表
            
        Raises:
            ValueError: 当服务解析失败时
        """
        all_layers = []
        
        # 如果指定了服务类型，只解析该类型
        if service_type:
            service_types = [service_type.upper()]
        else:
            # 否则尝试解析所有支持的服务类型
            service_types = ['WMS', 'WFS', 'WMTS']
        
        successful_types = []
        errors = []
        
        for svc_type in service_types:
            try:
                if svc_type == 'WMS':
                    layers = await self.parse_wms_service(url, service_name)
                elif svc_type == 'WFS':
                    layers = await self.parse_wfs_service(url, service_name)
                elif svc_type == 'WMTS':
                    layers = await self.parse_wmts_service(url, service_name)
                else:
                    continue
                
                if layers:  # 只有当找到图层时才认为解析成功
                    all_layers.extend(layers)
                    successful_types.append(svc_type)
                    logger.info(f"成功解析{svc_type}服务，找到 {len(layers)} 个图层")
                
            except Exception as e:
                error_msg = f"解析{svc_type}服务失败: {e}"
                errors.append(error_msg)
                logger.debug(error_msg)
                continue
        
        # 如果没有成功解析任何服务类型，抛出错误
        if not all_layers:
            if errors:
                raise ValueError(f"无法解析OGC服务 {url}。错误详情: {'; '.join(errors)}")
            else:
                raise ValueError(f"OGC服务 {url} 没有找到任何图层")
        
        logger.info(f"OGC服务解析完成，共解析 {len(successful_types)} 种服务类型: {', '.join(successful_types)}，总计 {len(all_layers)} 个图层")
        return all_layers