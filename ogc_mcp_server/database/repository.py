"""
图层资源数据访问层

提供图层资源的CRUD操作接口
"""

import uuid
from datetime import datetime
from typing import List, Optional
import logging

from .models import LayerResource, LayerResourceCreate, LayerResourceUpdate, LayerResourceQuery
from .connection import DatabaseManager, get_db_manager

logger = logging.getLogger(__name__)


class LayerResourceRepository:
    """图层资源数据访问层
    
    提供图层资源的增删改查操作
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """初始化仓储
        
        Args:
            db_manager: 数据库管理器
        """
        self.db_manager = db_manager
    
    async def create(self, layer_data: LayerResourceCreate) -> LayerResource:
        """创建新的图层资源
        
        Args:
            layer_data: 图层资源创建数据
            
        Returns:
            创建的图层资源对象
            
        Raises:
            ValueError: 当图层资源已存在时
        """
        # 生成唯一ID
        resource_id = str(uuid.uuid4())
        
        # 检查是否已存在相同的图层（包含服务类型）
        existing = await self.get_by_service_layer_and_type(
            layer_data.service_url, 
            layer_data.layer_name,
            layer_data.service_type
        )
        if existing:
            raise ValueError(f"图层资源已存在: {layer_data.service_url} - {layer_data.layer_name} ({layer_data.service_type})")
        
        # 创建图层资源对象（只包含基础元数据）
        now = datetime.now()
        layer_resource = LayerResource(
            resource_id=resource_id,
            service_name=layer_data.service_name,
            service_url=layer_data.service_url,
            service_type=layer_data.service_type,
            layer_name=layer_data.layer_name,
            layer_title=layer_data.layer_title,
            layer_abstract=layer_data.layer_abstract,
            created_at=now,
            updated_at=now
        )
        
        # 插入数据库（只包含基础元数据字段）
        insert_sql = """
        INSERT INTO layer_resources (
            resource_id, service_name, service_url, service_type,
            layer_name, layer_title, layer_abstract,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        data_dict = layer_resource.to_dict()
        params = (
            data_dict['resource_id'],
            data_dict['service_name'],
            data_dict['service_url'],
            data_dict['service_type'],
            data_dict['layer_name'],
            data_dict['layer_title'],
            data_dict['layer_abstract'],
            data_dict['created_at'],
            data_dict['updated_at']
        )
        
        try:
            await self.db_manager.execute_update(insert_sql, params)
            logger.info(f"图层资源创建成功: {resource_id}")
            return layer_resource
        except Exception as e:
            logger.error(f"创建图层资源失败: {e}")
            raise
    
    async def get_by_id(self, resource_id: str) -> Optional[LayerResource]:
        """根据ID获取图层资源
        
        Args:
            resource_id: 资源ID
            
        Returns:
            图层资源对象，如果不存在则返回None
        """
        sql = "SELECT * FROM layer_resources WHERE resource_id = ?"
        result = await self.db_manager.fetch_one(sql, (resource_id,))
        
        if result:
            return LayerResource.from_dict(result)
        return None
    
    async def get_by_service_and_layer(self, service_url: str, layer_name: str) -> Optional[LayerResource]:
        """根据服务URL和图层名称获取图层资源
        
        Args:
            service_url: 服务URL
            layer_name: 图层名称
            
        Returns:
            图层资源对象，如果不存在则返回None
        """
        sql = "SELECT * FROM layer_resources WHERE service_url = ? AND layer_name = ?"
        result = await self.db_manager.fetch_one(sql, (service_url, layer_name))
        
        if result:
            return LayerResource.from_dict(result)
        return None
    
    async def get_by_service_layer_and_type(self, service_url: str, layer_name: str, service_type: str) -> Optional[LayerResource]:
        """根据服务URL、图层名称和服务类型获取图层资源
        
        Args:
            service_url: 服务URL
            layer_name: 图层名称
            service_type: 服务类型（WMS/WFS）
            
        Returns:
            图层资源对象，如果不存在则返回None
        """
        sql = "SELECT * FROM layer_resources WHERE service_url = ? AND layer_name = ? AND service_type = ?"
        result = await self.db_manager.fetch_one(sql, (service_url, layer_name, service_type))
        
        if result:
            return LayerResource.from_dict(result)
        return None
    
    async def get_layers_by_service_url(self, service_url: str) -> List[LayerResource]:
        """根据服务URL获取所有图层资源
        
        Args:
            service_url: 服务URL
            
        Returns:
            图层资源列表
        """
        sql = "SELECT * FROM layer_resources WHERE service_url = ?"
        results = await self.db_manager.fetch_all(sql, (service_url,))
        return [LayerResource.from_dict(result) for result in results]
    
    async def delete_by_service_url_and_type(self, service_url: str, service_type: str) -> int:
        """删除指定服务URL和类型的所有图层资源
        
        Args:
            service_url: 服务URL
            service_type: 服务类型
            
        Returns:
            删除的记录数量
        """
        sql = "DELETE FROM layer_resources WHERE service_url = ? AND service_type = ?"
        
        try:
            affected_rows = await self.db_manager.execute_update(sql, (service_url, service_type))
            logger.info(f"删除服务图层资源: {service_url} ({service_type}), 删除 {affected_rows} 条记录")
            return affected_rows
        except Exception as e:
            logger.error(f"删除服务图层资源失败: {e}")
            raise
    
    async def list_resources(self, query: LayerResourceQuery) -> List[LayerResource]:
        """查询图层资源列表
        
        Args:
            query: 查询参数
            
        Returns:
            图层资源列表
        """
        # 构建查询条件
        where_conditions = []
        params = []
        
        if query.service_type:
            where_conditions.append("service_type = ?")
            params.append(query.service_type)
        
        if query.service_name:
            where_conditions.append("service_name LIKE ?")
            params.append(f"%{query.service_name}%")
        
        if query.layer_name:
            where_conditions.append("layer_name LIKE ?")
            params.append(f"%{query.layer_name}%")
        
        # 构建SQL语句
        sql = "SELECT * FROM layer_resources"
        if where_conditions:
            sql += " WHERE " + " AND ".join(where_conditions)
        
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([query.limit, query.offset])
        
        results = await self.db_manager.fetch_all(sql, tuple(params))
        return [LayerResource.from_dict(result) for result in results]
    
    async def update(self, resource_id: str, update_data: LayerResourceUpdate) -> Optional[LayerResource]:
        """更新图层资源
        
        Args:
            resource_id: 资源ID
            update_data: 更新数据
            
        Returns:
            更新后的图层资源对象，如果资源不存在则返回None
        """
        # 检查资源是否存在
        existing = await self.get_by_id(resource_id)
        if not existing:
            return None
        
        # 构建更新字段（只包含基础元数据字段）
        update_fields = []
        params = []
        
        for field, value in update_data.dict(exclude_unset=True).items():
            # 跳过动态参数字段
            if field in ['crs', 'bbox']:
                continue
            update_fields.append(f"{field} = ?")
            params.append(value)
        
        if not update_fields:
            return existing
        
        # 添加更新时间
        update_fields.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        
        # 添加WHERE条件
        params.append(resource_id)
        
        sql = f"UPDATE layer_resources SET {', '.join(update_fields)} WHERE resource_id = ?"
        
        try:
            await self.db_manager.execute_update(sql, tuple(params))
            logger.info(f"图层资源更新成功: {resource_id}")
            return await self.get_by_id(resource_id)
        except Exception as e:
            logger.error(f"更新图层资源失败: {e}")
            raise
    
    async def delete(self, resource_id: str) -> bool:
        """删除图层资源
        
        Args:
            resource_id: 资源ID
            
        Returns:
            删除成功返回True，资源不存在返回False
        """
        sql = "DELETE FROM layer_resources WHERE resource_id = ?"
        
        try:
            affected_rows = await self.db_manager.execute_update(sql, (resource_id,))
            if affected_rows > 0:
                logger.info(f"图层资源删除成功: {resource_id}")
                return True
            else:
                logger.warning(f"图层资源不存在: {resource_id}")
                return False
        except Exception as e:
            logger.error(f"删除图层资源失败: {e}")
            raise
    
    async def count(self, query: LayerResourceQuery) -> int:
        """统计图层资源数量
        
        Args:
            query: 查询参数
            
        Returns:
            符合条件的资源数量
        """
        # 构建查询条件
        where_conditions = []
        params = []
        
        if query.service_type:
            where_conditions.append("service_type = ?")
            params.append(query.service_type)
        
        if query.service_name:
            where_conditions.append("service_name LIKE ?")
            params.append(f"%{query.service_name}%")
        
        if query.layer_name:
            where_conditions.append("layer_name LIKE ?")
            params.append(f"%{query.layer_name}%")
        
        # 构建SQL语句
        sql = "SELECT COUNT(*) as count FROM layer_resources"
        if where_conditions:
            sql += " WHERE " + " AND ".join(where_conditions)
        
        result = await self.db_manager.fetch_one(sql, tuple(params))
        return result['count'] if result else 0


async def get_layer_repository() -> LayerResourceRepository:
    """获取图层资源仓储实例
    
    用于依赖注入
    
    Returns:
        图层资源仓储实例
    """
    db_manager = await get_db_manager()
    return LayerResourceRepository(db_manager)