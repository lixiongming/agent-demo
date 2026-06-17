"""数据库迁移脚本 - 添加记忆管理字段

执行方式：
    docker-compose exec api python -m app.db.migrations.add_memory_fields

新增字段：
    - weight: 记忆权重（用于遗忘机制）
    - importance: 记忆重要性（用于淘汰策略）
    - confidence: 记忆置信度（用于冲突修正）
    - last_accessed: 最后访问时间
    - access_count: 访问次数
    - version: 记忆版本（用于冲突追踪）
    - updated_at: 更新时间
"""

from sqlalchemy import text
from app.db.database import get_async_session
from app.core.logger import get_logger
import asyncio

logger = get_logger(__name__)


async def add_memory_fields():
    """添加记忆管理字段"""
    
    async for session in get_async_session():
        try:
            logger.info("开始添加记忆管理字段...")
            
            # 1. 添加 weight 字段（记忆权重）
            await session.execute(text("""
                ALTER TABLE long_term_memory
                ADD COLUMN IF NOT EXISTS weight FLOAT DEFAULT 1.0
            """))
            logger.info("添加 weight 字段完成")
            
            # 2. 添加 importance 字段（记忆重要性）
            await session.execute(text("""
                ALTER TABLE long_term_memory
                ADD COLUMN IF NOT EXISTS importance FLOAT DEFAULT 1.0
            """))
            logger.info("添加 importance 字段完成")
            
            # 3. 添加 confidence 字段（记忆置信度）
            await session.execute(text("""
                ALTER TABLE long_term_memory
                ADD COLUMN IF NOT EXISTS confidence FLOAT DEFAULT 0.5
            """))
            logger.info("添加 confidence 字段完成")
            
            # 4. 添加 last_accessed 字段（最后访问时间）
            await session.execute(text("""
                ALTER TABLE long_term_memory
                ADD COLUMN IF NOT EXISTS last_accessed TIMESTAMP
            """))
            logger.info("添加 last_accessed 字段完成")
            
            # 5. 添加 access_count 字段（访问次数）
            await session.execute(text("""
                ALTER TABLE long_term_memory
                ADD COLUMN IF NOT EXISTS access_count INTEGER DEFAULT 0
            """))
            logger.info("添加 access_count 字段完成")
            
            # 6. 添加 version 字段（记忆版本）
            await session.execute(text("""
                ALTER TABLE long_term_memory
                ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1
            """))
            logger.info("添加 version 字段完成")
            
            # 7. 添加 updated_at 字段（更新时间）
            await session.execute(text("""
                ALTER TABLE long_term_memory
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP
            """))
            logger.info("添加 updated_at 字段完成")
            
            # 8. 创建索引（提高查询性能）
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_memory_weight
                ON long_term_memory(weight)
            """))
            logger.info("创建 weight 索引完成")
            
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_memory_importance
                ON long_term_memory(importance)
            """))
            logger.info("创建 importance 索引完成")
            
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_memory_score
                ON long_term_memory((weight * importance))
            """))
            logger.info("创建 score 索引完成")
            
            # 提交更改
            await session.commit()
            
            logger.info("✅ 所有字段添加完成")
            
            # 验证字段
            result = await session.execute(text("""
                SELECT column_name, data_type, column_default
                FROM information_schema.columns
                WHERE table_name = 'long_term_memory'
                AND column_name IN (
                    'weight', 'importance', 'confidence',
                    'last_accessed', 'access_count', 'version', 'updated_at'
                )
            """))
            
            columns = result.fetchall()
            logger.info("字段验证:")
            for col in columns:
                logger.info(f"  - {col.column_name}: {col.data_type} (default: {col.column_default})")
            
            return True
        
        except Exception as e:
            logger.error(f"字段添加失败: {e}")
            await session.rollback()
            return False


async def main():
    """主函数"""
    success = await add_memory_fields()
    
    if success:
        logger.info("迁移成功完成")
    else:
        logger.error("迁移失败")


if __name__ == "__main__":
    asyncio.run(main())