"""
WFS过滤器构建模块

负责构建WFS查询的过滤条件，支持属性过滤、空间过滤等
"""

import logging
from typing import Dict, Any, List, Optional, Union
from urllib.parse import quote

logger = logging.getLogger(__name__)


class WFSFilterBuilder:
    """WFS过滤器构建器
    
    支持构建各种类型的WFS过滤条件：
    - 属性过滤（PropertyIsEqualTo, PropertyIsLike等）
    - 空间过滤（BBOX, Intersects等）
    - 逻辑组合（And, Or, Not）
    """
    
    def __init__(self):
        """初始化过滤器构建器"""
        self.filters = []
        self.logical_operator = "And"
    
    def add_property_filter(
        self, 
        property_name: str, 
        value: Union[str, int, float], 
        operator: str = "PropertyIsEqualTo"
    ) -> 'WFSFilterBuilder':
        """添加属性过滤条件
        
        Args:
            property_name: 属性名称
            value: 属性值
            operator: 过滤操作符（PropertyIsEqualTo, PropertyIsLike, 
                     PropertyIsGreaterThan, PropertyIsLessThan等）
                     
        Returns:
            过滤器构建器实例（支持链式调用）
        """
        filter_condition = {
            "type": "property",
            "operator": operator,
            "property_name": property_name,
            "value": value
        }
        self.filters.append(filter_condition)
        return self
    
    def add_like_filter(
        self, 
        property_name: str, 
        pattern: str, 
        wildcard: str = "*", 
        single_char: str = "?", 
        escape_char: str = "\\"
    ) -> 'WFSFilterBuilder':
        """添加模糊匹配过滤条件
        
        Args:
            property_name: 属性名称
            pattern: 匹配模式
            wildcard: 通配符（默认*）
            single_char: 单字符通配符（默认?）
            escape_char: 转义字符（默认\）
            
        Returns:
            过滤器构建器实例
        """
        filter_condition = {
            "type": "like",
            "property_name": property_name,
            "pattern": pattern,
            "wildcard": wildcard,
            "single_char": single_char,
            "escape_char": escape_char
        }
        self.filters.append(filter_condition)
        return self
    
    def add_range_filter(
        self, 
        property_name: str, 
        min_value: Union[int, float], 
        max_value: Union[int, float], 
        include_bounds: bool = True
    ) -> 'WFSFilterBuilder':
        """添加范围过滤条件
        
        Args:
            property_name: 属性名称
            min_value: 最小值
            max_value: 最大值
            include_bounds: 是否包含边界值
            
        Returns:
            过滤器构建器实例
        """
        filter_condition = {
            "type": "range",
            "property_name": property_name,
            "min_value": min_value,
            "max_value": max_value,
            "include_bounds": include_bounds
        }
        self.filters.append(filter_condition)
        return self
    
    def add_bbox_filter(
        self, 
        bbox: List[float], 
        crs: str = "EPSG:4326"
    ) -> 'WFSFilterBuilder':
        """添加边界框过滤条件
        
        Args:
            bbox: 边界框 [minx, miny, maxx, maxy]
            crs: 坐标参考系统
            
        Returns:
            过滤器构建器实例
        """
        filter_condition = {
            "type": "bbox",
            "bbox": bbox,
            "crs": crs
        }
        self.filters.append(filter_condition)
        return self
    
    def set_logical_operator(self, operator: str) -> 'WFSFilterBuilder':
        """设置逻辑操作符
        
        Args:
            operator: 逻辑操作符（And, Or）
            
        Returns:
            过滤器构建器实例
        """
        if operator not in ["And", "Or"]:
            raise ValueError("逻辑操作符必须是 'And' 或 'Or'")
        self.logical_operator = operator
        return self
    
    def build_cql_filter(self) -> Optional[str]:
        """构建CQL过滤器字符串
        
        Returns:
            CQL过滤器字符串，如果没有过滤条件则返回None
        """
        if not self.filters:
            return None
        
        cql_parts = []
        
        for filter_condition in self.filters:
            cql_part = self._build_single_cql_filter(filter_condition)
            if cql_part:
                cql_parts.append(cql_part)
        
        if not cql_parts:
            return None
        
        if len(cql_parts) == 1:
            return cql_parts[0]
        
        # 使用逻辑操作符连接多个条件
        logical_op = " AND " if self.logical_operator == "And" else " OR "
        return f"({logical_op.join(cql_parts)})"
    
    def _build_single_cql_filter(self, filter_condition: Dict[str, Any]) -> Optional[str]:
        """构建单个CQL过滤条件
        
        Args:
            filter_condition: 过滤条件字典
            
        Returns:
            CQL过滤条件字符串
        """
        filter_type = filter_condition.get("type")
        
        if filter_type == "property":
            return self._build_property_cql(filter_condition)
        elif filter_type == "like":
            return self._build_like_cql(filter_condition)
        elif filter_type == "range":
            return self._build_range_cql(filter_condition)
        elif filter_type == "bbox":
            return self._build_bbox_cql(filter_condition)
        
        return None
    
    def _build_property_cql(self, condition: Dict[str, Any]) -> str:
        """构建属性过滤的CQL条件"""
        property_name = condition["property_name"]
        value = condition["value"]
        operator = condition["operator"]
        
        # 处理字符串值的引号
        if isinstance(value, str):
            value = f"'{value}'"
        
        # 映射操作符
        operator_map = {
            "PropertyIsEqualTo": "=",
            "PropertyIsNotEqualTo": "!=",
            "PropertyIsGreaterThan": ">",
            "PropertyIsGreaterThanOrEqualTo": ">=",
            "PropertyIsLessThan": "<",
            "PropertyIsLessThanOrEqualTo": "<="
        }
        
        cql_operator = operator_map.get(operator, "=")
        return f"{property_name} {cql_operator} {value}"
    
    def _build_like_cql(self, condition: Dict[str, Any]) -> str:
        """构建模糊匹配的CQL条件"""
        property_name = condition["property_name"]
        pattern = condition["pattern"]
        
        return f"{property_name} LIKE '{pattern}'"
    
    def _build_range_cql(self, condition: Dict[str, Any]) -> str:
        """构建范围过滤的CQL条件"""
        property_name = condition["property_name"]
        min_value = condition["min_value"]
        max_value = condition["max_value"]
        include_bounds = condition.get("include_bounds", True)
        
        if include_bounds:
            return f"{property_name} >= {min_value} AND {property_name} <= {max_value}"
        else:
            return f"{property_name} > {min_value} AND {property_name} < {max_value}"
    
    def _build_bbox_cql(self, condition: Dict[str, Any]) -> str:
        """构建边界框的CQL条件"""
        bbox = condition["bbox"]
        crs = condition.get("crs", "EPSG:4326")
        
        # BBOX(geometry_column, minx, miny, maxx, maxy, crs)
        return f"BBOX(the_geom, {bbox[0]}, {bbox[1]}, {bbox[2]}, {bbox[3]}, '{crs}')"
    
    def clear(self) -> 'WFSFilterBuilder':
        """清空所有过滤条件
        
        Returns:
            过滤器构建器实例
        """
        self.filters.clear()
        self.logical_operator = "And"
        return self
    
    def get_filter_summary(self) -> Dict[str, Any]:
        """获取过滤器摘要信息
        
        Returns:
            过滤器摘要字典
        """
        return {
            "filter_count": len(self.filters),
            "logical_operator": self.logical_operator,
            "filter_types": [f["type"] for f in self.filters],
            "has_property_filters": any(f["type"] == "property" for f in self.filters),
            "has_spatial_filters": any(f["type"] == "bbox" for f in self.filters),
            "has_like_filters": any(f["type"] == "like" for f in self.filters),
            "has_range_filters": any(f["type"] == "range" for f in self.filters)
        }


def create_simple_property_filter(property_name: str, value: Union[str, int, float]) -> str:
    """创建简单的属性过滤器（便捷函数）
    
    Args:
        property_name: 属性名称
        value: 属性值
        
    Returns:
        CQL过滤器字符串
    """
    builder = WFSFilterBuilder()
    builder.add_property_filter(property_name, value)
    return builder.build_cql_filter()


def create_like_filter(property_name: str, pattern: str) -> str:
    """创建模糊匹配过滤器（便捷函数）
    
    Args:
        property_name: 属性名称
        pattern: 匹配模式
        
    Returns:
        CQL过滤器字符串
    """
    builder = WFSFilterBuilder()
    builder.add_like_filter(property_name, pattern)
    return builder.build_cql_filter()


def create_range_filter(property_name: str, min_value: Union[int, float], max_value: Union[int, float]) -> str:
    """创建范围过滤器（便捷函数）
    
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