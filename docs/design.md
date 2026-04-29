# Stock Quant — 系统设计文档

> A 股涨幅规律量化分析平台

## 1. 系统概览

```
┌─────────────────────────────────────────────────┐
│                   前端 (React)                   │
│  StockList / KlineChart / PatternPanel           │
│  BacktestPanel / PredictionPanel / TradingPanel  │
└──────────────────┬──────────────────────────────┘
                   │ HTTP REST + WebSocket
┌──────────────────┴──────────────────────────────┐
│                后端 (FastAPI)                     │
│                                                   │
│  ┌──────────┐ ┌──────────┐ ┌───────────────┐     │
│  │ routes.py│ │websocket │ │ thread_pool   │     │
│  └────┬─────┘ └────┬─────┘ └───────────────┘     │
│       │            │                              │
│  ┌────┴────────────┴──────────────────────┐      │
│  │           Services 层                   │      │
│  │  stock_data / pattern / bowl_rebound   │      │
│  │  backtest / predict / virtual_trading  │      │
│  └────┬──────────────────────────────────┘      │
│       │                                          │
│  ┌────┴──────────────────────────────────┐      │
│  │        数据源 / 外部依赖               │      │
│  │  东方财富 push2 API · akshare · PyTorch│      │
│  │  akquant · klinecharts                │      │
│  └───────────────────────────────────────┘      │
└──────────────────────────────────────────────────┘
```

**技术栈：**

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | React + TypeScript + Vite | 单页应用，深色主题 |
| 图表 | klinecharts | K 线图，8 种周期 |
| 后端 | FastAPI + Uvicorn | 异步 ASGI 服务 |
| 数据源 | 东方财富 push2 API | 直接 HTTP，并发分页 |
| 数据处理 | akshare | 分钟线/日线/周线/月线 |
| 回测 | akquant | Rust 加速回测引擎 |
| 深度学习 | PyTorch LSTM | 趋势预测，CPU 模式 |
| 实时推送 | WebSocket | 3 秒间隔行情推送 |

## 2. 目录结构

```
stock-quant/
├── backend/
│   ├── main.py                    # FastAPI 入口，生命周期管理
│   ├── config.py                  # 环境变量配置
│   ├── api/
│   │   ├── routes.py              # REST API 路由（18 个端点）
│   │   └── websocket.py           # WebSocket 实时行情推送
│   ├── models/
│   │   └── schemas.py             # Pydantic 请求/响应模型
│   ├── services/
│   │   ├── stock_data.py          # 数据层：行情获取 + 缓存
│   │   ├── pattern.py             # 涨幅规律分析引擎（5 种模式）
│   │   ├── bowl_rebound.py        # 碗底反弹策略（双趋势线+KDJ）
│   │   ├── backtest.py            # AKQuant 回测引擎封装
│   │   ├── predict.py             # LSTM 深度学习趋势预测
│   │   ├── virtual_trading.py     # 虚拟交易引擎
│   │   └── thread_pool.py         # 线程池（异步任务）
│   └── tests/                     # 52 个单元测试
├── frontend/
│   └── src/
│       ├── App.tsx                # 主布局
│       ├── types/index.ts         # TypeScript 类型定义
│       ├── components/
│       │   ├── StockList.tsx       # 股票列表
│       │   ├── StockFilter.tsx     # 筛选器
│       │   ├── KlineChart.tsx      # K 线图（8 周期）
│       │   ├── PatternPanel.tsx    # 规律分析面板
│       │   ├── BacktestPanel.tsx   # 回测面板
│       │   ├── PredictionPanel.tsx # AI 预测面板
│       │   ├── TradingPanel.tsx    # 虚拟交易面板
│       │   └── Header.tsx          # 顶栏（连接状态）
│       └── hooks/
│           ├── useStockData.ts     # 行情 + 规律分析 Hook
│           └── useWebSocket.ts     # WebSocket Hook
└── models/                        # 训练好的 LSTM 模型文件
```

## 3. 核心模块设计

### 3.1 数据层 — `stock_data.py`

**数据流向：**
```
东方财富 push2 API
    ↓ 并发分页（10 线程，58 页 → ~4 秒）
内存缓存 (_spot_df)
    ↑ 后台守护线程 30 秒刷新
    ↓
get_a_stock_list()       # 全量 A 股列表
get_realtime_quote()     # 按代码筛选
get_top_gainers()        # 涨幅排行
get_stock_history()      # 个股历史行情
```

**关键设计：**
- 绕过 akshare 的 `stock_zh_a_spot_em()`（~70 秒），直接请求东方财富 push2 API
- `pz=5000` 每页 5000 条，`ThreadPoolExecutor(10)` 并发拉取剩余页
- `_spot_df` 全局内存缓存 + `threading.Lock` 保护
- 历史行情按 `period` 分发：分钟线 → `stock_zh_a_hist_min_em()`，日线+ → `stock_zh_a_hist()`
- 缓存 TTL：分钟线 60 秒，日线 300 秒

**K 线周期支持：**
| 周期 | 参数值 | 数据源 | 缓存 TTL |
|------|--------|--------|----------|
| 1 分钟 | `1m` | akshare 分钟线 | 60s |
| 5 分钟 | `5m` | akshare 分钟线 | 60s |
| 15 分钟 | `15m` | akshare 分钟线 | 60s |
| 30 分钟 | `30m` | akshare 分钟线 | 60s |
| 60 分钟 | `60m` | akshare 分钟线 | 60s |
| 日线 | `daily` | akshare 日线 | 300s |
| 周线 | `weekly` | akshare 周线 | 300s |
| 月线 | `monthly` | akshare 月线 | 300s |

### 3.2 规律分析引擎 — `pattern.py`

识别 6 种涨幅模式：

| 模式 | 函数 | 逻辑 |
|------|------|------|
| 连续涨停 | `detect_limit_up_streak` | 连续 ≥2 天涨幅 > 9.5% |
| 均线多头 | `detect_ma_bullish_alignment` | MA5 > MA10 > MA20 > MA60 持续 ≥5 天 |
| 放量突破 | `detect_volume_breakout` | 量比 > 2 且 涨幅 > 3% |
| 缩量反弹 | `detect_shrinkage_bounce` | 连续 3 天缩量下跌后放量上涨 |
| V 型反转 | `detect_v_shape_reversal` | 20 日内跌 > 10% 后反弹 > 跌幅 50% |
| 碗底反弹 | `detect_bowl_rebound` | 双趋势线 + KDJ + 放量阳线 |

### 3.3 碗底反弹策略 — `bowl_rebound.py`

**信号分类：**
- `bowl_center`：回落碗中（多空线 < 收盘 < 短期趋势线）
- `near_duokong`：收盘靠近多空线 ±3%
- `near_short_trend`：收盘靠近短期趋势线 ±2%

**技术指标：**
- 短期趋势线 = EMA(EMA(CLOSE, 10), 10)
- 多空线 = (MA14 + MA28 + MA57 + MA114) / 4
- KDJ = 标准 9 日 KDJ
- 关键 K 线 = 放量阳线（量 > 均量 × N）

**相似度评分（四维加权）：**
| 维度 | 权重 | 条件 |
|------|------|------|
| 双线结构 | 30% | 短期/多空比值偏离度 |
| KDJ 状态 | 20% | J 值 ≤ 30 加分 |
| 量能 | 25% | 存在关键 K 线 |
| 价格形态 | 25% | 回落碗中加分 |

### 3.4 回测引擎 — `backtest.py`

封装 akquant 回测引擎：
- 策略类 `BowlReboundBTStrategy` 继承 `akquant.Strategy`
- 止盈 10% / 止损 5% / 离开碗口卖出
- 输出指标：总收益率、夏普比率、最大回撤、胜率
- 通过 `metrics._raw` 访问 Rust 后端指标

### 3.5 LSTM 趋势预测 — `predict.py`

```
akshare 历史数据
    ↓
特征工程（17 维）
    ↓
标准化 (StandardScaler)
    ↓
30 日滑动窗口 → 序列
    ↓
LSTM（2 层 × 64 隐单元）
    ↓
全连接头 → Sigmoid
    ↓
输出：1日/3日/5日 涨跌概率
```

**17 维特征：**
| 分类 | 特征 |
|------|------|
| 价格 | open, high, low, close |
| 量能 | volume |
| 均线 | ma5, ma10, ma20 |
| 动量 | rsi (14) |
| 趋势 | macd, macd_signal |
| 超买超卖 | kdj_k, kdj_d, kdj_j |
| 收益率 | return_1d, return_5d |
| 波动率 | volatility (20 日) |

**模型参数：**
- 输入：`[batch, 30, 17]`
- LSTM：2 层，64 隐单元，dropout 0.2
- 输出：`[batch, 3]` — 3 个时间窗口的涨跌概率
- 损失：BCELoss
- 优化器：Adam (lr=1e-3)
- 训练：80/20 分割，early stopping on val loss
- 模型文件：`D:/AI/stock-quant/models/{code}.pt`

### 3.6 虚拟交易引擎 — `virtual_trading.py`

```
初始资金 100 万
    ↓
下单 → 撮合（市价 + 滑点 ±0.05%）
    ↓
T+1 锁定（当日买入不可卖）
    ↓
JSON 持久化
```

**费用模拟：**
| 项目 | 费率 |
|------|------|
| 佣金 | 0.025%（最低 5 元） |
| 印花税 | 0.1%（卖出） |
| 滑点 | 买入 +0.05%，卖出 -0.05% |

### 3.7 WebSocket 实时推送 — `websocket.py`

- `ConnectionManager` 管理多连接订阅
- 客户端发送 `{type: "subscribe", codes: [...]}` 订阅
- 服务端每 3 秒从内存缓存推送行情
- `running` 标志防止断连后 send 报错

## 4. 前端组件

| 组件 | 功能 | 数据源 |
|------|------|--------|
| `StockList` | A 股列表，支持关键词搜索 | GET /stocks |
| `StockFilter` | 筛选器（涨幅/价格/换手率/排序） | — |
| `KlineChart` | K 线图，8 周期切换 | GET /stocks/{code}/history |
| `PatternPanel` | 规律分析结果（按模式分组） | GET /stocks/{code}/pattern |
| `BacktestPanel` | 策略回测指标卡片 | POST /backtest/{code} |
| `PredictionPanel` | AI 预测（训练+预测） | POST /train + GET /predict |
| `TradingPanel` | 虚拟交易下单 | POST /trading/order |
| `Header` | 顶栏，WS 连接状态 | WebSocket |
