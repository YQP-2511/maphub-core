"""
图层详细信息获取模块

负责获取WMS、WFS和WMTS图层的详细信息
"""

import logging
import re
from typing import Dict, Any, List
from owslib.wms import WebMapService
from owslib.wfs import WebFeatureService
from owslib.wmts import WebMapTileService
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

    def _extract_tile_matrix_details(self, tile_matrix_set) -> Dict[str, Any]:
        """提取瓦片矩阵集的详细信息
        
        Args:
            tile_matrix_set: OWSLib的TileMatrixSet对象
            
        Returns:
            瓦片矩阵集详细信息字典
        """
        details = {
            "identifier": getattr(tile_matrix_set, 'identifier', ''),
            "title": getattr(tile_matrix_set, 'title', ''),
            "abstract": getattr(tile_matrix_set, 'abstract', ''),
            "crs": getattr(tile_matrix_set, 'crs', ''),
            "matrices": []
        }
        
        # 提取瓦片矩阵信息
        if hasattr(tile_matrix_set, 'tilematrix') and tile_matrix_set.tilematrix:
            for matrix_id, matrix in tile_matrix_set.tilematrix.items():
                matrix_info = {
                    "identifier": matrix_id,
                    "scale_denominator": getattr(matrix, 'scaledenominator', None),
                    "top_left_corner": getattr(matrix, 'topleftcorner', None),
                    "tile_width": getattr(matrix, 'tilewidth', None),
                    "tile_height": getattr(matrix, 'tileheight', None),
                    "matrix_width": getattr(matrix, 'matrixwidth', None),
                    "matrix_height": getattr(matrix, 'matrixheight', None)
                }
                details["matrices"].append(matrix_info)
        
        # 按比例尺排序（从大到小，即从低分辨率到高分辨率）
        if details["matrices"]:
            details["matrices"].sort(
                key=lambda x: x.get("scale_denominator", 0), 
                reverse=True
            )
        
        return details

    async def get_layer_details(self, service_url: str, service_type: str, layer_name: str, strict_mode: bool = False) -> Dict[str, Any]:
        """获取图层详细信息
        
        支持WMS、WFS和WMTS类型的图层
        如果指定的服务类型失败，会尝试另一种服务类型作为备选（除非启用严格模式）
        
        Args:
            service_url: 服务URL（标准化的基础URL）
            service_type: 服务类型（WMS/WFS/WMTS）
            layer_name: 图层名称
            strict_mode: 严格模式，如果为True则不尝试备选服务类型
            
        Returns:
            图层详细信息字典
        """
        service_type_upper = service_type.upper()
        
        if service_type_upper == 'WMS':
            try:
                return await self._get_wms_layer_details(service_url, layer_name)
            except Exception as wms_error:
                if strict_mode:
                    raise ValueError(f"图层 '{layer_name}' 不支持WMS服务: {wms_error}")
                
                logger.debug(f"WMS获取失败，尝试WFS作为备选: {wms_error}")
                try:
                    wfs_details = await self._get_wfs_layer_details(service_url, layer_name)
                    logger.info(f"图层 {layer_name} 实际支持WFS服务，而非WMS")
                    return wfs_details
                except Exception as wfs_error:
                    logger.error(f"WMS和WFS都获取失败: WMS={wms_error}, WFS={wfs_error}")
                    raise ValueError(f"图层 '{layer_name}' 不支持WMS服务: {wms_error}")
                    
        elif service_type_upper == 'WFS':
            try:
                return await self._get_wfs_layer_details(service_url, layer_name)
            except Exception as wfs_error:
                if strict_mode:
                    raise ValueError(f"图层 '{layer_name}' 不支持WFS服务: {wfs_error}")
                
                logger.debug(f"WFS获取失败，尝试WMS作为备选: {wfs_error}")
                try:
                    wms_details = await self._get_wms_layer_details(service_url, layer_name)
                    logger.info(f"图层 {layer_name} 实际支持WMS服务，而非WFS")
                    return wms_details
                except Exception as wms_error:
                    logger.error(f"WFS和WMS都获取失败: WFS={wfs_error}, WMS={wms_error}")
                    raise ValueError(f"图层 '{layer_name}' 不支持WFS服务: {wfs_error}")
                    
        elif service_type_upper == 'WMTS':
            try:
                return await self._get_wmts_layer_details(service_url, layer_name)
            except Exception as wmts_error:
                if strict_mode:
                    raise ValueError(f"图层 '{layer_name}' 不支持WMTS服务: {wmts_error}")
                
                logger.debug(f"WMTS获取失败，尝试WMS作为备选: {wmts_error}")
                try:
                    wms_details = await self._get_wms_layer_details(service_url, layer_name)
                    logger.info(f"图层 {layer_name} 实际支持WMS服务，而非WMTS")
                    return wms_details
                except Exception as wms_error:
                    logger.error(f"WMTS和WMS都获取失败: WMTS={wmts_error}, WMS={wms_error}")
                    raise ValueError(f"图层 '{layer_name}' 不支持WMTS服务: {wmts_error}")
        else:
            raise ValueError(f"不支持的服务类型: {service_type}")

    async def _get_wmts_layer_details(self, service_url: str, layer_name: str) -> Dict[str, Any]:
        """获取WMTS图层详细信息
        
        Args:
            service_url: WMTS服务URL（标准化的基础URL）
            layer_name: 图层名称
            
        Returns:
            WMTS图层详细信息
        """
        # 从标准化的URL重新发现可用端点
        working_url = await self.url_utils.find_working_endpoint(service_url, 'WMTS')
        if not working_url:
            working_url = service_url
        
        # 构建能力文档URL
        capabilities_url = self.url_utils.build_capabilities_url(working_url, 'WMTS')
        
        # 创建WMTS服务对象
        wmts = WebMapTileService(capabilities_url, timeout=self.timeout)
        
        # 查找指定图层
        if layer_name not in wmts.contents:
            raise ValueError(f"图层 '{layer_name}' 在WMTS服务中不存在")
        
        layer = wmts.contents[layer_name]
        
        # 构建详细信息
        details = {
            "service_type": "WMTS",
            "layer_name": layer_name,
            "title": getattr(layer, 'title', layer_name),
            "abstract": getattr(layer, 'abstract', None),
            "keywords": getattr(layer, 'keywords', []),
            "bbox": None,
            "tile_matrix_sets": [],
            "formats": [],
            "styles": [],
            "dimensions": {},
            "resource_urls": {},
            "metadata_urls": [],
            "default_style": None,
            "default_format": "image/png",
            "tile_matrix_details": {}
        }
        
        # 提取边界框信息
        if hasattr(layer, 'boundingBoxWGS84') and layer.boundingBoxWGS84:
            bbox_wgs84 = layer.boundingBoxWGS84
            details["bbox"] = {
                "wgs84": [bbox_wgs84[0], bbox_wgs84[1], bbox_wgs84[2], bbox_wgs84[3]],
                "crs": "EPSG:4326",
                "source": "capabilities"
            }
        
        # 提取瓦片矩阵集信息 - 优先使用新的tilematrixsetlinks属性
        tile_matrix_sets = None
        if hasattr(layer, 'tilematrixsetlinks') and layer.tilematrixsetlinks:
            # 使用新的推荐属性
            tile_matrix_sets = layer.tilematrixsetlinks
        elif hasattr(layer, 'tilematrixsets') and layer.tilematrixsets:
            # 兼容旧属性
            tile_matrix_sets = layer.tilematrixsets
            
        if tile_matrix_sets:
            details["tile_matrix_sets"] = list(tile_matrix_sets)
            
            # 获取瓦片矩阵集的详细信息
            for tms_id in tile_matrix_sets:
                if hasattr(wmts, 'tilematrixsets') and tms_id in wmts.tilematrixsets:
                    tms_details = self._extract_tile_matrix_details(wmts.tilematrixsets[tms_id])
                    details["tile_matrix_details"][tms_id] = tms_details
        
        # 提取支持的格式
        if hasattr(layer, 'formats') and layer.formats:
            details["formats"] = list(layer.formats)
            # 设置默认格式
            if 'image/png' in layer.formats:
                details["default_format"] = 'image/png'
            elif layer.formats:
                details["default_format"] = list(layer.formats)[0]
        
        # 提取样式信息 - 添加类型检查
        if hasattr(layer, 'styles') and layer.styles:
            styles = []
            if isinstance(layer.styles, dict):
                # 如果是字典类型
                for style_id, style in layer.styles.items():
                    style_info = {
                        "identifier": style_id,
                        "title": getattr(style, 'title', style_id),
                        "abstract": getattr(style, 'abstract', None),
                        "is_default": getattr(style, 'isDefault', False)
                    }
                    
                    # 提取图例URL
                    if hasattr(style, 'legend') and style.legend:
                        style_info["legend_url"] = style.legend
                    
                    styles.append(style_info)
                    
                    # 设置默认样式
                    if getattr(style, 'isDefault', False):
                        details["default_style"] = style_id
            elif isinstance(layer.styles, (list, tuple)):
                # 如果是列表类型
                for style in layer.styles:
                    style_id = getattr(style, 'identifier', getattr(style, 'name', ''))
                    style_info = {
                        "identifier": style_id,
                        "title": getattr(style, 'title', style_id),
                        "abstract": getattr(style, 'abstract', None),
                        "is_default": getattr(style, 'isDefault', False)
                    }
                    
                    # 提取图例URL
                    if hasattr(style, 'legend') and style.legend:
                        style_info["legend_url"] = style.legend
                    
                    styles.append(style_info)
                    
                    # 设置默认样式
                    if getattr(style, 'isDefault', False):
                        details["default_style"] = style_id
            
            details["styles"] = styles
            
            # 如果没有找到默认样式，使用第一个
            if not details["default_style"] and styles:
                details["default_style"] = styles[0]["identifier"]
        
        # 提取维度信息、资源URL和元数据URL（保持原有逻辑）
        if hasattr(layer, 'dimensions') and layer.dimensions:
            dimensions = {}
            if isinstance(layer.dimensions, dict):
                # 如果是字典类型
                for dim_name, dimension in layer.dimensions.items():
                    dim_info = {
                        "identifier": dim_name,
                        "title": getattr(dimension, 'title', dim_name),
                        "abstract": getattr(dimension, 'abstract', None),
                        "values": getattr(dimension, 'values', []),
                        "default": getattr(dimension, 'default', None),
                        "current": getattr(dimension, 'current', False),
                        "units": getattr(dimension, 'units', None)
                    }
                    dimensions[dim_name] = dim_info
            elif isinstance(layer.dimensions, (list, tuple)):
                # 如果是列表类型
                for dimension in layer.dimensions:
                    dim_name = getattr(dimension, 'identifier', getattr(dimension, 'name', ''))
                    dim_info = {
                        "identifier": dim_name,
                        "title": getattr(dimension, 'title', dim_name),
                        "abstract": getattr(dimension, 'abstract', None),
                        "values": getattr(dimension, 'values', []),
                        "default": getattr(dimension, 'default', None),
                        "current": getattr(dimension, 'current', False),
                        "units": getattr(dimension, 'units', None)
                    }
                    dimensions[dim_name] = dim_info
            details["dimensions"] = dimensions
        
        # 提取资源URL信息 - 添加类型检查
        if hasattr(layer, 'resourceURLs') and layer.resourceURLs:
            resource_urls = {}
            if isinstance(layer.resourceURLs, dict):
                # 如果是字典类型
                for resource_type, url_info in layer.resourceURLs.items():
                    resource_urls[resource_type] = {
                        "format": getattr(url_info, 'format', None),
                        "template": getattr(url_info, 'template', None),
                        "resource_type": getattr(url_info, 'resourceType', None)
                    }
            elif isinstance(layer.resourceURLs, (list, tuple)):
                # 如果是列表类型
                for url_info in layer.resourceURLs:
                    resource_type = getattr(url_info, 'resourceType', 'unknown')
                    resource_urls[resource_type] = {
                        "format": getattr(url_info, 'format', None),
                        "template": getattr(url_info, 'template', None),
                        "resource_type": resource_type
                    }
            details["resource_urls"] = resource_urls
        
        # 处理元数据URL信息
        if hasattr(layer, 'metadataUrls') and layer.metadataUrls:
            metadata_urls = []
            for metadata_url in layer.metadataUrls:
                url_info = {
                    "type": getattr(metadata_url, 'type', None),
                    "format": getattr(metadata_url, 'format', None),
                    "url": getattr(metadata_url, 'url', None)
                }
                metadata_urls.append(url_info)
            details["metadata_urls"] = metadata_urls
        
        # 直接返回从GetCapabilities获取的标准信息
        return details

    def _get_tilematrix_identifier(self, tile_matrix_set: str, details: Dict[str, Any]) -> str:
        """获取正确的TILEMATRIX标识符
        
        根据瓦片矩阵集详细信息构建正确的TILEMATRIX参数
        支持多种标识符格式的智能匹配
        
        Args:
            tile_matrix_set: 瓦片矩阵集名称
            details: 图层详细信息
            
        Returns:
            正确格式的TILEMATRIX标识符
        """
        try:
            # 检查是否有瓦片矩阵集的详细信息
            if (details.get("tile_matrix_details") and 
                tile_matrix_set in details["tile_matrix_details"]):
                
                tms_details = details["tile_matrix_details"][tile_matrix_set]
                
                # 如果有瓦片矩阵列表，使用第一个（通常是最高级别）
                if "matrices" in tms_details and tms_details["matrices"]:
                    first_matrix = tms_details["matrices"][0]
                    if "identifier" in first_matrix:
                        matrix_id = first_matrix["identifier"]
                        logger.debug(f"使用瓦片矩阵详细信息中的标识符: {matrix_id}")
                        return matrix_id
            
            # 根据常见的GeoServer WMTS命名规则构建标识符
            # 对于EPSG坐标系，通常格式为 "EPSG:4326:0", "EPSG:3857:0" 等
            if "EPSG" in tile_matrix_set.upper():
                # 如果已经包含冒号，直接添加级别
                if ":" in tile_matrix_set:
                    tilematrix_id = f"{tile_matrix_set}:0"
                else:
                    tilematrix_id = f"{tile_matrix_set}:0"
                logger.debug(f"构建EPSG格式标识符: {tilematrix_id}")
                return tilematrix_id
            
            # 对于其他命名规则，尝试多种格式
            possible_formats = [
                f"{tile_matrix_set}:0",  # 标准格式
                "0",                     # 简单数字格式
                f"{tile_matrix_set}_0",  # 下划线格式
                tile_matrix_set          # 直接使用矩阵集名称
            ]
            
            # 返回第一个可能的格式，后续可以在测试中尝试其他格式
            tilematrix_id = possible_formats[0]
            logger.debug(f"使用默认格式标识符: {tilematrix_id}")
            return tilematrix_id
            
        except Exception as e:
            logger.warning(f"构建TILEMATRIX标识符时出错: {e}")
            # 回退到简单格式
            return "0"

    def _get_tilematrix_candidates(self, details: Dict[str, Any], tile_matrix_set: str) -> List[str]:
        """获取瓦片矩阵标识符候选列表
        
        从GetCapabilities响应中提取准确的TILEMATRIX标识符
        
        Args:
            details: 图层详细信息
            tile_matrix_set: 瓦片矩阵集标识符
            
        Returns:
            瓦片矩阵标识符列表（按比例尺从大到小排序）
        """
        try:
            # 直接从瓦片矩阵详细信息中获取准确的标识符
            if (details.get("tile_matrix_details") and 
                tile_matrix_set in details["tile_matrix_details"]):
                
                tms_details = details["tile_matrix_details"][tile_matrix_set]
                
                if "matrices" in tms_details and tms_details["matrices"]:
                    # 返回所有可用的矩阵标识符（已按比例尺排序）
                    candidates = []
                    for matrix in tms_details["matrices"]:
                        if "identifier" in matrix and matrix["identifier"]:
                            candidates.append(matrix["identifier"])
                    
                    if candidates:
                        logger.info(f"从GetCapabilities提取到{len(candidates)}个TILEMATRIX标识符: {candidates[:5]}...")
                        return candidates
            
            # 如果无法从GetCapabilities提取，记录警告并使用基本格式
            logger.warning(f"无法从GetCapabilities提取TILEMATRIX标识符，使用基本格式: {tile_matrix_set}")
            return ["0", f"{tile_matrix_set}:0"]
            
        except Exception as e:
            logger.error(f"提取TILEMATRIX标识符时出错: {e}")
            return ["0", f"{tile_matrix_set}:0"]

    def get_tilematrix_for_zoom(self, details: Dict[str, Any], tile_matrix_set: str, zoom_level: int) -> str:
        """根据缩放级别获取对应的瓦片矩阵标识符
        
        Args:
            details: 图层详细信息
            tile_matrix_set: 瓦片矩阵集标识符
            zoom_level: 缩放级别（0为最低分辨率）
            
        Returns:
            对应的瓦片矩阵标识符
        """
        try:
            if (details.get("tile_matrix_details") and 
                tile_matrix_set in details["tile_matrix_details"]):
                
                tms_details = details["tile_matrix_details"][tile_matrix_set]
                matrices = tms_details.get("matrices", [])
                
                if matrices and 0 <= zoom_level < len(matrices):
                    matrix_id = matrices[zoom_level].get("identifier")
                    if matrix_id:
                        return matrix_id
            
            # 回退到基本格式
            return str(zoom_level)
            
        except Exception as e:
            logger.error(f"获取缩放级别{zoom_level}的瓦片矩阵标识符时出错: {e}")
            return str(zoom_level)

    def _build_wmts_gettile_url(self, service_url: str, layer: str, style: str, 
                               tilematrixset: str, tilematrix: str, tilerow: str, 
                               tilecol: str, format_type: str) -> str:
        """构建WMTS GetTile请求URL
        
        根据WMTS 1.0.0标准构建正确的GetTile请求URL，
        使用从GetCapabilities响应中提取的准确参数
        
        Args:
            service_url: 服务基础URL
            layer: 图层名称
            style: 样式名称
            tilematrixset: 瓦片矩阵集标识符
            tilematrix: 瓦片矩阵标识符（从GetCapabilities提取的准确值）
            tilerow: 瓦片行号
            tilecol: 瓦片列号
            format_type: 图像格式类型
            
        Returns:
            完整的GetTile请求URL
        """
        # 清理service_url，确保不包含已有的GetTile参数
        if "REQUEST=GetTile" in service_url.upper():
            # 如果URL已经包含GetTile参数，提取基础URL
            base_url = service_url.split('?')[0]
            if '?' in service_url:
                # 保留非GetTile相关的参数
                query_params = service_url.split('?')[1]
                filtered_params = []
                for param in query_params.split('&'):
                    param_upper = param.upper()
                    if not any(param_upper.startswith(p) for p in 
                             ['REQUEST=', 'SERVICE=', 'VERSION=', 'LAYER=', 
                              'STYLE=', 'TILEMATRIXSET=', 'TILEMATRIX=', 
                              'TILEROW=', 'TILECOL=', 'FORMAT=']):
                        filtered_params.append(param)
                
                if filtered_params:
                    service_url = f"{base_url}?{'&'.join(filtered_params)}"
                else:
                    service_url = base_url
        
        # 确定URL分隔符
        separator = '&' if '?' in service_url else '?'
        
        # 构建GetTile请求参数（严格按照WMTS 1.0.0标准）
        params = [
            "SERVICE=WMTS",
            "REQUEST=GetTile", 
            "VERSION=1.0.0",
            f"LAYER={layer}",
            f"STYLE={style}",
            f"TILEMATRIXSET={tilematrixset}",
            f"TILEMATRIX={tilematrix}",  # 使用从GetCapabilities提取的准确标识符
            f"TILEROW={tilerow}",
            f"TILECOL={tilecol}",
            f"FORMAT={format_type}"
        ]
        
        url = f"{service_url}{separator}{'&'.join(params)}"
        logger.debug(f"构建WMTS GetTile URL: {url}")
        return url

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