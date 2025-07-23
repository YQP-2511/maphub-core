"""
数据库模块

提供SQLite数据库的连接管理、数据模型和数据访问层
"""

from .models import (
    LayerResource,
    LayerResourceCreate,
    LayerResourceUpdate,
    LayerResourceQuery,
    BoundingBox
)
from .connection import (
    DatabaseManager,
    db_manager,
    get_db_manager,
    init_database,
    close_database
)
from .repository import (
    LayerResourceRepository,
    get_layer_repository
)

__all__ = [
    # 数据模型
    'LayerResource',
    'LayerResourceCreate', 
    'LayerResourceUpdate',
    'LayerResourceQuery',
    'BoundingBox',
    
    # 数据库连接
    'DatabaseManager',
    'db_manager',
    'get_db_manager',
    'init_database',
    'close_database',
    
    # 数据访问层
    'LayerResourceRepository',
    'get_layer_repository'
]