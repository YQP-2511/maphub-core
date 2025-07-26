"""资源模块

包含所有OGC相关的MCP资源：
- layer_registry: 图层注册表和动态模板资源
"""

from .layer_registry import layer_registry_server

__all__ = [
    'layer_registry_server',      # 图层注册表资源
]