"""
Scanner API — SuperTrend opportunity ranking + manual trigger.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.api.dependencies import get_bot_context
from app.api.auth import require_api_key

router = APIRouter(prefix="/api/scanner", tags=["Scanner"], dependencies=[Depends(require_api_key)])


class ManualScanRequest(BaseModel):
    auto_switch: Optional[bool] = Field(
        None,
        description="Override scanner_settings.auto_switch for this run only",
    )


def _job(bot):
    job = getattr(bot, "scanner_job", None)
    if job is None:
        raise HTTPException(status_code=503, detail="Scanner job not initialized")
    return job


@router.get("/opportunities")
def get_opportunities(bot=Depends(get_bot_context)):
    """Return last SuperTrend scan results (cached in ScannerJob)."""
    job = _job(bot)
    results = job.get_last_results()
    settings = getattr(bot, "scanner_settings", {}) or {}
    return {
        "status": "success",
        "enabled": bool(settings.get("enabled", False)),
        "auto_switch": bool(settings.get("auto_switch", False)),
        "min_score": settings.get("min_score", 60),
        "active_symbol": bot.active_symbol,
        "is_scanning": job.is_scanning,
        "count": len(results),
        "results": results,
    }


@router.post("/scan")
def trigger_scan(payload: ManualScanRequest = ManualScanRequest(), bot=Depends(get_bot_context)):
    """Run an immediate SuperTrend scan."""
    job = _job(bot)
    result = job.manual_scan(auto_switch=payload.auto_switch)
    if result.get("status") == "busy":
        raise HTTPException(status_code=409, detail=result.get("message", "Scan busy"))
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message", "Scan failed"))
    return result


@router.get("/status")
def scanner_status(bot=Depends(get_bot_context)):
    job = _job(bot)
    settings = getattr(bot, "scanner_settings", {}) or {}
    return {
        "running": bool(job.is_running),
        "is_scanning": bool(job.is_scanning),
        "last_scan_time": job.last_scan_time,
        "settings": settings,
        "st_params": job._load_st_params(),
        "result_count": len(job.get_last_results()),
    }
