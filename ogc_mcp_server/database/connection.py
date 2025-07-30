"""
数据库连接管理模块

提供SQLite数据库的连接、初始化和管理功能
"""

import aiosqlite
import logging
from pathlib import Path
from typing import Optional
import asyncio

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器
    
    负责SQLite数据库的连接管理、初始化和基础操作
    """
    
    def __init__(self, db_path: str = "data/ogc_layers.db"):
        """初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self._connection: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
        
        # 确保数据目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    async def connect(self) -> aiosqlite.Connection:
        """获取数据库连接
        
        Returns:
            数据库连接对象
        """
        async with self._lock:
            if self._connection is None:
                self._connection = await aiosqlite.connect(
                    self.db_path,
                    check_same_thread=False
                )
                # 启用外键约束
                await self._connection.execute("PRAGMA foreign_keys = ON")
                await self._connection.commit()
                logger.info(f"数据库连接已建立: {self.db_path}")
            
            return self._connection
    
    async def close(self):
        """关闭数据库连接"""
        async with self._lock:
            if self._connection:
                await self._connection.close()
                self._connection = None
                logger.info("数据库连接已关闭")
    
    async def initialize_database(self):
        """初始化数据库表结构
        
        创建基础元数据表，不包含动态参数字段
        """
        conn = await self.connect()
        
        # 检查表是否存在
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='layer_resources';")
        table_exists = await cursor.fetchone()
        
        if table_exists:
            # 检查表结构是否需要更新（去除crs和bbox字段）
            cursor = await conn.execute("PRAGMA table_info(layer_resources);")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            # 如果存在crs或bbox字段，需要重建表
            if 'crs' in column_names or 'bbox' in column_names:
                logger.info("检测到旧的表结构，正在更新为基础元数据表...")
                await self._migrate_to_basic_metadata(conn)
        
        # 创建基础元数据表（只包含基础字段）
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS layer_resources (
            resource_id TEXT PRIMARY KEY,
            service_name TEXT NOT NULL,
            service_url TEXT NOT NULL,
            service_type TEXT NOT NULL CHECK (service_type IN ('WMS', 'WFS')),
            layer_name TEXT NOT NULL,
            layer_title TEXT,
            layer_abstract TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(service_url, layer_name, service_type)
        );
        """
        
        # 创建索引
        create_indexes_sql = [
            "CREATE INDEX IF NOT EXISTS idx_service_type ON layer_resources(service_type);",
            "CREATE INDEX IF NOT EXISTS idx_service_name ON layer_resources(service_name);",
            "CREATE INDEX IF NOT EXISTS idx_layer_name ON layer_resources(layer_name);",
            "CREATE INDEX IF NOT EXISTS idx_service_url ON layer_resources(service_url);"
        ]
        
        try:
            await conn.execute(create_table_sql)
            
            for index_sql in create_indexes_sql:
                await conn.execute(index_sql)
            
            await conn.commit()
            logger.info("基础元数据表结构初始化完成")
            
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            await conn.rollback()
            raise
    
    async def _migrate_to_basic_metadata(self, conn: aiosqlite.Connection):
        """迁移到基础元数据表结构
        
        Args:
            conn: 数据库连接
        """
        try:
            # 备份现有数据（只保留基础字段）
            await conn.execute("""
                CREATE TEMPORARY TABLE layer_resources_backup AS 
                SELECT 
                    resource_id,
                    service_name,
                    service_url,
                    service_type,
                    layer_name,
                    layer_title,
                    layer_abstract,
                    created_at,
                    updated_at
                FROM layer_resources;
            """)
            
            # 删除旧表
            await conn.execute("DROP TABLE layer_resources;")
            
            # 创建新的基础元数据表（移除BOTH类型支持）
            await conn.execute("""
                CREATE TABLE layer_resources (
                    resource_id TEXT PRIMARY KEY,
                    service_name TEXT NOT NULL,
                    service_url TEXT NOT NULL,
                    service_type TEXT NOT NULL CHECK (service_type IN ('WMS', 'WFS')),
                    layer_name TEXT NOT NULL,
                    layer_title TEXT,
                    layer_abstract TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(service_url, layer_name, service_type)
                );
            """)
            
            # 恢复数据
            await conn.execute("""
                INSERT INTO layer_resources 
                SELECT * FROM layer_resources_backup;
            """)
            
            # 删除临时表
            await conn.execute("DROP TABLE layer_resources_backup;")
            
            logger.info("表结构迁移完成，已移除BOTH类型支持")
            
        except Exception as e:
            logger.error(f"表结构迁移失败: {e}")
            raise
    
    async def execute_query(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        """执行查询语句
        
        Args:
            sql: SQL查询语句
            params: 查询参数
            
        Returns:
            查询结果游标
        """
        conn = await self.connect()
        return await conn.execute(sql, params)
    
    async def execute_many(self, sql: str, params_list: list) -> None:
        """批量执行SQL语句
        
        Args:
            sql: SQL语句
            params_list: 参数列表
        """
        conn = await self.connect()
        await conn.executemany(sql, params_list)
        await conn.commit()
    
    async def fetch_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """查询单条记录
        
        Args:
            sql: SQL查询语句
            params: 查询参数
            
        Returns:
            查询结果字典，如果没有结果则返回None
        """
        cursor = await self.execute_query(sql, params)
        row = await cursor.fetchone()
        
        if row:
            # 获取列名
            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, row))
        
        return None
    
    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        """查询多条记录
        
        Args:
            sql: SQL查询语句
            params: 查询参数
            
        Returns:
            查询结果字典列表
        """
        cursor = await self.execute_query(sql, params)
        rows = await cursor.fetchall()
        
        if rows:
            # 获取列名
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        
        return []
    
    async def execute_update(self, sql: str, params: tuple = ()) -> int:
        """执行更新语句
        
        Args:
            sql: SQL更新语句
            params: 更新参数
            
        Returns:
            受影响的行数
        """
        conn = await self.connect()
        cursor = await conn.execute(sql, params)
        await conn.commit()
        return cursor.rowcount


# 全局数据库管理器实例
db_manager = DatabaseManager()


async def get_db_manager() -> DatabaseManager:
    """获取数据库管理器实例
    
    用于依赖注入
    
    Returns:
        数据库管理器实例
    """
    return db_manager


async def init_database():
    """初始化数据库
    
    在应用启动时调用
    """
    await db_manager.initialize_database()


async def close_database():
    """关闭数据库连接
    
    在应用关闭时调用
    """
    await db_manager.close()