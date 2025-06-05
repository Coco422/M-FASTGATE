"""
API Key 管理服务
"""

import json
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from ..models.api_key import (
    APIKeyDB, APIKeyCreate, APIKeyUpdate, APIKeyResponse,
    generate_api_key, calculate_expires_at
)


class KeyManager:
    """API Key 管理服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_key(self, key_data: APIKeyCreate) -> APIKeyResponse:
        """
        创建 API Key
        
        Args:
            key_data: API Key 创建数据
        
        Returns:
            APIKeyResponse: 创建的 API Key
        """
        # 生成 Key ID 和 Value
        key_id, key_value = generate_api_key()
        
        # 计算过期时间
        expires_at = None
        if key_data.expires_days:
            expires_at = calculate_expires_at(key_data.expires_days)
        
        # 创建数据库记录
        db_key = APIKeyDB(
            key_id=key_id,
            key_value=key_value,
            source_path=key_data.source_path,
            permissions=json.dumps(key_data.permissions),
            expires_at=expires_at,
            rate_limit=key_data.rate_limit
        )
        
        self.db.add(db_key)
        self.db.commit()
        self.db.refresh(db_key)
        
        return self._to_response(db_key)
    
    def get_key(self, key_id: str) -> Optional[APIKeyResponse]:
        """
        获取单个 API Key
        
        Args:
            key_id: API Key ID
        
        Returns:
            APIKeyResponse: API Key 信息，不存在则返回 None
        """
        db_key = self.db.query(APIKeyDB).filter(APIKeyDB.key_id == key_id).first()
        if db_key:
            return self._to_response(db_key)
        return None
    
    def get_key_by_value(self, key_value: str) -> Optional[APIKeyResponse]:
        """
        根据 Key Value 获取 API Key
        
        Args:
            key_value: API Key Value
        
        Returns:
            APIKeyResponse: API Key 信息，不存在则返回 None
        """
        db_key = self.db.query(APIKeyDB).filter(APIKeyDB.key_value == key_value).first()
        if db_key:
            return self._to_response(db_key)
        return None
    
    def get_keys(self, source_path: str = None, is_active: bool = None) -> List[APIKeyResponse]:
        """
        获取 API Key 列表
        
        Args:
            source_path: 过滤来源路径
            is_active: 过滤激活状态
        
        Returns:
            List[APIKeyResponse]: API Key 列表
        """
        query = self.db.query(APIKeyDB)
        
        if source_path:
            query = query.filter(APIKeyDB.source_path == source_path)
        
        if is_active is not None:
            query = query.filter(APIKeyDB.is_active == is_active)
        
        db_keys = query.order_by(APIKeyDB.created_at.desc()).all()
        return [self._to_response(db_key) for db_key in db_keys]
    
    def update_key(self, key_id: str, key_data: APIKeyUpdate) -> Optional[APIKeyResponse]:
        """
        更新 API Key
        
        Args:
            key_id: API Key ID
            key_data: 更新数据
        
        Returns:
            APIKeyResponse: 更新后的 API Key，不存在则返回 None
        """
        db_key = self.db.query(APIKeyDB).filter(APIKeyDB.key_id == key_id).first()
        if not db_key:
            return None
        
        # 更新字段
        if key_data.source_path is not None:
            db_key.source_path = key_data.source_path
        
        if key_data.permissions is not None:
            db_key.permissions = json.dumps(key_data.permissions)
        
        if key_data.expires_at is not None:
            db_key.expires_at = key_data.expires_at
        
        if key_data.is_active is not None:
            db_key.is_active = key_data.is_active
        
        if key_data.rate_limit is not None:
            db_key.rate_limit = key_data.rate_limit
        
        self.db.commit()
        self.db.refresh(db_key)
        
        return self._to_response(db_key)
    
    def delete_key(self, key_id: str) -> bool:
        """
        删除 API Key
        
        Args:
            key_id: API Key ID
        
        Returns:
            bool: 删除成功返回 True，不存在返回 False
        """
        db_key = self.db.query(APIKeyDB).filter(APIKeyDB.key_id == key_id).first()
        if not db_key:
            return False
        
        self.db.delete(db_key)
        self.db.commit()
        return True
    
    def validate_key(self, key_value: str) -> Optional[APIKeyResponse]:
        """
        验证 API Key 是否有效
        
        Args:
            key_value: API Key Value
            
        Returns:
            APIKeyResponse: 有效的 API Key 信息，无效则返回 None
        """
        db_key = self.db.query(APIKeyDB).filter(
            and_(
                APIKeyDB.key_value == key_value,
                APIKeyDB.is_active == True
            )
        ).first()
        
        if not db_key:
            return None
        
        # 检查是否过期
        if db_key.expires_at and db_key.expires_at < datetime.utcnow():
            return None
        
        return self._to_response(db_key)
    
    def update_usage(self, key_value: str) -> bool:
        """
        更新 API Key 使用统计
        
        Args:
            key_value: API Key Value
        
        Returns:
            bool: 更新成功返回 True
        """
        db_key = self.db.query(APIKeyDB).filter(APIKeyDB.key_value == key_value).first()
        if not db_key:
            return False
        
        db_key.usage_count += 1
        db_key.last_used_at = datetime.utcnow()
        
        self.db.commit()
        return True
    
    def _to_response(self, db_key: APIKeyDB) -> APIKeyResponse:
        """
        转换数据库模型到响应模型
        
        Args:
            db_key: 数据库模型
        
        Returns:
            APIKeyResponse: 响应模型
        """
        permissions = []
        try:
            permissions = json.loads(db_key.permissions)
        except:
            permissions = []
        
        return APIKeyResponse(
            key_id=db_key.key_id,
            key_value=db_key.key_value,
            source_path=db_key.source_path,
            permissions=permissions,
            created_at=db_key.created_at,
            expires_at=db_key.expires_at,
            is_active=db_key.is_active,
            usage_count=db_key.usage_count,
            rate_limit=db_key.rate_limit,
            last_used_at=db_key.last_used_at
        )

    def list_keys(
        self, 
        skip: int = 0, 
        limit: int = 100, 
        source_path: Optional[str] = None, 
        is_active: Optional[bool] = None
    ) -> List[APIKeyResponse]:
        """
        获取 API Key 列表（分页和过滤）
        
        Args:
            skip: 跳过的记录数
            limit: 返回的记录数
            source_path: 按来源路径过滤
            is_active: 按活跃状态过滤
        
        Returns:
            List[APIKeyResponse]: API Key 列表
        """
        query = self.db.query(APIKeyDB)
        
        # 应用过滤条件
        if source_path:
            query = query.filter(APIKeyDB.source_path == source_path)
        if is_active is not None:
            query = query.filter(APIKeyDB.is_active == is_active)
        
        # 分页和排序
        keys = query.order_by(APIKeyDB.created_at.desc()).offset(skip).limit(limit).all()
        
        return [self._to_response(key) for key in keys]

    def get_keys(
        self, 
        source_path: Optional[str] = None, 
        is_active: Optional[bool] = None
    ) -> List[APIKeyResponse]:
        """
        获取 API Key 列表（兼容原有方法）
        
        Args:
            source_path: 按来源路径过滤
            is_active: 按活跃状态过滤
        
        Returns:
            List[APIKeyResponse]: API Key 列表
        """
        return self.list_keys(source_path=source_path, is_active=is_active) 