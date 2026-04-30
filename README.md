# Stock Quant — A股涨幅规律分析系统

基于 FastAPI + React 的 A 股量化分析平台，支持涨幅模式识别、K 线图表、策略回测、虚拟交易、AI 预测和数据集持久化。

## 功能概览

| 模块 | 功能 |
|------|------|
| 涨幅规律 | 6 种模式检测：连板、均线多头、放量突破、缩量反弹、V 型反转、碗底反弹 |
| K 线图表 | 多周期 K 线（1 分~月），MA/VOL 指标，基于 klinecharts |
| 数据集 | SQLite 持久化存储，定时增量采集，CSV/JSON 导出 |
| 策略回测 | 碗底反弹策略回测，收益率/夏普/回撤/胜率 |
| 虚拟交易 | T+1 模拟交易，佣金/印花税/滑点 |
| AI 预测 | LSTM 模型预测 1/3/5 日涨跌概率 |

## 技术栈

**后端**: Python 3.11+ / FastAPI / WebSocket / akshare / pandas / numpy / PyTorch / SQLite

**前端**: React 19 + TypeScript / Vite / klinecharts

**数据源**: 东方财富（主力）→ 腾讯财经（降级），三级自动切换

## 快速开始

```bash
# 后端
cd backend
pip install -r requirements.txt
python main.py

# 前端
cd frontend
npm install
npm run dev
```

启动后访问 http://localhost:3000

## 项目结构

```
backend/
  main.py              -- FastAPI 入口
  config.py            -- 环境变量配置
  api/
    routes.py          -- REST API 路由
    websocket.py       -- WS 实时推送
  services/
    stock_data.py      -- 数据获取（三级降级）
    pattern.py         -- 涨幅规律分析引擎
    bowl_rebound.py    -- 碗底反弹策略
    predict.py         -- LSTM 预测
    backtest.py        -- 策略回测
    virtual_trading.py -- 虚拟交易引擎
    data_store.py      -- SQLite 持久化
    collector.py       -- 定时采集任务
    scanner.py         -- 量化预警扫描
  data/                -- SQLite 数据库（自动创建）
frontend/
  src/
    App.tsx            -- Tab 布局主框架
    components/
      DatasetPanel.tsx -- 数据集管理面板
      KlineChart.tsx   -- K 线图组件
      PatternPanel.tsx -- 规律分析面板
      ...              -- 其他业务组件
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stocks` | A 股列表（支持筛选排序） |
| GET | `/api/stocks/{code}/history` | 历史行情（8 种周期） |
| GET | `/api/stocks/{code}/pattern` | 涨幅规律分析 |
| POST | `/api/stocks/{code}/train` | 训练 LSTM 模型 |
| GET | `/api/stocks/{code}/predict` | AI 趋势预测 |
| POST | `/api/backtest/{code}` | 策略回测 |
| GET | `/api/dataset/stats` | 数据集统计 |
| GET | `/api/dataset/export/csv` | 导出 CSV |
| GET | `/api/dataset/export/json` | 导出 JSON |
| POST | `/api/dataset/collect` | 手动触发采集 |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HOST` | `0.0.0.0` | 服务监听地址 |
| `PORT` | `8000` | 后端端口 |
| `DEBUG` | `true` | 调试模式 |
| `COLLECT_INTERVAL` | `300` | 定时采集间隔（秒） |
| `MODEL_DIR` | `D:/AI/stock-quant/models` | 模型存储目录 |

## License

MIT
