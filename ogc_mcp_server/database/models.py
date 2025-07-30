"""
OGC MCP服务器数据模型

定义图层资源的基础元数据结构和验证规则
只保存基础元数据，动态参数通过资源模板实时获取
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class LayerResource(BaseModel):
    """图层资源基础元数据模型
    
    只保存基础元数据信息，不包含动态参数（如crs、bbox等）
    动态参数通过资源模板实时从OGC服务获取
    """
    resource_id: str = Field(..., description="唯一标识符")
    service_name: str = Field(..., description="服务名称")
    service_url: str = Field(..., description="服务URL")
    service_type: str = Field(..., description="服务类型(WMS/WFS/WMTS)")
    layer_name: str = Field(..., description="图层名称")
    layer_title: Optional[str] = Field(None, description="图层标题")
    layer_abstract: Optional[str] = Field(None, description="图层描述")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    @field_validator('service_type')
    @classmethod
    def validate_service_type(cls, v):
        """验证服务类型"""
        allowed_types = ['WMS', 'WFS', 'WMTS']
        if v.upper() not in allowed_types:
            raise ValueError(f'服务类型必须是 {allowed_types} 之一')
        return v.upper()

    @field_validator('service_url')
    @classmethod
    def validate_service_url(cls, v):
        """验证服务URL"""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('服务URL必须以http://或https://开头')
        return v

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于数据库存储"""
        return {
            "resource_id": self.resource_id,
            "service_name": self.service_name,
            "service_url": self.service_url,
            "service_type": self.service_type,
            "layer_name": self.layer_name,
            "layer_title": self.layer_title,
            "layer_abstract": self.layer_abstract,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LayerResource":
        """从字典创建图层资源对象"""
        # 处理时间字段
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if isinstance(data.get('updated_at'), str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
            
        return cls(**data)


class LayerResourceCreate(BaseModel):
    """创建图层资源的数据模型
    
    只包含基础元数据字段，不包含动态参数
    """
    service_name: str = Field(..., description="服务名称")
    service_url: str = Field(..., description="服务URL")
    service_type: str = Field(..., description="服务类型(WMS/WFS/WMTS)")
    layer_name: str = Field(..., description="图层名称")
    layer_title: Optional[str] = Field(None, description="图层标题")
    layer_abstract: Optional[str] = Field(None, description="图层描述")

    @field_validator('service_type')
    @classmethod
    def validate_service_type(cls, v):
        """验证服务类型"""
        allowed_types = ['WMS', 'WFS', 'WMTS']
        if v.upper() not in allowed_types:
            raise ValueError(f'服务类型必须是 {allowed_types} 之一')
        return v.upper()

    @field_validator('service_url')
    @classmethod
    def validate_service_url(cls, v):
        """验证服务URL"""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('服务URL必须以http://或https://开头')
        return v


class LayerResourceUpdate(BaseModel):
    """更新图层资源的数据模型
    
    只包含基础元数据字段，不包含动态参数
    """
    service_name: Optional[str] = Field(None, description="服务名称")
    service_url: Optional[str] = Field(None, description="服务URL")
    service_type: Optional[str] = Field(None, description="服务类型(WMS/WFS/WMTS)")
    layer_name: Optional[str] = Field(None, description="图层名称")
    layer_title: Optional[str] = Field(None, description="图层标题")
    layer_abstract: Optional[str] = Field(None, description="图层描述")

    @field_validator('service_type')
    @classmethod
    def validate_service_type(cls, v):
        """验证服务类型"""
        if v is not None:
            allowed_types = ['WMS', 'WFS', 'WMTS']
            if v.upper() not in allowed_types:
                raise ValueError(f'服务类型必须是 {allowed_types} 之一')
            return v.upper()
        return v

    @field_validator('service_url')
    @classmethod
    def validate_service_url(cls, v):
        """验证服务URL"""
        if v is not None and not v.startswith(('http://', 'https://')):
            raise ValueError('服务URL必须以http://或https://开头')
        return v


class LayerResourceQuery(BaseModel):
    """查询图层资源的参数模型"""
    service_type: Optional[str] = Field(None, description="按服务类型筛选")
    service_name: Optional[str] = Field(None, description="按服务名称筛选")
    layer_name: Optional[str] = Field(None, description="按图层名称筛选")
    # 修复：增加limit的最大值到10000，以支持大量图层
    limit: int = Field(default=100, ge=1, le=10000, description="返回结果数量限制")
    offset: int = Field(default=0, ge=0, description="结果偏移量")