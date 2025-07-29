"""
OGC服务解析器 - 模块化入口

这个文件提供向后兼容的接口，实际功能已被拆分到ogc_parser包中
"""

# 从新的模块化结构中导入所有内容
from .ogc_parser import OGCServiceParser, ogc_parser, get_ogc_parser

# 为了完全向后兼容，重新导出所有内容
__all__ = ['OGCServiceParser', 'ogc_parser', 'get_ogc_parser']