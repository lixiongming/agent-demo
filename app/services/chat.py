"""聊天服务"""
from typing import Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.db import SessionRepository, MessageRepository
from app.agent import get_chat_app, AgentState
from app.llm import get_llm
from app.memory import ShortTermMemory
from app.config import get_settings
from app.core.logger import get_logger
import uuid

logger = get_logger(__name__)
settings = get_settings()


def get_rag_service():
    """获取 RAG 服务（单例模式）
    
    生产标准：
    - 使用容器获取单例
    - 只初始化一次
    - 后续请求直接获取
    """
    from app.core.container import DIContainer
    from app.core.interfaces import IRAGService
    
    # 使用容器获取单例
    return DIContainer.get(IRAGService)


class ChatService:
    """聊天服务 - 增强 RAG 检索"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.session_repo = SessionRepository(db)
        self.message_repo = MessageRepository(db)
    
    async def chat(
        self,
        session_id: str,
        message: str,
        user_id: Optional[int] = None,
        use_rag: bool = True  # 默认启用 RAG
    ) -> dict:
        """聊天（非流式）- 自动检索知识库"""
        # 获取或创建会话
        session = await self.session_repo.get_by_id(session_id)
        if not session:
            session = await self.session_repo.create(
                session_id=session_id,
                agent_type="chat",
                model_name=settings.DEFAULT_MODEL,
                user_id=user_id
            )
        
        # 获取历史消息（对话使用最近 20 条）
        history = await self.message_repo.get_recent(session.id, limit=20)
        
        # 构建消息列表
        messages = []
        if session.system_prompt:
            messages.append(SystemMessage(content=session.system_prompt))
        
        for msg in history:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
        
        # ===== RAG 检索（三级相似度策略） =====
        rag_context = None
        rag_strategy = None  # 记录使用的策略
        best_score = 0.0
        best_source = None
        
        if use_rag:
            try:
                rag_service = get_rag_service()
                rag_result = await rag_service.query(
                    question=message,
                    top_k=5,
                    threshold=0.3  # 使用较低阈值获取更多候选
                )
                
                sources = rag_result.get("sources", [])
                if sources:
                    # 获取最高相似度
                    best_source = sources[0]
                    best_score = best_source.get("score", 0)
                    
                    # ===== 三级相似度策略 =====
                    if best_score >= 0.8:
                        # 【策略1】高相似度：直接返回知识库内容，不调用 LLM（防止幻觉）
                        rag_strategy = "direct_return"
                        logger.info(f"RAG策略: 直接返回（相似度={best_score:.3f}）")
                        
                        # 直接返回知识库内容
                        direct_response = best_source.get("content", "")
                        
                        # 保存用户消息
                        await self.message_repo.create(
                            session_id=session.id,
                            role="user",
                            content=message
                        )
                        
                        # 保存助手消息
                        await self.message_repo.create(
                            session_id=session.id,
                            role="assistant",
                            content=direct_response,
                            model_name="rag_direct"
                        )
                        
                        await self.session_repo.increment_message_count(session_id)
                        
                        return {
                            "session_id": session_id,
                            "response": direct_response,
                            "message_count": session.message_count + 1,
                            "rag_used": True,
                            "rag_strategy": rag_strategy,
                            "rag_score": best_score,
                            "rag_sources_count": 1
                        }
                    
                    elif best_score >= 0.5:
                        # 【策略2】中等相似度：让 LLM 参考知识库内容
                        rag_strategy = "llm_reference"
                        logger.info(f"RAG策略: LLM参考（相似度={best_score:.3f}）")
                        
                        # 构建知识上下文（只使用高相似度的内容）
                        context_parts = []
                        for source in sources:
                            score = source.get("score", 0)
                            if score >= 0.5:  # 只包含相似度 >= 0.5 的内容
                                context_parts.append(f"[相似度:{score:.2f}] {source.get('content', '')}")
                        
                        rag_context = "\n".join(context_parts)
                        
                        # 严格的系统提示（防止幻觉）
                        rag_system_msg = SystemMessage(
                            content=f"""以下是知识库中检索到的相关话术（相似度均>=0.5），请严格遵守以下规则：

{rag_context}

【严格规则 - 防止幻觉】：
1. **必须优先使用知识库中的话术**，不要自己编造内容
2. 如果话术中有【占位符】，请根据用户问题填充具体内容
3. **禁止添加知识库中没有的信息**
4. 如果知识库内容与用户问题不完全匹配，请明确告知用户"我需要更多信息来帮您处理"
5. 回答时请标注参考的知识来源（如：根据知识库第X条）"""
                        )
                        messages.insert(0, rag_system_msg)
                        
                    else:
                        # 【策略3】低相似度：明确告知用户
                        rag_strategy = "no_match"
                        logger.info(f"RAG策略: 无匹配（相似度={best_score:.3f}）")
                        
                        # 明确告知用户知识库中没有相关信息
                        rag_system_msg = SystemMessage(
                            content="""【重要提示】：
知识库中没有找到与用户问题高度匹配的内容（相似度<0.5）。

请遵循以下规则：
1. 明确告知用户："抱歉，知识库中没有找到与您问题直接匹配的答案"
2. 可以提供一般性建议，但要明确说明"这是通用建议，非知识库内容"
3. 建议用户提供更多信息或联系人工客服"""
                        )
                        messages.insert(0, rag_system_msg)
                    
                else:
                    # 完全没有检索结果
                    rag_strategy = "no_result"
                    logger.info("RAG策略: 无检索结果")
                    
                    rag_system_msg = SystemMessage(
                        content="""【重要提示】：
知识库中没有找到任何相关内容。

请告知用户：抱歉，知识库中没有相关信息，建议联系人工客服或提供更多细节"""
                    )
                    messages.insert(0, rag_system_msg)
                    
            except Exception as e:
                logger.warning(f"RAG检索失败（继续执行）: {e}")
                rag_strategy = "error"
        
        # 添加当前消息
        messages.append(HumanMessage(content=message))
        
        # 保存用户消息
        await self.message_repo.create(
            session_id=session.id,
            role="user",
            content=message
        )
        
        # 调用LLM
        llm = get_llm(session.model_name)
        response = await llm.ainvoke(messages)
        
        # 保存助手消息
        await self.message_repo.create(
            session_id=session.id,
            role="assistant",
            content=response.content,
            model_name=session.model_name
        )
        
        # 更新会话统计
        await self.session_repo.increment_message_count(session_id)
        
        return {
            "session_id": session_id,
            "response": response.content,
            "message_count": session.message_count + 1,
            "rag_used": rag_context is not None or rag_strategy == "no_match" or rag_strategy == "no_result",
            "rag_strategy": rag_strategy,
            "rag_score": best_score,
            "rag_sources_count": len([s for s in sources if s.get("score", 0) >= 0.5]) if rag_context else 0
        }
    
    async def chat_stream(
        self,
        session_id: str,
        message: str,
        user_id: Optional[int] = None,
        use_rag: bool = True  # 默认启用 RAG
    ) -> AsyncGenerator[dict, None]:
        """聊天（流式）- 自动检索知识库"""
        # 获取或创建会话
        session = await self.session_repo.get_by_id(session_id)
        if not session:
            session = await self.session_repo.create(
                session_id=session_id,
                agent_type="chat",
                model_name=settings.DEFAULT_MODEL,
                user_id=user_id
            )
        
        # 获取历史
        history = await self.message_repo.get_recent(session.id, limit=20)
        
        # 构建消息
        messages = []
        if session.system_prompt:
            messages.append(SystemMessage(content=session.system_prompt))
        
        for msg in history:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
        
        # ===== RAG 检索（三级相似度策略） =====
        rag_context = None
        rag_strategy = None
        best_score = 0.0
        best_source = None
        
        if use_rag:
            try:
                rag_service = get_rag_service()
                rag_result = await rag_service.query(
                    question=message,
                    top_k=5,
                    threshold=0.3
                )
                
                sources = rag_result.get("sources", [])
                if sources:
                    best_source = sources[0]
                    best_score = best_source.get("score", 0)
                    
                    if best_score >= 0.8:
                        # 【策略1】高相似度：直接返回，不调用 LLM
                        rag_strategy = "direct_return"
                        logger.info(f"RAG策略: 直接返回（相似度={best_score:.3f}）")
                        
                        direct_response = best_source.get("content", "")
                        
                        # 保存用户消息
                        await self.message_repo.create(
                            session_id=session.id,
                            role="user",
                            content=message
                        )
                        
                        # 流式输出直接返回的内容
                        yield {"content": direct_response}
                        
                        # 保存助手消息
                        await self.message_repo.create(
                            session_id=session.id,
                            role="assistant",
                            content=direct_response,
                            model_name="rag_direct"
                        )
                        
                        await self.session_repo.increment_message_count(session_id)
                        
                        yield {"done": True, "rag_used": True, "rag_strategy": rag_strategy, "rag_score": best_score}
                        return  # 直接返回，不继续执行
                    
                    elif best_score >= 0.5:
                        # 【策略2】中等相似度：LLM 参考
                        rag_strategy = "llm_reference"
                        logger.info(f"RAG策略: LLM参考（相似度={best_score:.3f}）")
                        
                        context_parts = []
                        for source in sources:
                            score = source.get("score", 0)
                            if score >= 0.5:
                                context_parts.append(f"[相似度:{score:.2f}] {source.get('content', '')}")
                        
                        rag_context = "\n".join(context_parts)
                        
                        rag_system_msg = SystemMessage(
                            content=f"""以下是知识库中检索到的相关话术（相似度均>=0.5），请严格遵守以下规则：

{rag_context}

【严格规则 - 防止幻觉】：
1. **必须优先使用知识库中的话术**，不要自己编造内容
2. 如果话术中有【占位符】，请根据用户问题填充具体内容
3. **禁止添加知识库中没有的信息**
4. 如果知识库内容与用户问题不完全匹配，请明确告知用户"我需要更多信息来帮您处理"
5. 回答时请标注参考的知识来源"""
                        )
                        messages.insert(0, rag_system_msg)
                        
                    else:
                        # 【策略3】低相似度：明确告知用户
                        rag_strategy = "no_match"
                        logger.info(f"RAG策略: 无匹配（相似度={best_score:.3f}）")
                        
                        rag_system_msg = SystemMessage(
                            content="""【重要提示】：
知识库中没有找到与用户问题高度匹配的内容（相似度<0.5）。

请遵循以下规则：
1. 明确告知用户："抱歉，知识库中没有找到与您问题直接匹配的答案"
2. 可以提供一般性建议，但要明确说明"这是通用建议，非知识库内容"
3. 建议用户提供更多信息或联系人工客服"""
                        )
                        messages.insert(0, rag_system_msg)
                    
                else:
                    rag_strategy = "no_result"
                    logger.info("RAG策略: 无检索结果")
                    
                    rag_system_msg = SystemMessage(
                        content="""【重要提示】：
知识库中没有找到任何相关内容。

请告知用户：抱歉，知识库中没有相关信息，建议联系人工客服或提供更多细节"""
                    )
                    messages.insert(0, rag_system_msg)
                    
            except Exception as e:
                logger.warning(f"RAG检索失败（继续执行）: {e}")
                rag_strategy = "error"
        
        messages.append(HumanMessage(content=message))
        
        # 保存用户消息
        await self.message_repo.create(
            session_id=session.id,
            role="user",
            content=message
        )
        
        # 流式调用LLM
        llm = get_llm(session.model_name)
        full_response = []

        async for chunk in llm.astream(messages):
            content = chunk.content
            # 过滤空字符串，避免推送无意义的空内容
            if content and content.strip():
                clean_content = content.strip()  # ✅ 去除前后空格
                full_response.append(clean_content)
                yield {"content": clean_content}
        
        # 保存完整响应
        complete_response = "".join(full_response)
        await self.message_repo.create(
            session_id=session.id,
            role="assistant",
            content=complete_response,
            model_name=session.model_name
        )
        
        await self.session_repo.increment_message_count(session_id)
        
        yield {"done": True, "rag_used": rag_context is not None or rag_strategy in ["no_match", "no_result"], "rag_strategy": rag_strategy, "rag_score": best_score}
    
    async def create_session(
        self,
        agent_type: str = "chat",
        model_name: str = None,
        user_id: Optional[int] = None,
        system_prompt: Optional[str] = None
    ) -> dict:
        """创建会话"""
        session_id = str(uuid.uuid4())
        
        session = await self.session_repo.create(
            session_id=session_id,
            agent_type=agent_type,
            model_name=model_name or settings.DEFAULT_MODEL,
            user_id=user_id,
            system_prompt=system_prompt
        )
        
        return {
            "session_id": session.session_id,
            "agent_type": session.agent_type,
            "model_name": session.model_name,
            "created_at": session.created_at
        }