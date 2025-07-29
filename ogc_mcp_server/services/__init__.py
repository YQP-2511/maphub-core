"""
服务模块

提供OGC服务相关的业务逻辑
"""

from .layer_service import register_ogc_layers
from .ogc_parser import OGCServiceParser, ogc_parser, get_ogc_parser

__all__ = [
    'register_ogc_layers',
    'OGCServiceParser', 
    'ogc_parser', 
    'get_ogc_parser'
]