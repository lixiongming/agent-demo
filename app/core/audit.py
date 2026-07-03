"""审计日志模块 - 大厂标准

功能：
- 记录用户操作
- 记录工具调用
- 记录权限变更
- 记录敏感操作

参考：
- 阿里云审计日志
- 腾讯云操作审计
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from app.core.logger import get_logger
import json

logger = get_logger(__name__)


class AuditLogger:
    """审计日志记录器
    
    功能：
    - 记录用户操作
    - 记录工具调用
    - 记录权限变更
    - 记录敏感操作
    
    使用场景：
    - 工具调用审计
    - 用户行为分析
    - 安全审计
    """
    
    def __init__(self, service_name: str = "agent-service"):
        self.service_name = service_name
    
    def log(
        self,
        action: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ):
        """记录审计日志
        
        Args:
            action: 操作类型（如 tool_call, login, logout, permission_change）
            user_id: 用户 ID
            session_id: 会话 ID
            resource: 资源标识（如工具名称）
            details: 详细信息
            ip_address: IP 地址
            user_agent: 用户代理
            status: 状态（success, failure）
            error_message: 错误信息
        """
        audit_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": self.service_name,
            "action": action,
            "user_id": user_id,
            "session_id": session_id,
            "resource": resource,
            "details": details or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
            "status": status,
            "error_message": error_message
        }
        
        # 记录到日志
        logger.info(f"[AUDIT] {json.dumps(audit_record, ensure_ascii=False)}")
    
    def log_tool_call(
        self,
        tool_name: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        arguments: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        duration_ms: Optional[float] = None
    ):
        """记录工具调用审计日志
        
        Args:
            tool_name: 工具名称
            user_id: 用户 ID
            session_id: 会话 ID
            arguments: 调用参数
            result: 调用结果
            status: 状态
            error_message: 错误信息
            duration_ms: 耗时（毫秒）
        """
        details = {
            "arguments": arguments,
            "result": result,
            "duration_ms": duration_ms
        }
        
        self.log(
            action="tool_call",
            user_id=user_id,
            session_id=session_id,
            resource=tool_name,
            details=details,
            status=status,
            error_message=error_message
        )

    def log_tool_decision(
        self,
        user_id: Optional[str] = None,
        query: Optional[str] = None,
        tool_calls: Optional[list] = None,
        method: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        """记录工具决策审计日志

        Args:
            user_id: 用户 ID
            query: 用户查询
            tool_calls: 工具调用列表
            method: 决策方法
            session_id: 会话 ID
        """
        details = {
            "query": query,
            "tool_calls": tool_calls,
            "method": method
        }

        self.log(
            action="tool_decision",
            user_id=user_id,
            session_id=session_id,
            resource="router",
            details=details,
            status="success"
        )

    def log_tool_execution(
        self,
        tool_name: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tool_args: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        latency_ms: Optional[float] = None
    ):
        """记录工具执行审计日志

        Args:
            tool_name: 工具名称
            user_id: 用户 ID
            session_id: 会话 ID
            tool_args: 调用参数
            result: 执行结果
            success: 是否成功
            error_message: 错误信息
            latency_ms: 耗时（毫秒）
        """
        details = {
            "arguments": tool_args,
            "result": result,
            "latency_ms": latency_ms
        }

        self.log(
            action="tool_execution",
            user_id=user_id,
            session_id=session_id,
            resource=tool_name,
            details=details,
            status="success" if success else "failed",
            error_message=error_message
        )

    def log_permission_check(
        self,
        user_id: str,
        permission: str,
        resource: str,
        granted: bool,
        reason: Optional[str] = None
    ):
        """记录权限检查审计日志
        
        Args:
            user_id: 用户 ID
            permission: 权限类型
            resource: 资源标识
            granted: 是否授权
            reason: 原因
        """
        self.log(
            action="permission_check",
            user_id=user_id,
            resource=resource,
            details={
                "permission": permission,
                "granted": granted,
                "reason": reason
            },
            status="success" if granted else "denied"
        )
    
    def log_operation(
        self,
        operation: str,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        resource: Optional[str] = None,
        ip_address: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ):
        """记录用户操作审计日志

        Args:
            operation: 操作类型（如 user_register, user_login, user_logout）
            user_id: 用户 ID
            details: 详细信息
            resource: 资源标识
            ip_address: IP 地址
            status: 状态（success, failure）
            error_message: 错误信息
        """
        self.log(
            action=operation,
            user_id=str(user_id) if user_id else None,
            resource=resource,
            details=details,
            ip_address=ip_address,
            status=status,
            error_message=error_message
        )

    def log_security(
        self,
        event: str,
        severity: str = "medium",
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ):
        """记录安全事件审计日志

        Args:
            event: 安全事件类型（如 login_failed, login_locked, token_revoked）
            severity: 严重程度（low, medium, high, critical）
            user_id: 用户 ID
            details: 详细信息
            ip_address: IP 地址
        """
        self.log(
            action=f"security_{event}",
            user_id=str(user_id) if user_id else None,
            details={**(details or {}), "severity": severity},
            ip_address=ip_address,
            status="alert"
        )

    def log_sensitive_operation(
        self,
        operation: str,
        user_id: str,
        resource: str,
        details: Optional[Dict[str, Any]] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ):
        """记录敏感操作审计日志
        
        Args:
            operation: 操作类型
            user_id: 用户 ID
            resource: 资源标识
            details: 详细信息
            status: 状态
            error_message: 错误信息
        """
        self.log(
            action=f"sensitive_{operation}",
            user_id=user_id,
            resource=resource,
            details=details,
            status=status,
            error_message=error_message
        )


# 全局审计日志记录器
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """获取全局审计日志记录器"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger