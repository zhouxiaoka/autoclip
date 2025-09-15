from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from ..core.database import get_db
from ..models.bilibili import BilibiliAccount
from ..services.account_health_service import health_service, AccountHealthStatus
from ..services.account_health_service import check_account_health_task, check_all_accounts_health_task, auto_refresh_cookies_task

router = APIRouter()

# 请求模型
class HealthCheckRequest(BaseModel):
    account_ids: Optional[List[int]] = None
    force_check: bool = False

class CookieRefreshRequest(BaseModel):
    account_id: int
    auto_refresh: bool = True

# 响应模型
class AccountHealthResponse(BaseModel):
    account_id: int
    username: str
    status: str
    message: str
    details: dict
    last_check: datetime
    expires_in: Optional[int] = None

class HealthSummaryResponse(BaseModel):
    total_accounts: int
    healthy_count: int
    warning_count: int
    critical_count: int
    unknown_count: int
    accounts: List[AccountHealthResponse]
    last_updated: datetime

class CookieRefreshResponse(BaseModel):
    success: bool
    message: str
    account_id: int
    username: Optional[str] = None

@router.get("/health/check/{account_id}", response_model=AccountHealthResponse)
async def check_single_account_health(
    account_id: int,
    force_check: bool = False,
    db: Session = Depends(get_db)
):
    """检查单个账号健康状态"""
    try:
        # 检查账号是否存在
        account = db.query(BilibiliAccount).filter(BilibiliAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="账号不存在")
        
        # 如果不强制检查且最近检查过，返回缓存结果
        if not force_check and account.last_health_check:
            time_diff = datetime.now() - account.last_health_check
            if time_diff.total_seconds() < 300:  # 5分钟内检查过
                return AccountHealthResponse(
                    account_id=account.id,
                    username=account.username,
                    status=account.health_status or AccountHealthStatus.UNKNOWN,
                    message=account.health_details.get("message", "缓存结果") if account.health_details else "缓存结果",
                    details=account.health_details or {},
                    last_check=account.last_health_check,
                    expires_in=account.health_details.get("cookie", {}).get("expires_in") if account.health_details else None
                )
        
        # 执行健康检查
        result = await health_service.check_account_health(account_id)
        
        return AccountHealthResponse(
            account_id=result["account_id"],
            username=result.get("username", ""),
            status=result["status"],
            message=result["message"],
            details=result.get("details", {}),
            last_check=result["last_check"],
            expires_in=result.get("details", {}).get("cookie", {}).get("expires_in")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检查失败: {str(e)}")

@router.post("/health/check", response_model=HealthSummaryResponse)
async def check_multiple_accounts_health(
    request: HealthCheckRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """批量检查账号健康状态"""
    try:
        # 获取要检查的账号
        if request.account_ids:
            accounts = db.query(BilibiliAccount).filter(
                BilibiliAccount.id.in_(request.account_ids),
                BilibiliAccount.is_active == True
            ).all()
        else:
            accounts = db.query(BilibiliAccount).filter(BilibiliAccount.is_active == True).all()
        
        if not accounts:
            return HealthSummaryResponse(
                total_accounts=0,
                healthy_count=0,
                warning_count=0,
                critical_count=0,
                unknown_count=0,
                accounts=[],
                last_updated=datetime.now()
            )
        
        # 执行批量检查
        results = []
        for account in accounts:
            # 如果不强制检查且最近检查过，使用缓存结果
            if not request.force_check and account.last_health_check:
                time_diff = datetime.now() - account.last_health_check
                if time_diff.total_seconds() < 300:  # 5分钟内检查过
                    results.append(AccountHealthResponse(
                        account_id=account.id,
                        username=account.username,
                        status=account.health_status or AccountHealthStatus.UNKNOWN,
                        message=account.health_details.get("message", "缓存结果") if account.health_details else "缓存结果",
                        details=account.health_details or {},
                        last_check=account.last_health_check,
                        expires_in=account.health_details.get("cookie", {}).get("expires_in") if account.health_details else None
                    ))
                    continue
            
            # 执行实时检查
            result = await health_service.check_account_health(account.id)
            results.append(AccountHealthResponse(
                account_id=result["account_id"],
                username=result.get("username", ""),
                status=result["status"],
                message=result["message"],
                details=result.get("details", {}),
                last_check=result["last_check"],
                expires_in=result.get("details", {}).get("cookie", {}).get("expires_in")
            ))
        
        # 统计各状态数量
        status_counts = {
            AccountHealthStatus.HEALTHY: 0,
            AccountHealthStatus.WARNING: 0,
            AccountHealthStatus.CRITICAL: 0,
            AccountHealthStatus.UNKNOWN: 0
        }
        
        for result in results:
            if result.status in status_counts:
                status_counts[result.status] += 1
            else:
                status_counts[AccountHealthStatus.UNKNOWN] += 1
        
        return HealthSummaryResponse(
            total_accounts=len(results),
            healthy_count=status_counts[AccountHealthStatus.HEALTHY],
            warning_count=status_counts[AccountHealthStatus.WARNING],
            critical_count=status_counts[AccountHealthStatus.CRITICAL],
            unknown_count=status_counts[AccountHealthStatus.UNKNOWN],
            accounts=results,
            last_updated=datetime.now()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量检查失败: {str(e)}")

@router.get("/health/summary", response_model=HealthSummaryResponse)
async def get_health_summary(db: Session = Depends(get_db)):
    """获取账号健康状态摘要"""
    try:
        accounts = db.query(BilibiliAccount).filter(BilibiliAccount.is_active == True).all()
        
        if not accounts:
            return HealthSummaryResponse(
                total_accounts=0,
                healthy_count=0,
                warning_count=0,
                critical_count=0,
                unknown_count=0,
                accounts=[],
                last_updated=datetime.now()
            )
        
        # 统计各状态数量
        status_counts = {
            AccountHealthStatus.HEALTHY: 0,
            AccountHealthStatus.WARNING: 0,
            AccountHealthStatus.CRITICAL: 0,
            AccountHealthStatus.UNKNOWN: 0
        }
        
        account_responses = []
        for account in accounts:
            status = account.health_status or AccountHealthStatus.UNKNOWN
            if status in status_counts:
                status_counts[status] += 1
            else:
                status_counts[AccountHealthStatus.UNKNOWN] += 1
            
            account_responses.append(AccountHealthResponse(
                account_id=account.id,
                username=account.username,
                status=status,
                message=account.health_details.get("message", "未检查") if account.health_details else "未检查",
                details=account.health_details or {},
                last_check=account.last_health_check or datetime.now(),
                expires_in=account.health_details.get("cookie", {}).get("expires_in") if account.health_details else None
            ))
        
        return HealthSummaryResponse(
            total_accounts=len(accounts),
            healthy_count=status_counts[AccountHealthStatus.HEALTHY],
            warning_count=status_counts[AccountHealthStatus.WARNING],
            critical_count=status_counts[AccountHealthStatus.CRITICAL],
            unknown_count=status_counts[AccountHealthStatus.UNKNOWN],
            accounts=account_responses,
            last_updated=datetime.now()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取摘要失败: {str(e)}")

@router.post("/health/refresh-cookie", response_model=CookieRefreshResponse)
async def refresh_account_cookie(
    request: CookieRefreshRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """刷新账号Cookie"""
    try:
        # 检查账号是否存在
        account = db.query(BilibiliAccount).filter(BilibiliAccount.id == request.account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="账号不存在")
        
        if request.auto_refresh:
            # 异步执行自动刷新
            background_tasks.add_task(
                lambda: auto_refresh_cookies_task.delay(request.account_id)
            )
            
            return CookieRefreshResponse(
                success=True,
                message="已启动自动刷新任务，请稍后查看结果",
                account_id=request.account_id,
                username=account.username
            )
        else:
            # 执行同步刷新
            result = await health_service.auto_refresh_cookies(request.account_id)
            
            return CookieRefreshResponse(
                success=result["success"],
                message=result["message"],
                account_id=request.account_id,
                username=result.get("username", account.username)
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刷新Cookie失败: {str(e)}")

@router.post("/health/schedule-check")
async def schedule_health_check(
    background_tasks: BackgroundTasks,
    account_ids: Optional[List[int]] = None
):
    """调度健康检查任务"""
    try:
        if account_ids:
            # 调度指定账号的检查任务
            for account_id in account_ids:
                background_tasks.add_task(
                    lambda aid=account_id: check_account_health_task.delay(aid)
                )
            
            return {
                "success": True,
                "message": f"已调度 {len(account_ids)} 个账号的健康检查任务",
                "account_count": len(account_ids)
            }
        else:
            # 调度所有账号的检查任务
            background_tasks.add_task(
                lambda: check_all_accounts_health_task.delay()
            )
            
            return {
                "success": True,
                "message": "已调度所有账号的健康检查任务"
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"调度任务失败: {str(e)}")

@router.get("/health/status/{account_id}")
async def get_account_status(
    account_id: int,
    db: Session = Depends(get_db)
):
    """获取账号状态信息"""
    try:
        account = db.query(BilibiliAccount).filter(BilibiliAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="账号不存在")
        
        return {
            "account_id": account.id,
            "username": account.username,
            "status": account.status,
            "health_status": account.health_status,
            "is_active": account.is_active,
            "last_health_check": account.last_health_check,
            "health_details": account.health_details,
            "cookie_expires_at": account.cookie_expires_at,
            "created_at": account.created_at,
            "updated_at": account.updated_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")