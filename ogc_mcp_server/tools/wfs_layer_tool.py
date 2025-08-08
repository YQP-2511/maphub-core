"""简化的WFS图层工具

基于WFS标准HTTP请求，支持完整的过滤和排序功能
分为多个清晰的模块：URL构建、过滤器、排序、数据获取
"""

import json
import logging
import aiohttp
from typing import Dict, Any, List, Optional, Union
from urllib.parse import urlencode, quote
from fastmcp import FastMCP, Context

logger = logging.getLogger(__name__)

# 创建WFS图层工具服务器
wfs_layer_server = FastMCP(name="WFS图层工具")

# 导入全局图层存储
from . import visualization_tools


# ==================== 模块1: WFS URL构建器 ====================

class WFSURLBuilder:
    """WFS请求URL构建器"""
    
    def __init__(self, service_url: str, layer_name: str):
        self.service_url = service_url.rstrip('?&')
        self.layer_name = layer_name
        self.base_params = {
            'service': 'WFS',
            'version': '2.0.0',
            'request': 'GetFeature',
            'typeNames': layer_name,
            'outputFormat': 'application/json'
        }
    
    def build_url(self, 
                  cql_filter: Optional[str] = None,
                  sort_by: Optional[str] = None,
                  max_features: int = 1000,
                  bbox: Optional[List[float]] = None,
                  srs_name: str = "EPSG:4326",
                  property_names: Optional[List[str]] = None) -> str:
        """构建完整的WFS GetFeature URL
        
        Args:
            cql_filter: CQL过滤表达式
            sort_by: 排序字段，格式：'field_name' 或 'field_name+D'(降序)
            max_features: 最大要素数量
            bbox: 边界框 [minx, miny, maxx, maxy]
            srs_name: 坐标参考系统
            property_names: 指定返回的属性字段
            
        Returns:
            完整的WFS请求URL
        """
        params = self.base_params.copy()
        
        # 添加基础参数
        if max_features > 0:
            # WFS 2.0.0使用count参数，早期版本使用maxFeatures参数
            if self.base_params.get('version') == '2.0.0':
                params['count'] = str(max_features)
            else:
                params['maxFeatures'] = str(max_features)
        
        if srs_name:
            params['srsName'] = srs_name
        
        # 添加空间过滤
        if bbox and len(bbox) == 4:
            params['bbox'] = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},{srs_name}"
        
        # 添加属性选择
        if property_names:
            params['propertyName'] = ','.join(property_names)
        
        # 添加CQL过滤器
        if cql_filter:
            params['cql_filter'] = cql_filter
        
        # 添加排序
        if sort_by:
            params['sortBy'] = sort_by
        
        # 构建URL
        query_string = urlencode(params, quote_via=quote)
        separator = '&' if '?' in self.service_url else '?'
        
        return f"{self.service_url}{separator}{query_string}"


# ==================== 模块2: CQL过滤器构建器 ====================

class CQLFilterBuilder:
    """CQL过滤器构建器，支持多种过滤条件组合"""
    
    @staticmethod
    def build_simple_filter(attribute: str, values: Union[str, List[str]], operator: str = "=") -> str:
        """构建简单过滤条件
        
        Args:
            attribute: 属性名
            values: 值或值列表
            operator: 操作符 (=, !=, >, <, >=, <=, LIKE, IN, BETWEEN)
            
        Returns:
            CQL过滤表达式
        """
        if isinstance(values, str):
            values = [values]
        
        # 智能处理数值和字符串
        processed_values = []
        for v in values:
            str_v = str(v)
            # 检查是否为数值（整数或小数）
            if CQLFilterBuilder._is_numeric(str_v):
                processed_values.append(str_v)  # 数值不加引号
            else:
                # 字符串需要转义单引号并加引号
                escaped_v = str_v.replace("'", "''")
                processed_values.append(f"'{escaped_v}'")
        
        if operator.upper() == "IN" or (operator == "=" and len(values) > 1):
            return f"{attribute} IN ({', '.join(processed_values)})"
        
        elif operator.upper() == "LIKE":
            # LIKE操作符总是需要引号，因为它用于字符串匹配
            original_value = str(values[0]).replace("'", "''")
            return f"{attribute} LIKE '%{original_value}%'"
        
        elif operator.upper() == "BETWEEN":
            # BETWEEN操作符需要两个值
            if len(processed_values) < 2:
                raise ValueError(f"BETWEEN操作符需要两个值，但只提供了 {len(processed_values)} 个")
            return f"{attribute} BETWEEN {processed_values[0]} AND {processed_values[1]}"
        
        elif operator in ["=", "!=", ">", "<", ">=", "<="]:
            return f"{attribute} {operator} {processed_values[0]}"
        
        else:
            raise ValueError(f"不支持的操作符: {operator}")
    
    @staticmethod
    def _is_numeric(value: str) -> bool:
        """检查字符串是否为数值（整数或小数）
        
        Args:
            value: 要检查的字符串
            
        Returns:
            如果是数值返回True，否则返回False
        """
        try:
            float(value)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def build_range_filter(attribute: str, min_value: str, max_value: str) -> str:
        """构建范围过滤条件"""
        # 智能处理数值和字符串
        if CQLFilterBuilder._is_numeric(min_value) and CQLFilterBuilder._is_numeric(max_value):
            return f"{attribute} BETWEEN {min_value} AND {max_value}"
        else:
            min_escaped = str(min_value).replace("'", "''")
            max_escaped = str(max_value).replace("'", "''")
            return f"{attribute} BETWEEN '{min_escaped}' AND '{max_escaped}'"
    
    @staticmethod
    def combine_filters(filters: List[str], logic: str = "AND") -> str:
        """组合多个过滤条件
        
        Args:
            filters: 过滤条件列表
            logic: 逻辑操作符 (AND, OR)
            
        Returns:
            组合后的CQL表达式
        """
        if not filters:
            return ""
        
        if len(filters) == 1:
            return filters[0]
        
        logic_op = f" {logic.upper()} "
        return f"({logic_op.join(filters)})"
    
    @staticmethod
    def build_from_json(filter_config: Dict[str, Any]) -> str:
        """从JSON配置构建CQL过滤器
        
        JSON格式示例:
        {
            "filters": [
                {"attribute": "CITY_NAME", "values": ["北京", "上海"], "operator": "IN"},
                {"attribute": "POPULATION", "values": ["1000000"], "operator": ">"},
                {"attribute": "LAND_KM", "values": ["100000", "500000"], "operator": "BETWEEN"}
            ],
            "logic": "AND"
        }
        """
        filters_list = filter_config.get("filters", [])
        logic = filter_config.get("logic", "AND")
        
        cql_parts = []
        for filter_item in filters_list:
            attribute = filter_item.get("attribute")
            values = filter_item.get("values", [])
            operator = filter_item.get("operator", "=")
            
            if attribute and values:
                # 对于BETWEEN操作符，使用专门的build_range_filter方法
                if operator.upper() == "BETWEEN" and len(values) >= 2:
                    cql_part = CQLFilterBuilder.build_range_filter(attribute, values[0], values[1])
                else:
                    cql_part = CQLFilterBuilder.build_simple_filter(attribute, values, operator)
                cql_parts.append(cql_part)
        
        return CQLFilterBuilder.combine_filters(cql_parts, logic)


# ==================== 模块3: 排序构建器 ====================

class SortBuilder:
    """WFS排序参数构建器"""
    
    @staticmethod
    def build_sort_param(sort_config: Union[str, Dict[str, Any]]) -> str:
        """构建sortBy参数
        
        Args:
            sort_config: 排序配置
                - 字符串格式: "field_name" 或 "field_name+D"
                - 字典格式: {"attribute": "field_name", "order": "asc|desc"}
                - 多字段: [{"attribute": "field1", "order": "asc"}, ...]
                
        Returns:
            sortBy参数值
        """
        if isinstance(sort_config, str):
            return sort_config
        
        elif isinstance(sort_config, dict):
            attribute = sort_config.get("attribute")
            order = sort_config.get("order", "asc").lower()
            
            if not attribute:
                raise ValueError("排序配置缺少attribute字段")
            
            # 修复：使用空格分隔格式，这是WFS标准格式
            if order == "desc":
                return f"{attribute} D"
            else:
                return f"{attribute} A"
        
        elif isinstance(sort_config, list):
            # 多字段排序
            sort_parts = []
            for item in sort_config:
                if isinstance(item, dict):
                    part = SortBuilder.build_sort_param(item)
                    sort_parts.append(part)
            return ",".join(sort_parts)
        
        else:
            raise ValueError(f"不支持的排序配置类型: {type(sort_config)}")


# ==================== 模块4: 数据获取器 ====================

class WFSDataFetcher:
    """WFS数据获取器"""
    
    def __init__(self, timeout: int = 60):
        self.timeout = timeout
    
    async def fetch_data(self, url: str, ctx: Optional[Context] = None) -> Dict[str, Any]:
        """获取WFS数据
        
        Args:
            url: WFS请求URL
            ctx: MCP上下文
            
        Returns:
            GeoJSON格式的数据
        """
        if ctx:
            await ctx.info(f"🌐 发送WFS请求: {url}")
            await ctx.debug(f"🔍 完整URL: {url}")
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        if ctx:
                            await ctx.error(f"HTTP {response.status} 错误响应: {error_text[:200]}")
                        raise Exception(f"HTTP错误 {response.status}: {error_text}")
                    
                    content_type = response.headers.get('content-type', '').lower()
                    if 'json' not in content_type:
                        text_content = await response.text()
                        if 'exception' in text_content.lower() or 'error' in text_content.lower():
                            raise Exception(f"WFS服务错误: {text_content[:500]}")
                    
                    data = await response.json()
                    
                    # 验证GeoJSON格式
                    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
                        raise Exception("返回数据不是有效的GeoJSON格式")
                    
                    features = data.get("features", [])
                    if ctx:
                        await ctx.info(f"✅ 成功获取 {len(features)} 个要素")
                    
                    return data
                    
        except Exception as e:
            error_msg = f"WFS数据获取失败: {str(e)}"
            if ctx:
                await ctx.error(error_msg)
            raise Exception(error_msg)


# ==================== 模块5: 图层信息获取器 ====================

async def get_layer_info_from_registry(layer_name: str, ctx: Optional[Context] = None) -> Dict[str, Any]:
    """从图层注册表获取图层信息
    
    Args:
        layer_name: 图层名称
        ctx: MCP上下文对象
        
    Returns:
        图层详细信息字典
        
    Raises:
        ValueError: 当无法获取图层信息时
    """
    try:
        # 使用MCP资源读取机制获取图层详情
        if not ctx:
            raise ValueError("需要MCP上下文来读取资源")
        
        # 读取图层详细资源
        layer_resource_result = await ctx.read_resource(f"ogc://layer/{layer_name}")
        
        if not layer_resource_result or not layer_resource_result[0].content:
            raise ValueError(f"无法获取图层 '{layer_name}' 的详细信息")
        
        layer_content = layer_resource_result[0].content
        
        # 处理不同类型的资源数据
        layer_info: Dict[str, Any] = {}
        
        if isinstance(layer_content, str):
            # 字符串类型，需要JSON解析
            layer_info = json.loads(layer_content)
        elif isinstance(layer_content, bytes):
            # 字节类型，先解码再JSON解析
            layer_info = json.loads(layer_content.decode('utf-8'))
        elif isinstance(layer_content, dict):
            # 字典类型，直接使用
            layer_info = layer_content
        else:
            # 其他类型，尝试转换为字符串再解析
            layer_info = json.loads(str(layer_content))
        
        # 检查是否有错误信息
        if isinstance(layer_info, dict) and "error" in layer_info:
            raise ValueError(layer_info["error"])
        
        return layer_info
        
    except json.JSONDecodeError as e:
        error_msg = f"解析图层信息JSON失败: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        raise ValueError(error_msg)
    except Exception as e:
        error_msg = f"获取图层信息失败: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        raise ValueError(error_msg)


# ==================== 主工具函数 ====================

@wfs_layer_server.tool(
    name="add_wfs_layer",
    description="""添加WFS矢量图层，支持完整的过滤、排序和属性显示功能。
重点：在执行该工具前要先执行get_wfs_layer_attributes工具获取图层属性信息

🔍 查询参数 (JSON格式):
{
  "filters": [
    {"attribute": "名称字段", "values": ["查询值"], "operator": "="}
  ],
  "sort": {"attribute": "排序字段", "order": "desc"},
  "display_attributes": ["显示字段1", "显示字段2", "显示字段3"],
  "limit": 100,
  "logic": "AND"
}

📋 参数说明:
- filters: 过滤条件列表，用于筛选数据
- sort: 排序条件，决定数据的显示顺序
- display_attributes: 要显示的属性列表，即使不用于过滤或排序也会返回这些属性
- limit: 返回的最大要素数量
- logic: 多个过滤条件之间的逻辑关系(AND/OR)

📊 属性显示说明:
- 如果不指定display_attributes，系统只会返回用于过滤和排序的属性
- 要查看特定属性(如人口、面积、温度等)，请将其添加到display_attributes列表中
- 例如: 要查看某地区的温度情况，应同时指定地区名称过滤和温度字段显示属性

📋 支持的操作符:
- 等于: = 
- 不等于: !=
- 大于/小于: >, <, >=, <=
- 包含: IN (多值)
- 模糊匹配: LIKE (如 "北%" 匹配所有"北"开头的值)
- 范围: BETWEEN (需要提供两个值)

🔄 排序选项:
- 升序: {"attribute": "field_name", "order": "asc"}
- 降序: {"attribute": "field_name", "order": "desc"}
- 多字段: [{"attribute": "field1", "order": "asc"}, {"attribute": "field2", "order": "desc"}]

💡 多属性查询示例:
- 查看特定区域的多个属性: 
  {"filters": [
    {"attribute": "区域名称", "values": ["区域1","区域2"], "operator": "IN"}
  ], 
  "display_attributes": ["属性1", "属性2", "属性3"],
  "logic": "AND"}

- 按数值大小筛选并排序:
  {"filters": [
    {"attribute": "数值字段", "values": ["阈值"], "operator": ">"}
  ], 
  "sort": {"attribute": "数值字段", "order": "desc"},
  "display_attributes": ["名称字段", "数值字段", "其他属性"],
  "logic": "AND"}

- 复杂条件查询:
  {"filters": [
    {"attribute": "属性A", "values": ["属性B"], "operator": ">"},
    {"attribute": "属性C", "values": ["阈值"], "operator": "<"}
  ], 
  "display_attributes": ["名称字段", "属性A", "属性B", "属性C"],
  "logic": "AND"}

📊 性能优化建议:
- 使用精确的过滤条件减少返回数据量
- 设置合理的limit值限制返回要素数量
- 只查询必要的属性字段(系统会自动添加ID和几何字段)
- 对大数据集使用BETWEEN代替多个>/<条件

🌟 常见属性字段类型:
- 名称/标识: NAME, ID, CODE (文本或数字)
- 数值型: VALUE, COUNT, AMOUNT (整数或小数)
- 比例型: RATE, PERCENTAGE, RATIO (小数，如0.75表示75%)
- 面积/长度: AREA, LENGTH, DISTANCE (数值，通常带单位)
- 时间型: DATE, TIME, TIMESTAMP (日期时间格式)
""",
    tags={"wfs", "layer", "vector", "filter", "sort", "query", "numeric"}
)
async def add_wfs_layer(
    layer_name: str,
    query: Optional[str] = None,
    max_features: int = 1000,
    layer_title: Optional[str] = None,
    display_attributes: Optional[List[str]] = None,  # 新增参数
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """添加WFS图层到地图
    
    Args:
        layer_name: 图层名称
        query: JSON格式的查询参数，包含filters、sort、limit、logic等
        max_features: 最大要素数量
        layer_title: 自定义图层标题
        ctx: MCP上下文
        
    Returns:
        操作结果字典
    """
    try:
        if ctx:
            await ctx.info(f"🔍 开始添加WFS图层: {layer_name}")
        
        # 获取图层信息
        layer_info = await get_layer_info_from_registry(layer_name, ctx)
        
        # 验证WFS支持
        wfs_params = layer_info.get("access_parameters", {}).get("wfs")
        if not wfs_params:
            supported_services = layer_info.get("metadata", {}).get("supported_services", [])
            raise ValueError(
                f"图层 '{layer_name}' 不支持WFS服务。"
                f"支持的服务类型: {', '.join(supported_services) if supported_services else '无'}"
            )
        
        # 获取服务URL并确保是WFS端点
        service_url = layer_info.get("basic_info", {}).get("service_url", "")
        if not service_url:
            raise ValueError(f"图层 '{layer_name}' 缺少服务URL")
        
        # 确保服务URL指向WFS端点
        if "wmts" in service_url.lower():
            # 如果是WMTS URL，转换为WFS URL
            service_url = service_url.replace("/gwc/service/wmts", "/wfs").replace("/wmts", "/wfs")
        elif not service_url.endswith(("/wfs", "/ows")):
            # 如果不是标准的WFS端点，添加/wfs
            if service_url.endswith("/"):
                service_url = service_url + "wfs"
            else:
                service_url = service_url + "/wfs"
        
        if ctx:
            await ctx.debug(f"🔧 优化后的WFS服务URL: {service_url}")
        
        # 解析查询参数
        query_config = {}
        if query:
            try:
                query_config = json.loads(query)
            except json.JSONDecodeError as e:
                raise ValueError(f"查询参数JSON格式错误: {str(e)}")
        # 处理 display_attributes 参数
        if display_attributes:
            query_config["display_attributes"] = display_attributes
        # 构建URL
        url_builder = WFSURLBuilder(service_url, layer_name)
        
        # 构建CQL过滤器
        cql_filter = None
        if query_config.get("filters"):
            cql_filter = CQLFilterBuilder.build_from_json(query_config)
            if ctx:
                await ctx.info(f"🎯 CQL过滤器: {cql_filter}")
        
        # 构建排序参数
        sort_by = None
        if query_config.get("sort"):
            sort_by = SortBuilder.build_sort_param(query_config["sort"])
            if ctx:
                await ctx.info(f"📊 排序参数: {sort_by}")
        
        # 应用限制
        effective_max_features = query_config.get("limit", max_features)
        
        # 提取查询的属性
        queried_attributes = _extract_queried_attributes(query_config)
        if ctx and queried_attributes:
            await ctx.debug(f"📋 查询的属性: {', '.join(queried_attributes)}")
        
        # 获取主标识字段
        primary_identifier = _get_primary_identifier(layer_info)
        if ctx:
            await ctx.debug(f"🔑 主标识字段: {primary_identifier}")
        
        # 获取几何字段
        geometry_field = _get_geometry_field_name(layer_info)
        if ctx:
            await ctx.debug(f"🌐 几何字段: {geometry_field}")
        
        # 构建属性限制列表
        property_names = []
        
        # 只有在有查询条件时才限制属性
        if queried_attributes:
            # 添加查询的属性
            for attr in queried_attributes:
                if attr not in property_names:
                    property_names.append(attr)
            
            # 添加主标识字段
            if primary_identifier and primary_identifier not in property_names:
                property_names.append(primary_identifier)
            
            # 添加几何字段
            if geometry_field and geometry_field not in property_names:
                property_names.append(geometry_field)
            
            if ctx and property_names:
                await ctx.debug(f"📝 属性限制列表: {', '.join(property_names)}")
        else:
            # 没有查询条件时，不限制属性（返回全部属性）
            if ctx:
                await ctx.debug(f"📝 未指定查询条件，将返回全部属性")
            property_names = None
        
        # 构建完整URL
        wfs_url = url_builder.build_url(
            cql_filter=cql_filter,
            sort_by=sort_by,
            max_features=effective_max_features,
            srs_name=wfs_params.get("srsName", "EPSG:4326"),
            property_names=property_names if property_names else None
        )
        
        if ctx:
            await ctx.debug(f"🔗 构建的WFS URL: {wfs_url}")
            await ctx.debug(f"🏗️ 服务基础URL: {service_url}")
            await ctx.debug(f"📋 WFS参数: {wfs_params}")
        
        # 获取数据
        data_fetcher = WFSDataFetcher()
        geojson_data = await data_fetcher.fetch_data(wfs_url, ctx)
        
        # 分析结果
        features = geojson_data.get("features", [])
        feature_count = len(features)
        
        # 添加调试信息：显示实际获取的要素数量和期望的数量
        if ctx:
            await ctx.info(f"📊 实际获取要素数量: {feature_count}")
            await ctx.info(f"🎯 期望获取要素数量: {effective_max_features}")
            if sort_by:
                await ctx.info(f"🔄 排序参数: {sort_by}")
            
            # 如果有排序，显示前几个要素的关键属性
            if sort_by and features:
                # 修复：正确处理多字段排序的情况
                sort_config = query_config.get("sort")
                sort_attribute = None
                
                if isinstance(sort_config, dict):
                    sort_attribute = sort_config.get("attribute")
                elif isinstance(sort_config, list) and sort_config:
                    # 对于多字段排序，显示第一个排序字段
                    first_sort = sort_config[0]
                    if isinstance(first_sort, dict):
                        sort_attribute = first_sort.get("attribute")
                
                if sort_attribute:
                    await ctx.info(f"📋 前3个要素的{sort_attribute}值:")
                    for i, feature in enumerate(features[:3]):
                        props = feature.get("properties", {})
                        value = props.get(sort_attribute, "N/A")
                        state_name = props.get("STATE_NAME", props.get("NAME", f"要素{i+1}"))
                        await ctx.info(f"  {i+1}. {state_name}: {value}")
        
        if feature_count == 0 and (cql_filter or sort_by):
            return {
                "success": False,
                "message": "查询条件未匹配到任何要素",
                "layer_name": layer_name,
                "query_config": query_config,
                "wfs_url": wfs_url,
                "current_layer_count": len(visualization_tools._current_layers)
            }
        
        # 创建增强的图层对象，包含更多调试信息
        wfs_layer = {
            "id": f"wfs_{layer_name}_{len(visualization_tools._current_layers)}",
            "name": layer_name,
            "title": layer_title or layer_name,
            "layer_name": layer_name,  # 添加layer_name字段以匹配模板显示需求
            "type": "wfs",  # 将"geojson"改为"wfs"
            "service_type": "wfs",  # 添加服务类型标识
            "source": "wfs_service",
            "geojson_data": geojson_data,  # 修改字段名以匹配模板期望
            "data": geojson_data,  # 保留原字段以兼容其他逻辑
            "feature_count": feature_count,
            # 添加默认样式配置
            "style": {
                "color": "#3388ff",
                "weight": 2,
                "opacity": 0.8,
                "fillColor": "#3388ff",
                "fillOpacity": 0.2
            },
            "opacity": 0.8,  # 添加透明度字段
            "visible": True,  # 添加可见性字段
            "query_info": {
                "has_filter": bool(cql_filter),
                "has_sort": bool(sort_by),
                "cql_filter": cql_filter,
                "sort_by": sort_by,
                "max_features": effective_max_features,
                "requested_limit": query_config.get("limit"),
                "actual_returned": feature_count
            },
            "service_info": {
                "service_url": service_url,
                "layer_name": layer_name,
                "wfs_url": wfs_url
            },
            # 添加图层信息以匹配模板期望
            "layer_info": {
                "layer_name": layer_name,  # 确保layer_info中也有layer_name
                "service_name": service_url.split('/')[2] if '//' in service_url else "WFS服务",
                "layer_title": layer_title or layer_name,
                "crs": "EPSG:4326"
            },
            "metadata": {
                "created_at": json.dumps({"timestamp": "now"}),
                "source": "wfs_layer_tool_v2"
            },
            # 添加几何类型信息以便可视化
            "geometry_type": _detect_geometry_type(geojson_data),
            # 添加边界框信息
            "bbox": _calculate_bbox(geojson_data)
        }
        
        # 添加到图层列表
        visualization_tools._current_layers.append(wfs_layer)
        
        # 构建成功消息
        success_msg = f"✅ WFS图层 '{layer_name}' 添加成功，包含 {feature_count} 个要素"
        if cql_filter:
            success_msg += f"，应用了过滤条件"
        if sort_by:
            success_msg += f"，应用了排序"
        
        if ctx:
            await ctx.info(success_msg)
        
        return {
            "success": True,
            "message": success_msg,
            "layer_info": {
                "name": layer_name,
                "title": wfs_layer["title"],
                "type": "wfs",
                "feature_count": feature_count,
                "has_filter": bool(cql_filter),
                "has_sort": bool(sort_by),
                "query_config": query_config
            },
            "current_layer_count": len(visualization_tools._current_layers)
        }
        
    except Exception as e:
        error_msg = f"❌ 添加WFS图层失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        if ctx:
            await ctx.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "layer_name": layer_name,
            "current_layer_count": len(visualization_tools._current_layers)
        }


# ==================== 辅助工具 ====================

def _detect_geometry_type(geojson_data: Dict[str, Any]) -> str:
    """检测GeoJSON数据的几何类型"""
    features = geojson_data.get("features", [])
    if not features:
        return "unknown"
    
    # 检查第一个要素的几何类型
    first_feature = features[0]
    geometry = first_feature.get("geometry", {})
    return geometry.get("type", "unknown").lower()


def _calculate_bbox(geojson_data: Dict[str, Any]) -> Optional[List[float]]:
    """计算GeoJSON数据的边界框"""
    features = geojson_data.get("features", [])
    if not features:
        return None
    
    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')
    
    for feature in features:
        geometry = feature.get("geometry", {})
        coords = geometry.get("coordinates", [])
        
        if geometry.get("type") == "Point":
            x, y = coords
            min_x, max_x = min(min_x, x), max(max_x, x)
            min_y, max_y = min(min_y, y), max(max_y, y)
        elif geometry.get("type") in ["LineString", "MultiPoint"]:
            for coord in coords:
                x, y = coord
                min_x, max_x = min(min_x, x), max(max_x, x)
                min_y, max_y = min(min_y, y), max(max_y, y)
        elif geometry.get("type") in ["Polygon", "MultiLineString"]:
            for ring in coords:
                for coord in ring:
                    x, y = coord
                    min_x, max_x = min(min_x, x), max(max_x, x)
                    min_y, max_y = min(min_y, y), max(max_y, y)
        elif geometry.get("type") == "MultiPolygon":
            for polygon in coords:
                for ring in polygon:
                    for coord in ring:
                        x, y = coord
                        min_x, max_x = min(min_x, x), max(max_x, x)
                        min_y, max_y = min(min_y, y), max(max_y, y)
    
    if min_x != float('inf'):
        return [min_x, min_y, max_x, max_y]
    return None

def _extract_queried_attributes(query_config: Dict[str, Any]) -> List[str]:
    """从查询配置中提取查询的属性名称
    
    Args:
        query_config: 查询配置字典
        
    Returns:
        查询属性名称列表
    """
    queried_attributes = []
    
    # 从过滤条件中提取属性
    filters = query_config.get("filters", [])
    for filter_item in filters:
        attribute = filter_item.get("attribute")
        if attribute and attribute not in queried_attributes:
            queried_attributes.append(attribute)
    
    # 从排序配置中提取属性
    sort_config = query_config.get("sort")
    if sort_config:
        if isinstance(sort_config, dict):
            sort_attr = sort_config.get("attribute")
            if sort_attr and sort_attr not in queried_attributes:
                queried_attributes.append(sort_attr)
        elif isinstance(sort_config, list):
            for sort_item in sort_config:
                if isinstance(sort_item, dict):
                    sort_attr = sort_item.get("attribute")
                    if sort_attr and sort_attr not in queried_attributes:
                        queried_attributes.append(sort_attr)
    # 新增：从显示属性列表中提取属性
    display_attributes = query_config.get("display_attributes", [])
    if display_attributes:
        for attr in display_attributes:
            if attr and attr not in queried_attributes:
                queried_attributes.append(attr)
    
    return queried_attributes                    


def _get_primary_identifier(layer_info: Dict[str, Any]) -> Optional[str]:
    """获取图层的主标识字段
    
    Args:
        layer_info: 图层信息字典
        
    Returns:
        主标识字段名称
    """
    # 常见的主标识字段名称
    common_id_fields = ["OBJECTID", "FID", "ID", "GEOID", "STATE_FIPS", "FIPS", "STATE_ABBR"]
    
    # 首先检查详细能力中的属性
    detailed_capabilities = layer_info.get("detailed_capabilities", {})
    wfs_capabilities = detailed_capabilities.get("wfs", {})
    
    # 1. 首先从detailed_capabilities.wfs.attributes中查找
    attributes = wfs_capabilities.get("attributes", [])
    if attributes:
        for attr in attributes:
            attr_name = attr.get("name", "") if isinstance(attr, dict) else str(attr)
            if attr_name.upper() in [field.upper() for field in common_id_fields]:
                return attr_name
    
    # 2. 然后从capabilities.attributes中查找
    capabilities = layer_info.get("capabilities", {})
    cap_attributes = capabilities.get("attributes", [])
    if cap_attributes:
        for attr in cap_attributes:
            attr_name = attr.get("name", "") if isinstance(attr, dict) else str(attr)
            if attr_name.upper() in [field.upper() for field in common_id_fields]:
                return attr_name
    
    # 3. 最后从fields中查找（向后兼容）
    fields = layer_info.get("fields", [])
    if fields:
        for field in fields:
            field_name = field.get("name", "") if isinstance(field, dict) else str(field)
            if field_name.upper() in [field.upper() for field in common_id_fields]:
                return field_name
    
    # 4. 如果没有找到常见ID字段，尝试查找包含"ID"的字段
    # 再次检查所有属性源
    for attr_list in [attributes, cap_attributes, fields]:
        if attr_list:
            for attr in attr_list:
                attr_name = attr.get("name", "") if isinstance(attr, dict) else str(attr)
                if "ID" in attr_name.upper():
                    return attr_name
    
    # 5. 新增：查找包含"NAME"的字段作为主标识
    for attr_list in [attributes, cap_attributes, fields]:
        if attr_list:
            for attr in attr_list:
                attr_name = attr.get("name", "") if isinstance(attr, dict) else str(attr)
                if "NAME" in attr_name.upper():
                    return attr_name
    
    # 6. 如果仍然没有找到，返回第一个非几何字段
    geometry_field = _get_geometry_field_name(layer_info)
    for attr_list in [attributes, cap_attributes, fields]:
        if attr_list:
            for attr in attr_list:
                attr_name = attr.get("name", "") if isinstance(attr, dict) else str(attr)
                if attr_name != geometry_field:
                    return attr_name
    
    # 7. 如果所有尝试都失败，返回默认值
    return "OBJECTID"


def _get_geometry_field_name(layer_info: Dict[str, Any]) -> str:
    """获取图层的几何字段名称
    
    Args:
        layer_info: 图层信息字典
        
    Returns:
        几何字段名称
    """
    # 常见的几何字段名称
    common_geom_fields = ["SHAPE", "GEOMETRY", "THE_GEOM", "GEOM", "SHAPE_GEOMETRY"]
    
    # 首先检查详细能力中的属性
    detailed_capabilities = layer_info.get("detailed_capabilities", {})
    wfs_capabilities = detailed_capabilities.get("wfs", {})
    
    # 1. 首先从detailed_capabilities.wfs.attributes中查找
    attributes = wfs_capabilities.get("attributes", [])
    if attributes:
        # 查找类型包含"geometry"或"geom"的字段
        for attr in attributes:
            if isinstance(attr, dict):
                attr_type = attr.get("type", "").lower()
                attr_name = attr.get("name", "")
                if "geometry" in attr_type or "geom" in attr_type:
                    return attr_name
                
        # 查找名称匹配常见几何字段的字段
        for attr in attributes:
            attr_name = attr.get("name", "") if isinstance(attr, dict) else str(attr)
            if attr_name.upper() in [field.upper() for field in common_geom_fields]:
                return attr_name
    
    # 2. 然后从capabilities.attributes中查找
    capabilities = layer_info.get("capabilities", {})
    cap_attributes = capabilities.get("attributes", [])
    if cap_attributes:
        # 查找类型包含"geometry"或"geom"的字段
        for attr in cap_attributes:
            if isinstance(attr, dict):
                attr_type = attr.get("type", "").lower()
                attr_name = attr.get("name", "")
                if "geometry" in attr_type or "geom" in attr_type:
                    return attr_name
                
        # 查找名称匹配常见几何字段的字段
        for attr in cap_attributes:
            attr_name = attr.get("name", "") if isinstance(attr, dict) else str(attr)
            if attr_name.upper() in [field.upper() for field in common_geom_fields]:
                return attr_name
    
    # 3. 最后从fields中查找（向后兼容）
    fields = layer_info.get("fields", [])
    if fields:
        # 查找类型包含"geometry"或"geom"的字段
        for field in fields:
            if isinstance(field, dict):
                field_type = field.get("type", "").lower()
                field_name = field.get("name", "")
                if "geometry" in field_type or "geom" in field_type:
                    return field_name
                
        # 查找名称匹配常见几何字段的字段
        for field in fields:
            field_name = field.get("name", "") if isinstance(field, dict) else str(field)
            if field_name.upper() in [field.upper() for field in common_geom_fields]:
                return field_name
    
    # 4. 如果没有找到，查找名称中包含"geom"的字段
    for attr_list in [attributes, cap_attributes, fields]:
        if attr_list:
            for attr in attr_list:
                attr_name = attr.get("name", "") if isinstance(attr, dict) else str(attr)
                if "GEOM" in attr_name.upper():
                    return attr_name
    
    # 5. 如果所有尝试都失败，返回默认值
    return "the_geom"

