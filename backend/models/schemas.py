from pydantic import BaseModel
from typing import Optional


class StockInfo(BaseModel):
    code: str
    name: str
    price: float
    change_pct: float
    volume: float
    turnover: float
    high: float
    low: float
    open: float
    close: float


class PatternResult(BaseModel):
    code: str
    name: str
    pattern_type: str
    confidence: float
    description: str
    start_date: str
    end_date: str
    rise_probability: Optional[float] = None


class AnalysisRequest(BaseModel):
    codes: list[str]
    period_days: int = 30
    pattern_types: list[str] = []


class WSMessage(BaseModel):
    type: str  # "subscribe" | "unsubscribe" | "ping"
    codes: list[str] = []


class TradeOrder(BaseModel):
    code: str
    name: str = ""
    side: str  # "buy" / "sell"
    quantity: int
    price: float = 0  # 0=市价
