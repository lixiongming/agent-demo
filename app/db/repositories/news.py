"""新闻仓库

功能：
- 新闻查询
- 新闻搜索
- 新闻统计
- 热门新闻
- 作者新闻
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.sql import text
from app.db.models.news import News
from app.core.logger import get_logger
from datetime import datetime, timedelta

logger = get_logger(__name__)


class NewsRepository:
    """新闻数据访问
    
    功能：
    - 基础查询（ID、列表、分页）
    - 搜索查询（关键词、标题、内容）
    - 统计查询（总数、浏览量）
    - 热门新闻（浏览量排序）
    - 作者新闻（按作者查询）
    - 时间范围查询（最近、本周、本月）
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ============================================
    # 基础查询
    # ============================================
    
    async def get_by_id(self, news_id: int) -> Optional[News]:
        """根据ID获取新闻
        
        Args:
            news_id: 新闻ID
            
        Returns:
            新闻对象
        """
        result = await self.db.execute(
            select(News).where(News.id == news_id)
        )
        return result.scalar_one_or_none()
    
    async def get_list(
        self,
        limit: int = 20,
        offset: int = 0,
        order_by: str = "created_at"
    ) -> List[News]:
        """获取新闻列表
        
        Args:
            limit: 返回数量
            offset: 偏移量
            order_by: 排序字段（created_at, views）
            
        Returns:
            新闻列表
        """
        # 构建排序
        if order_by == "views":
            order_field = News.views.desc()
        else:
            order_field = News.created_at.desc()
        
        result = await self.db.execute(
            select(News)
            .order_by(order_field)
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_recent(self, limit: int = 10) -> List[News]:
        """获取最近新闻
        
        Args:
            limit: 返回数量
            
        Returns:
            新闻列表
        """
        result = await self.db.execute(
            select(News)
            .order_by(News.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    # ============================================
    # 搜索查询
    # ============================================
    
    async def search(
        self,
        keyword: str,
        limit: int = 10,
        search_type: str = "all"
    ) -> List[News]:
        """搜索新闻
        
        Args:
            keyword: 搜索关键词
            limit: 返回数量
            search_type: 搜索类型（all, title, content, author）
            
        Returns:
            新闻列表
        """
        # 构建搜索条件
        if search_type == "title":
            condition = News.title.ilike(f"%{keyword}%")
        elif search_type == "content":
            condition = News.content.ilike(f"%{keyword}%")
        elif search_type == "author":
            condition = News.author.ilike(f"%{keyword}%")
        else:
            # 搜索所有字段
            condition = or_(
                News.title.ilike(f"%{keyword}%"),
                News.description.ilike(f"%{keyword}%"),
                News.content.ilike(f"%{keyword}%"),
                News.author.ilike(f"%{keyword}%")
            )
        
        result = await self.db.execute(
            select(News)
            .where(condition)
            .order_by(News.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def search_by_title(self, title: str, limit: int = 10) -> List[News]:
        """按标题搜索
        
        Args:
            title: 标题关键词
            limit: 返回数量
            
        Returns:
            新闻列表
        """
        return await self.search(title, limit, search_type="title")
    
    async def search_by_author(self, author: str, limit: int = 10) -> List[News]:
        """按作者搜索
        
        Args:
            author: 作者名称
            limit: 返回数量
            
        Returns:
            新闻列表
        """
        return await self.search(author, limit, search_type="author")
    
    # ============================================
    # 统计查询
    # ============================================
    
    async def count_all(self) -> int:
        """统计新闻总数
        
        Returns:
            新闻总数
        """
        result = await self.db.execute(
            select(func.count(News.id))
        )
        return result.scalar()
    
    async def count_by_author(self, author: str) -> int:
        """统计作者新闻数
        
        Args:
            author: 作者名称
            
        Returns:
            新闻数量
        """
        result = await self.db.execute(
            select(func.count(News.id))
            .where(News.author == author)
        )
        return result.scalar()
    
    async def get_total_views(self) -> int:
        """获取总浏览量
        
        Returns:
            总浏览量
        """
        result = await self.db.execute(
            select(func.sum(News.views))
        )
        return result.scalar() or 0
    
    async def get_avg_views(self) -> float:
        """获取平均浏览量
        
        Returns:
            平均浏览量
        """
        result = await self.db.execute(
            select(func.avg(News.views))
        )
        return result.scalar() or 0.0
    
    # ============================================
    # 热门新闻
    # ============================================
    
    async def get_hot_news(self, limit: int = 10) -> List[News]:
        """获取热门新闻（按浏览量排序）
        
        Args:
            limit: 返回数量
            
        Returns:
            新闻列表
        """
        result = await self.db.execute(
            select(News)
            .order_by(News.views.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_hot_news_by_time(
        self,
        days: int = 7,
        limit: int = 10
    ) -> List[News]:
        """获取指定时间范围内的热门新闻
        
        Args:
            days: 时间范围（天数）
            limit: 返回数量
            
        Returns:
            新闻列表
        """
        # 计算时间范围
        start_time = datetime.now() - timedelta(days=days)
        
        result = await self.db.execute(
            select(News)
            .where(News.created_at >= start_time)
            .order_by(News.views.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    # ============================================
    # 时间范围查询
    # ============================================
    
    async def get_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: int = 20
    ) -> List[News]:
        """获取时间范围内的新闻
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量
            
        Returns:
            新闻列表
        """
        result = await self.db.execute(
            select(News)
            .where(
                News.created_at >= start_time,
                News.created_at <= end_time
            )
            .order_by(News.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_today_news(self, limit: int = 20) -> List[News]:
        """获取今天的新闻
        
        Args:
            limit: 返回数量
            
        Returns:
            新闻列表
        """
        today = datetime.now().date()
        start_time = datetime.combine(today, datetime.min.time())
        end_time = datetime.combine(today, datetime.max.time())
        
        return await self.get_by_time_range(start_time, end_time, limit)
    
    async def get_this_week_news(self, limit: int = 20) -> List[News]:
        """获取本周新闻
        
        Args:
            limit: 返回数量
            
        Returns:
            新闻列表
        """
        start_time = datetime.now() - timedelta(days=7)
        end_time = datetime.now()
        
        return await self.get_by_time_range(start_time, end_time, limit)
    
    async def get_this_month_news(self, limit: int = 20) -> List[News]:
        """获取本月新闻
        
        Args:
            limit: 返回数量
            
        Returns:
            新闻列表
        """
        start_time = datetime.now() - timedelta(days=30)
        end_time = datetime.now()
        
        return await self.get_by_time_range(start_time, end_time, limit)
    
    # ============================================
    # 作者相关
    # ============================================
    
    async def get_by_author(self, author: str, limit: int = 10) -> List[News]:
        """获取作者的新闻
        
        Args:
            author: 作者名称
            limit: 返回数量
            
        Returns:
            新闻列表
        """
        result = await self.db.execute(
            select(News)
            .where(News.author == author)
            .order_by(News.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_all_authors(self, limit: int = 20) -> List[str]:
        """获取所有作者
        
        Args:
            limit: 返回数量
            
        Returns:
            作者列表
        """
        result = await self.db.execute(
            select(News.author)
            .distinct()
            .where(News.author.isnot(None))
            .limit(limit)
        )
        return [row[0] for row in result.all()]
    
    # ============================================
    # 统计信息
    # ============================================
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取新闻统计信息
        
        Returns:
            统计信息字典
        """
        total_count = await self.count_all()
        total_views = await self.get_total_views()
        avg_views = await self.get_avg_views()
        
        return {
            "total_count": total_count,
            "total_views": total_views,
            "avg_views": round(avg_views, 2),
            "authors_count": len(await self.get_all_authors())
        }