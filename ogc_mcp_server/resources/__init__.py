"""资源模块

包含所有OGC相关的MCP资源：
- layer_resources: 图层资源和模板
"""

from .layer_resources import layer_resource_server

__all__ = ['layer_resource_server']