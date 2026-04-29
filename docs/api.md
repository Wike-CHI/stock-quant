# Stock Quant — API 接口文档

> Base URL: `http://{host}:8000/api`
> WebSocket: `ws://{host}:8000/ws`

## 通用说明

**响应格式：** JSON

**错误响应：**
```json
{ "detail": "错误信息" }
```

**HTTP 状态码：**
| 状态码 | 含义 |
|--------|------|
| 200 | 成功 |
| 422 | 参数验证失败 |
| 500 | 服务端错误 |

---

## 1. 行情数据

### GET /stocks

获取 A 股列表（实时行情）

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `limit` | int | 50 | 返回数量 |
| `sort_by` | string | "change_pct" | 排序字段 |
| `ascending` | bool | false | 升序/降序 |
| `keyword` | string | "" | 搜索代码或名称 |
| `min_change` | float | — | 最低涨幅(%) |
| `max_change` | float | — | 最高涨幅(%) |
| `min_price` | float | — | 最低价格 |
| `max_price` | float | — | 最高价格 |
| `min_turnover_rate` | float | — | 最低换手率(%) |
| `min_vol_ratio` | float | — | 最低量比 |

**响应示例：**
```json
[
  {
    "code": "000001",
    "name": "平安银行",
    "price": 12.34,
    "change_pct": 3.52,
    "change_amount": 0.42,
    "volume": 158234567,
    "turnover": 1949234567.0,
    "amplitude": 4.12,
    "turnover_rate": 1.23,
    "pe": 5.67,
    "pb": 0.89,
    "vol_ratio": 1.45,
    "high": 12.50,
    "low": 11.92,
    "open": 12.00,
    "prev_close": 11.92,
    "total_mv": 239876543210.0,
    "circ_mv": 198765432100.0
  }
]
```

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | string | 股票代码 |
| `name` | string | 股票名称 |
| `price` | float | 最新价 |
| `change_pct` | float | 涨跌幅(%) |
| `change_amount` | float | 涨跌额 |
| `volume` | int | 成交量(股) |
| `turnover` | float | 成交额(元) |
| `amplitude` | float | 振幅(%) |
| `turnover_rate` | float | 换手率(%) |
| `pe` | float | 市盈率 |
| `pb` | float | 市净率 |
| `vol_ratio` | float | 量比 |
| `high` | float | 最高价 |
| `low` | float | 最低价 |
| `open` | float | 开盘价 |
| `prev_close` | float | 昨收价 |
| `total_mv` | float | 总市值 |
| `circ_mv` | float | 流通市值 |

---

### GET /stocks/{code}/history

获取个股历史行情（K 线数据）

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `code` | string | 股票代码（如 000001） |

**查询参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `period` | string | "daily" | 周期：`1m`/`5m`/`15m`/`30m`/`60m`/`daily`/`weekly`/`monthly` |
| `start_date` | string | "" | 起始日期（如 20240101） |
| `end_date` | string | "" | 结束日期 |

**响应示例：**
```json
[
  {
    "date": "2024-12-01",
    "code": "000001",
    "open": 12.00,
    "close": 12.34,
    "high": 12.50,
    "low": 11.92,
    "volume": 158234567,
    "turnover": 1949234567.0
  }
]
```

---

### GET /top-gainers

涨幅排行榜

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `limit` | int | 50 | 返回数量 |

**响应：** 同 `/stocks` 响应格式，按涨幅降序。

---

## 2. 规律分析

### GET /stocks/{code}/pattern

分析单只股票的涨幅规律

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `code` | path | — | 股票代码 |
| `name` | query | "" | 股票名称 |
| `period_days` | query | 120 | 分析天数 |

**响应示例：**
```json
[
  {
    "code": "000001",
    "name": "平安银行",
    "pattern_type": "volume_breakout",
    "confidence": 0.72,
    "description": "放量突破：量比2.1，涨幅3.5%",
    "start_date": "2024-11-20",
    "end_date": "2024-11-20",
    "rise_probability": 0.55,
    "details": {
      "volume_ratio": 2.1,
      "change_pct": 3.5
    }
  }
]
```

**pattern_type 取值：**

| 值 | 中文名 | 说明 |
|----|--------|------|
| `limit_up_streak` | 连板模式 | 连续涨停 |
| `ma_bullish_alignment` | 均线多头 | MA5>MA10>MA20>MA60 |
| `volume_breakout` | 放量突破 | 量比>2 且 涨幅>3% |
| `shrinkage_bounce` | 缩量反弹 | 缩量下跌后放量反弹 |
| `v_shape_reversal` | V型反转 | 快速下跌后快速回升 |
| `bowl_rebound` | 碗底反弹 | 双趋势线+KDJ信号 |

---

### POST /analyze

批量分析多只股票

**请求体：**
```json
{
  "codes": ["000001", "600036", "300750"],
  "period_days": 120,
  "pattern_types": []
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `codes` | string[] | 是 | 股票代码列表 |
| `period_days` | int | 否 | 分析天数，默认 120 |
| `pattern_types` | string[] | 否 | 筛选模式类型，空=全部 |

**响应：**
```json
{
  "000001": [
    { "code": "000001", "pattern_type": "...", "confidence": 0.8, ... }
  ],
  "600036": [
    { "code": "600036", "pattern_type": "...", "confidence": 0.6, ... }
  ]
}
```

---

### POST /analyze/async/{task_id}

提交异步分析任务

**路径参数：** `task_id` — 自定义任务 ID

**请求体：** 同 POST /analyze

**响应：**
```json
{ "task_id": "task-001", "status": "running" }
```

### GET /analyze/async/{task_id}/result

获取异步任务结果

**响应：**
```json
{
  "task_id": "task-001",
  "status": "done",
  "data": { "000001": [...] }
}
```

| status 值 | 说明 |
|-----------|------|
| `running` | 执行中 |
| `done` | 完成 |
| `not_found` | 任务不存在 |

---

## 3. 碗底反弹策略

### GET /stocks/{code}/bowl-rebound

碗底反弹策略分析

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `code` | path | — | 股票代码 |
| `name` | query | "" | 股票名称 |
| `period_days` | query | 120 | 分析天数 |

**响应示例：**
```json
[
  {
    "code": "000001",
    "name": "平安银行",
    "pattern_type": "bowl_rebound",
    "category": "bowl_center",
    "confidence": 0.725,
    "description": "回落碗中，J值25.3",
    "start_date": "2024-11-28",
    "end_date": "2024-11-28",
    "rise_probability": 0.618,
    "details": {
      "category": "bowl_center",
      "J": 25.3,
      "short_trend": 12.85,
      "bull_bear": 12.10,
      "has_key_candle": true,
      "similarity": 0.725
    }
  }
]
```

**category 取值：**

| 值 | 说明 |
|----|------|
| `bowl_center` | 回落碗中（多空线 < 收盘 < 短期趋势线） |
| `near_duokong` | 靠近多空线 ±3% |
| `near_short_trend` | 靠近短期趋势线 ±2% |

---

## 4. 策略回测

### POST /backtest/{code}

对个股执行碗底反弹策略回测

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `code` | path | — | 股票代码 |
| `start_date` | query | "20240101" | 回测起始日期 |
| `end_date` | query | "" | 回测结束日期（空=至今） |

**响应示例：**
```json
{
  "code": "000001",
  "total_return_pct": 12.35,
  "sharpe_ratio": 1.82,
  "max_drawdown_pct": -8.45,
  "end_market_value": 1123500.00,
  "total_bars": 242,
  "win_rate": 58.33
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `total_return_pct` | float | 总收益率(%) |
| `sharpe_ratio` | float | 夏普比率 |
| `max_drawdown_pct` | float | 最大回撤(%) |
| `end_market_value` | float | 终值(元) |
| `total_bars` | int | 总交易天数 |
| `win_rate` | float | 胜率(%) |

---

## 5. 深度学习预测

### POST /stocks/{code}/train

训练 LSTM 预测模型

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `code` | path | — | 股票代码 |
| `epochs` | query | 50 | 训练轮数 |

**响应示例：**
```json
{
  "code": "000001",
  "samples": 450,
  "train_samples": 360,
  "val_samples": 90,
  "best_val_loss": 0.6521,
  "epochs": 50,
  "history": [
    { "epoch": 41, "train_loss": 0.6812, "val_loss": 0.6521 },
    { "epoch": 50, "train_loss": 0.6745, "val_loss": 0.6534 }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `samples` | int | 总样本数 |
| `train_samples` | int | 训练集数量(80%) |
| `val_samples` | int | 验证集数量(20%) |
| `best_val_loss` | float | 最佳验证损失 |
| `history` | array | 最近 10 轮训练日志 |

**错误响应：**
```json
{ "error": "数据不足: 50 行" }
```

---

### GET /stocks/{code}/predict

获取个股趋势预测（需先训练）

**响应示例：**
```json
{
  "code": "000001",
  "last_date": "2024-12-01",
  "last_close": 12.34,
  "model": "LSTM",
  "predictions": [
    {
      "horizon": 1,
      "horizon_label": "1日",
      "rise_prob": 0.672,
      "signal": "看涨"
    },
    {
      "horizon": 3,
      "horizon_label": "3日",
      "rise_prob": 0.543,
      "signal": "中性"
    },
    {
      "horizon": 5,
      "horizon_label": "5日",
      "rise_prob": 0.389,
      "signal": "看跌"
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `last_date` | string | 最新数据日期 |
| `last_close` | float | 最新收盘价 |
| `predictions` | array | 预测结果列表 |
| `predictions[].horizon` | int | 预测天数(1/3/5) |
| `predictions[].rise_prob` | float | 上涨概率(0~1) |
| `predictions[].signal` | string | 信号：看涨(>0.6)/中性(0.4~0.6)/看跌(<0.4) |

**未训练响应：**
```json
{
  "error": "模型未训练: 000001",
  "need_train": true
}
```

---

### GET /model/status

查询模型状态

**响应示例：**
```json
{
  "model_dir": "D:/AI/stock-quant/models",
  "saved_models": ["000001", "600036"],
  "device": "cpu",
  "feature_count": 17,
  "seq_len": 30,
  "pred_horizons": [1, 3, 5]
}
```

---

## 6. 虚拟交易

### GET /trading/account

查询虚拟账户

**响应示例：**
```json
{
  "cash": 850000.00,
  "total_assets": 1050000.00,
  "total_profit": 50000.00,
  "total_profit_pct": 5.0,
  "positions": [
    {
      "code": "000001",
      "name": "平安银行",
      "quantity": 10000,
      "available": 10000,
      "avg_cost": 12.00,
      "latest_price": 12.50,
      "market_value": 125000.00,
      "profit": 5000.00,
      "profit_pct": 4.17
    }
  ]
}
```

---

### POST /trading/order

下单（买入/卖出）

**请求体：**
```json
{
  "code": "000001",
  "name": "平安银行",
  "side": "buy",
  "quantity": 100,
  "price": 0
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `code` | string | 是 | 股票代码 |
| `name` | string | 否 | 股票名称 |
| `side` | string | 是 | "buy" 或 "sell" |
| `quantity` | int | 是 | 数量（股） |
| `price` | float | 是 | 价格，0=市价单 |

**买入成功响应：**
```json
{
  "id": "000001-b-1701417600000",
  "code": "000001",
  "name": "平安银行",
  "side": "buy",
  "quantity": 100,
  "price": 0,
  "filled_price": 12.36,
  "status": "filled",
  "reason": "成交价12.360",
  "created_at": 1701417600.0,
  "filled_at": 1701417600.123
}
```

**卖出失败（T+1 锁定）响应：**
```json
{
  "id": "000001-s-1701417600000",
  "status": "rejected",
  "reason": "可卖不足（有0股）"
}
```

| status 值 | 说明 |
|-----------|------|
| `filled` | 已成交 |
| `rejected` | 已拒绝 |
| `pending` | 待处理 |

---

### GET /trading/orders

查询历史委托

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `limit` | int | 50 | 返回数量 |

**响应：** Order 对象数组，按时间倒序。

---

### POST /trading/settle

T+1 日结（将今日买入量转为可卖）

**响应：**
```json
{ "status": "ok", "message": "T+1 日结完成" }
```

---

### POST /trading/reset

重置虚拟账户（恢复 100 万初始资金）

**响应：**
```json
{ "status": "ok", "message": "账户已重置为100万" }
```

---

## 7. WebSocket

**连接地址：** `ws://{host}:8000/ws`

### 客户端 → 服务端

**订阅行情：**
```json
{ "type": "subscribe", "codes": ["000001", "600036"] }
```

**取消订阅：**
```json
{ "type": "unsubscribe", "codes": ["000001"] }
```

**心跳：**
```json
{ "type": "ping" }
```

### 服务端 → 客户端

**行情推送（每 3 秒）：**
```json
{
  "type": "quotes",
  "data": [
    { "code": "000001", "name": "平安银行", "price": 12.34, "change_pct": 3.52, ... }
  ]
}
```

**心跳响应：**
```json
{ "type": "pong" }
```

---

## 8. 端点汇总

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stocks` | A 股列表 |
| GET | `/api/stocks/{code}/history` | K 线历史数据 |
| GET | `/api/stocks/{code}/pattern` | 涨幅规律分析 |
| GET | `/api/stocks/{code}/bowl-rebound` | 碗底反弹分析 |
| POST | `/api/stocks/{code}/train` | 训练 LSTM 模型 |
| GET | `/api/stocks/{code}/predict` | 趋势预测 |
| POST | `/api/analyze` | 批量规律分析 |
| POST | `/api/analyze/async/{task_id}` | 异步分析任务 |
| GET | `/api/analyze/async/{task_id}/result` | 异步任务结果 |
| POST | `/api/backtest/{code}` | 策略回测 |
| GET | `/api/top-gainers` | 涨幅排行榜 |
| GET | `/api/model/status` | 模型状态 |
| GET | `/api/trading/account` | 虚拟账户 |
| POST | `/api/trading/order` | 下单 |
| GET | `/api/trading/orders` | 历史委托 |
| POST | `/api/trading/settle` | T+1 日结 |
| POST | `/api/trading/reset` | 重置账户 |
| — | `ws://.../ws` | WebSocket 实时行情 |
