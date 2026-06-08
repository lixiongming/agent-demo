"""长期记忆 - PGVector"""
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.db import get_async_session
from app.config import get_settings
from app.core.logger import get_logger
import json

logger = get_logger(__name__)
settings = get_settings()


class LongTermMemory:
    """长期记忆
    
    使用PostgreSQL + PGVector存储长期记忆，支持向量检索
    """
    
    def __init__(self, session_id: str, db: AsyncSession):
        self.session_id = session_id
        self.db = db
        self.limit = settings.MEMORY_LONG_TERM_LIMIT
    
    async def add_memory(
        self,
        content: str,
        metadata: Optional[dict] = None,
        embedding: Optional[List[float]] = None
    ):
        """添加长期记忆"""
        try:
            # 存储到数据库
            query = text("""
                INSERT INTO long_term_memory 
                (session_id, content, metadata, embedding, created_at)
                VALUES (:session_id, :content, :metadata, :embedding, NOW())
            """)
            
            await self.db.execute(
                query,
                {
                    "session_id": self.session_id,
                    "content": content,
                    "metadata": json.dumps(metadata or {}),
                    "embedding": embedding
                }
            )
            await self.db.commit()
            
            logger.debug(f"Long-term memory added: {content[:50]}")
        
        except Exception as e:
            logger.error(f"Failed to add long-term memory: {e}")
            await self.db.rollback()
    
    async def search_similar(
        self,
        query_embedding: List[float],
        limit: int = 10,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """向量相似度搜索"""
        try:
            query = text("""
                SELECT content, metadata, created_at,
                       1 - (embedding <=> :query_embedding) as similarity
                FROM long_term_memory
                WHERE session_id = :session_id
                AND 1 - (embedding <=> :query_embedding) > :threshold
                ORDER BY similarity DESC
                LIMIT :limit
            """)
            
            result = await self.db.execute(
                query,
                {
                    "session_id": self.session_id,
                    "query_embedding": query_embedding,
                    "threshold": threshold,
                    "limit": limit
                }
            )
            
            memories = []
            for row in result:
                memories.append({
                    "content": row.content,
                    "metadata": json.loads(row.metadata) if row.metadata else {},
                    "created_at": row.created_at,
                    "similarity": row.similarity
                })
            
            return memories
        
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []
    
    async def search_by_keyword(
        self,
        keyword: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """关键词搜索"""
        try:
            query = text("""
                SELECT content, metadata, created_at
                FROM long_term_memory
                WHERE session_id = :session_id
                AND content ILIKE :keyword
                ORDER BY created_at DESC
                LIMIT :limit
            """)
            
            result = await self.db.execute(
                query,
                {
                    "session_id": self.session_id,
                    "keyword": f"%{keyword}%",
                    "limit": limit
                }
            )
            
            memories = []
            for row in result:
                memories.append({
                    "content": row.content,
                    "metadata": json.loads(row.metadata) if row.metadata else {},
                    "created_at": row.created_at
                })
            
            return memories
        
        except Exception as e:
            logger.error(f"Keyword search error: {e}")
            return []
    
    async def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近记忆"""
        try:
            query = text("""
                SELECT content, metadata, created_at
                FROM long_term_memory
                WHERE session_id = :session_id
                ORDER BY created_at DESC
                LIMIT :limit
            """)
            
            result = await self.db.execute(
                query,
                {"session_id": self.session_id, "limit": limit}
            )
            
            memories = []
            for row in result:
                memories.append({
                    "content": row.content,
                    "metadata": json.loads(row.metadata) if row.metadata else {},
                    "created_at": row.created_at
                })
            
            return memories
        
        except Exception as e:
            logger.error(f"Get recent error: {e}")
            return []
    
    async def clear(self):
        """清空长期记忆"""
        try:
            query = text("""
                DELETE FROM long_term_memory
                WHERE session_id = :session_id
            """)
            
            await self.db.execute(query, {"session_id": self.session_id})
            await self.db.commit()
            
            logger.info(f"Long-term memory cleared: {self.session_id}")
        
        except Exception as e:
            logger.error(f"Clear error: {e}")
            await self.db.rollback()
    
    async def get_stats(self) -> dict:
        """获取统计"""
        try:
            query = text("""
                SELECT COUNT(*) as count
                FROM long_term_memory
                WHERE session_id = :session_id
            """)
            
            result = await self.db.execute(
                query, {"session_id": self.session_id}
            )
            count = result.scalar()
            
            return {
                "session_id": self.session_id,
                "memory_count": count,
                "limit": self.limit
            }
        
        except Exception as e:
            logger.error(f"Stats error: {e}")
            return {"session_id": self.session_id, "memory_count": 0}