"""
OGC服务能力文档解析模块

负责解析WMS和WFS服务的Capabilities文档，提取图层信息
"""

import logging
from typing import List, Dict, Any, Optional
from owslib.wms import WebMapService
from owslib.wfs import WebFeatureService
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
    
    def _get_service_title(self, service_obj, default_title: str) -> str:
        """安全地获取服务标题
        
        Args:
            service_obj: OWS服务对象
            default_title: 默认标题
            
        Returns:
            服务标题
        """
        try:
            if hasattr(service_obj, 'identification') and service_obj.identification:
                identification = service_obj.identification
                if hasattr(identification, 'title') and identification.title:
                    return identification.title
        except Exception as e:
            logger.debug(f"获取服务标题失败: {e}")
        
        return default_title
    
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
            
            # 创建WMS服务对象
            wms = WebMapService(capabilities_url, timeout=self.timeout)
            
            # 如果没有提供服务名称，尝试从服务信息中获取
            if not service_name:
                service_name = self._get_service_title(wms, 'Unknown WMS Service')
            
            layers = []
            
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
            
            # 如果没有提供服务名称，尝试从服务信息中获取
            if not service_name:
                service_name = self._get_service_title(wfs, 'Unknown WFS Service')
            
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
    
    async def parse_ogc_service(self, url: str, service_name: str = None) -> List[LayerResourceCreate]:
        """自动检测并解析OGC服务
        
        尝试同时解析WMS和WFS服务，返回所有找到的图层
        
        Args:
            url: OGC服务URL
            service_name: 服务名称（可选）
            
        Returns:
            图层资源创建对象列表
        """
        all_layers = []
        
        # 尝试解析WMS
        try:
            wms_layers = await self.parse_wms_service(url, service_name)
            all_layers.extend(wms_layers)
            logger.info(f"WMS解析成功，找到 {len(wms_layers)} 个图层")
        except Exception as e:
            logger.debug(f"WMS解析失败: {e}")
        
        # 尝试解析WFS
        try:
            wfs_layers = await self.parse_wfs_service(url, service_name)
            all_layers.extend(wfs_layers)
            logger.info(f"WFS解析成功，找到 {len(wfs_layers)} 个要素类型")
        except Exception as e:
            logger.debug(f"WFS解析失败: {e}")
        
        if not all_layers:
            raise ValueError(f"无法从URL解析任何OGC服务: {url}")
        
        logger.info(f"OGC服务解析完成，总共找到 {len(all_layers)} 个图层")
        return all_layers