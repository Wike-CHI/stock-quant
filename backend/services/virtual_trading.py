"""
虚拟交易引擎

- 虚拟账户（资金、持仓）
- 限价/市价单撮合（以 akshare 最新价成交）
- 盈亏计算
- JSON 持久化
"""
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from threading import Lock
from typing import Optional

from services.stock_data import get_realtime_quote

logger = logging.getLogger(__name__)

DATA_FILE = Path("data/virtual_account.json")


@dataclass
class Position:
    code: str
    name: str
    quantity: int
    available: int  # T+1 可卖数量
    avg_cost: float  # 持仓均价
    latest_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.latest_price

    @property
    def profit(self) -> float:
        return (self.latest_price - self.avg_cost) * self.quantity

    @property
    def profit_pct(self) -> float:
        return (self.latest_price - self.avg_cost) / self.avg_cost * 100 if self.avg_cost else 0


@dataclass
class Order:
    id: str
    code: str
    name: str
    side: str  # "buy" / "sell"
    quantity: int
    price: float  # 下单价
    filled_price: float = 0.0
    status: str = "pending"  # pending / filled / rejected / cancelled
    reason: str = ""
    created_at: float = 0.0
    filled_at: float = 0.0


@dataclass
class Account:
    cash: float = 1_000_000.0
    positions: dict[str, Position] = field(default_factory=dict)
    orders: list[Order] = field(default_factory=list)
    next_day_positions: dict[str, int] = field(default_factory=dict)  # T+1 今日买入量

    @property
    def total_assets(self) -> float:
        return self.cash + sum(p.market_value for p in self.positions.values())

    @property
    def total_profit(self) -> float:
        return self.total_assets - 1_000_000.0

    @property
    def total_profit_pct(self) -> float:
        return self.total_profit / 1_000_000.0 * 100

    def get_position(self, code: str) -> Optional[Position]:
        return self.positions.get(code)


_lock = Lock()
_account: Optional[Account] = None


def _get_account() -> Account:
    global _account
    if _account is None:
        _account = _load()
    return _account


def _load() -> Account:
    if DATA_FILE.exists():
        try:
            raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            positions = {
                k: Position(**v) for k, v in raw.get("positions", {}).items()
            }
            orders = [Order(**o) for o in raw.get("orders", [])]
            return Account(
                cash=raw.get("cash", 1_000_000),
                positions=positions,
                orders=orders,
                next_day_positions=raw.get("next_day_positions", {}),
            )
        except Exception as e:
            logger.warning("Load account failed: %s, using default", e)
    return Account()


def _save(account: Account):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "cash": account.cash,
        "positions": {k: asdict(v) for k, v in account.positions.items()},
        "orders": [asdict(o) for o in account.orders[-200:]],
        "next_day_positions": account.next_day_positions,
    }
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_account_info() -> dict:
    with _lock:
        acc = _get_account()
        _update_prices(acc)
        return {
            "cash": round(acc.cash, 2),
            "total_assets": round(acc.total_assets, 2),
            "total_profit": round(acc.total_profit, 2),
            "total_profit_pct": round(acc.total_profit_pct, 2),
            "positions": [
                {
                    "code": p.code, "name": p.name,
                    "quantity": p.quantity, "available": p.available,
                    "avg_cost": round(p.avg_cost, 2),
                    "latest_price": round(p.latest_price, 2),
                    "market_value": round(p.market_value, 2),
                    "profit": round(p.profit, 2),
                    "profit_pct": round(p.profit_pct, 2),
                }
                for p in acc.positions.values()
            ],
        }


def _update_prices(acc: Account):
    if not acc.positions:
        return
    codes = list(acc.positions.keys())
    try:
        df = get_realtime_quote(codes)
        for _, row in df.iterrows():
            p = acc.positions.get(row["code"])
            if p:
                p.latest_price = float(row["price"])
    except Exception as e:
        logger.warning("Update prices failed: %s", e)


def place_order(code: str, name: str, side: str, quantity: int, price: float = 0) -> dict:
    """下单并立即撮合（市价单用最新价）"""
    with _lock:
        acc = _get_account()

        order_id = f"{code}-{side[0]}-{int(time.time()*1000)}"
        order = Order(
            id=order_id, code=code, name=name, side=side,
            quantity=quantity, price=price,
            created_at=time.time(),
        )

        if side == "buy":
            _execute_buy(acc, order)
        else:
            _execute_sell(acc, order)

        acc.orders.append(order)
        _save(acc)
        return asdict(order)


def _execute_buy(acc: Account, order: Order):
    market_price = _get_market_price(order.code)
    if market_price <= 0:
        order.status = "rejected"
        order.reason = "无法获取行情"
        return

    fill_price = order.price if order.price > 0 else market_price
    # 模拟滑点 +0.05%
    fill_price *= 1.0005
    cost = fill_price * order.quantity + _calc_commission(fill_price * order.quantity)

    if cost > acc.cash:
        order.status = "rejected"
        order.reason = f"资金不足（需{cost:.0f}，有{acc.cash:.0f}）"
        return

    order.filled_price = round(fill_price, 3)
    order.status = "filled"
    order.filled_at = time.time()
    acc.cash -= cost

    pos = acc.positions.get(order.code)
    if pos:
        total_qty = pos.quantity + order.quantity
        pos.avg_cost = round((pos.avg_cost * pos.quantity + fill_price * order.quantity) / total_qty, 3)
        pos.quantity = total_qty
        pos.latest_price = market_price
    else:
        acc.positions[order.code] = Position(
            code=order.code, name=order.name,
            quantity=order.quantity, available=0,
            avg_cost=round(fill_price, 3), latest_price=market_price,
        )

    # T+1：今日买入不可卖
    acc.next_day_positions[order.code] = acc.next_day_positions.get(order.code, 0) + order.quantity
    order.reason = f"成交价{fill_price:.3f}"


def _execute_sell(acc: Account, order: Order):
    pos = acc.positions.get(order.code)
    if not pos or pos.available < order.quantity:
        order.status = "rejected"
        order.reason = f"可卖不足（有{pos.available if pos else 0}股）"
        return

    market_price = _get_market_price(order.code)
    if market_price <= 0:
        order.status = "rejected"
        order.reason = "无法获取行情"
        return

    fill_price = order.price if order.price > 0 else market_price
    fill_price *= 0.9995  # 滑点 -0.05%
    amount = fill_price * order.quantity
    commission = _calc_commission(amount)
    stamp_tax = amount * 0.001  # 印花税 0.1%（卖出）

    order.filled_price = round(fill_price, 3)
    order.status = "filled"
    order.filled_at = time.time()
    order.reason = f"成交价{fill_price:.3f}（佣金{commission:.0f}+印花税{stamp_tax:.0f}）"

    acc.cash += amount - commission - stamp_tax
    pos.quantity -= order.quantity
    pos.available -= order.quantity
    pos.latest_price = market_price

    if pos.quantity <= 0:
        del acc.positions[order.code]


def _get_market_price(code: str) -> float:
    try:
        df = get_realtime_quote([code])
        if not df.empty:
            return float(df.iloc[0]["price"])
    except Exception:
        pass
    return 0.0


def _calc_commission(amount: float) -> float:
    """佣金 0.025%，最低5元"""
    return max(amount * 0.00025, 5.0)


def settle_day():
    """T+1 日结：将今日买入量转为可卖"""
    with _lock:
        acc = _get_account()
        for code, qty in acc.next_day_positions.items():
            pos = acc.positions.get(code)
            if pos:
                pos.available += qty
        acc.next_day_positions.clear()
        _save(acc)
    return {"status": "ok", "message": "T+1 日结完成"}


def get_orders(limit: int = 50) -> list[dict]:
    with _lock:
        acc = _get_account()
        return [asdict(o) for o in reversed(acc.orders[-limit:])]


def reset_account():
    """重置账户"""
    with _lock:
        global _account
        _account = Account()
        _save(_account)
    return {"status": "ok", "message": "账户已重置为100万"}
