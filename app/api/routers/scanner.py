"""
Scanner API — SuperTrend opportunity ranking + manual trigger.
"""
import time

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


def _scanner_strategy_params(bot) -> dict:
    """SuperTrend params snapshot for backward-compatible /scanner/status."""
    engine = getattr(bot, "strategy_engine", None)
    if not engine:
        return {}
    strat = (getattr(engine, "strategies", None) or {}).get("supertrend")
    if strat is None:
        return {}
    cfg = getattr(strat, "config", None) or {}
    params = cfg.get("params") or getattr(strat, "params", None) or {}
    return dict(params) if isinstance(params, dict) else {}


def _scanner_lanes(job) -> list:
    lanes = []
    for name, strat in job._active_strategies():
        try:
            tf = str(strat.get_scan_timeframe() or "15m")
        except Exception:
            tf = "15m"
        try:
            interval_m = float(strat.get_scan_interval_minutes())
        except Exception:
            interval_m = 15.0
        lanes.append(
            {
                "strategy": name,
                "timeframe": tf,
                "interval_minutes": interval_m,
            }
        )
    return lanes


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
        "min_score": settings.get("min_score", 55),
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
    active = getattr(bot, "active_symbol", None)
    results = job.get_last_results()
    active_score = 0.0
    for row in results:
        if row.get("symbol") == active:
            try:
                active_score = float(row.get("score") or 0)
            except (TypeError, ValueError):
                active_score = 0.0
            break
    now = time.time()
    last_switch = float(getattr(job, "last_switch_time", 0) or 0)
    seconds_since_switch = int(now - last_switch) if last_switch > 0 else None
    return {
        "running": bool(job.is_running),
        "is_scanning": bool(job.is_scanning),
        "last_scan_time": job.last_scan_time,
        "last_switch_time": last_switch if last_switch > 0 else None,
        "seconds_since_switch": seconds_since_switch,
        "active_symbol": active,
        "active_symbol_score": active_score,
        "settings": settings,
        "st_params": _scanner_strategy_params(bot),
        "lanes": _scanner_lanes(job),
        "result_count": len(results),
    }
