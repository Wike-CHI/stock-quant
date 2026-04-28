import logging

from fastapi import APIRouter, HTTPException
from concurrent.futures import Future

from models.schemas import AnalysisRequest, PatternResult
from services import stock_data, pattern
from services import bowl_rebound
from services import backtest
from services import virtual_trading
from models.schemas import AnalysisRequest, TradeOrder
from services.thread_pool import ThreadPool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


@router.get("/stocks")
def list_stocks(limit: int = 50, sort_by: str = "change_pct", ascending: bool = False):
    """获取A股列表（涨幅排行等）"""
    try:
        df = stock_data.get_a_stock_list()
        df = df.dropna(subset=["change_pct"])
        df = df.sort_values(sort_by, ascending=ascending)
        df = df.head(limit)
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error("Failed to list stocks: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/{code}/history")
def stock_history(code: str, period: str = "daily", start_date: str = "", end_date: str = ""):
    """获取个股历史行情"""
    try:
        df = stock_data.get_stock_history(
            code, period=period,
            start_date=start_date or None,
            end_date=end_date or None,
        )
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error("Failed to get history for %s: %s", code, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/{code}/pattern")
def stock_pattern(code: str, name: str = "", period_days: int = 120):
    """分析单只股票的涨幅规律"""
    try:
        results = pattern.analyze_stock(code, name=name, period_days=period_days)
        return results
    except Exception as e:
        logger.error("Failed to analyze pattern for %s: %s", code, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
def batch_analyze(req: AnalysisRequest):
    """批量分析多只股票（线程池异步）"""
    try:
        codes = [(c, "") for c in req.codes]
        results = pattern.batch_analyze(codes, period_days=req.period_days)
        return results
    except Exception as e:
        logger.error("Batch analyze failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/async/{task_id}")
def start_async_analyze(task_id: str, req: AnalysisRequest):
    """提交异步分析任务"""
    codes = [(c, "") for c in req.codes]
    pool = ThreadPool.get_instance()

    def _work():
        return pattern.batch_analyze(codes, period_days=req.period_days)

    future = pool.submit(f"analyze-{task_id}", _work)
    return {"task_id": task_id, "status": "running"}


@router.get("/analyze/async/{task_id}/result")
def get_async_result(task_id: str):
    """获取异步任务结果"""
    pool = ThreadPool.get_instance()
    future = pool._futures.get(f"analyze-{task_id}")

    if future is None:
        return {"task_id": task_id, "status": "not_found"}
    if not future.done():
        return {"task_id": task_id, "status": "running"}

    result = future.result()
    return {"task_id": task_id, "status": "done", "data": result}


@router.get("/top-gainers")
def top_gainers(limit: int = 50):
    """涨幅排行榜"""
    try:
        df = stock_data.get_top_gainers(limit)
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error("Failed to get top gainers: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/{code}/bowl-rebound")
def stock_bowl_rebound(code: str, name: str = "", period_days: int = 120):
    """碗底反弹策略分析"""
    try:
        return bowl_rebound.analyze_bowl_rebound(code, name=name, period_days=period_days)
    except Exception as e:
        logger.error("Bowl rebound analysis failed for %s: %s", code, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backtest/{code}")
def run_stock_backtest(code: str, start_date: str = "20240101", end_date: str = ""):
    """对个股执行碗底反弹策略回测"""
    try:
        return backtest.run_backtest(code, start_date=start_date, end_date=end_date)
    except Exception as e:
        logger.error("Backtest failed for %s: %s", code, e)
        raise HTTPException(status_code=500, detail=str(e))


# ===== 虚拟交易 =====

@router.get("/trading/account")
def trading_account():
    """查询虚拟账户"""
    return virtual_trading.get_account_info()


@router.post("/trading/order")
def trading_order(req: TradeOrder):
    """下单（买入/卖出）"""
    try:
        return virtual_trading.place_order(
            code=req.code, name=req.name, side=req.side,
            quantity=req.quantity, price=req.price,
        )
    except Exception as e:
        logger.error("Order failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trading/orders")
def trading_orders(limit: int = 50):
    """查询历史委托"""
    return virtual_trading.get_orders(limit)


@router.post("/trading/settle")
def trading_settle():
    """T+1 日结（将今日买入量转为可卖）"""
    return virtual_trading.settle_day()


@router.post("/trading/reset")
def trading_reset():
    """重置虚拟账户"""
    return virtual_trading.reset_account()
