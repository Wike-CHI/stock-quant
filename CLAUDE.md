# stock-quant — A股涨幅规律分析系统

> Harness Engineering Framework activated. Plan-Build-Verify workflow enabled.

## Quick Reference

| Command | Purpose |
|---------|---------|
| `/plan <description>` | Create a feature spec from 1-4 sentences |
| `/build` | Build the latest spec via sprint workflow |
| `/qa` | Run evaluator against current code |
| `/sprint <description>` | Full Plan-Build-Verify cycle |

## Tech Stack

**后端**: Python 3.11+ / FastAPI / WebSocket / akshare / pandas / numpy
**前端**: React 19 + TypeScript / Vite / @tanstack/react-virtual
**架构**: 单进程多线程（ThreadPoolExecutor）

## Project Structure

```
backend/
  main.py              -- FastAPI 入口
  config.py            -- 配置（环境变量）
  api/
    routes.py          -- REST API 路由
    websocket.py       -- WS 实时推送
  services/
    stock_data.py      -- akshare 数据获取
    pattern.py         -- 涨幅规律分析引擎
    bowl_rebound.py    -- 碗底反弹策略
    thread_pool.py     -- 线程池管理
  models/
    schemas.py         -- Pydantic 数据模型
  tests/               -- 测试
frontend/
  src/
    App.tsx            -- 主布局（左侧列表 + 右侧分析面板）
    components/
      Header.tsx       -- 顶栏（WS状态/刷新）
      StockList.tsx    -- 虚拟列表股票列表
      PatternPanel.tsx -- 规律分析结果面板
    hooks/
      useWebSocket.ts  -- WS 连接管理
      useStockData.ts  -- 数据获取 hooks
    types/
      index.ts         -- 类型定义
docs/
  architecture.md      -- 系统设计
  golden-principles.md -- 核心规则
  sprint-workflow.md   -- Sprint 流程
  contracts/           -- Sprint 合同
  specs/               -- 功能规格
  plans/               -- 实现计划
.claude/
  agents/              -- Agent 定义
  commands/            -- Slash 命令
  hooks/               -- 自动化守卫
```

## Pattern Analysis Engine

识别6种涨幅模式：
1. **连板模式** (limit_up_streak) — 连续涨停检测
2. **均线多头排列** (ma_bullish_alignment) — MA5>MA10>MA20>MA60
3. **放量突破** (volume_breakout) — 量比>2 且涨幅>3%
4. **缩量反弹** (shrinkage_bounce) — 缩量回调后放量上涨
5. **V型反转** (v_shape_reversal) — 快速下跌后快速回升
6. **碗底反弹** (bowl_rebound) — 双趋势线+KDJ+放量阳线（参考A-Share Quant Selector）

## Running

```bash
# 后端
cd backend && pip install -r requirements.txt && python main.py

# 前端
cd frontend && npm install && npm run dev
```

## Agents

| Agent | Role | Trigger |
|-------|------|---------|
| planner | Expand brief prompts into specs | `/plan` |
| generator | Implement features in sprints | `/build` |
| evaluator | Test and grade implementations | `/qa` |
| doc-gardener | Maintain documentation freshness | Sprint complete |

## Sprint Workflow

1. **Plan**: Planner creates spec in `docs/specs/`
2. **Contract**: Generator + Evaluator agree on "done" criteria
3. **Build**: Generator implements one sprint
4. **Verify**: Evaluator tests against contract (threshold: 80/100)
5. **Fix**: If score < 80, Generator fixes (max 3 iterations)
6. **Complete**: Update docs, run doc-gardener

## Golden Principles

See [docs/golden-principles.md](docs/golden-principles.md) — these are non-negotiable.

## Hooks Active

- **Loop detection**: Blocks after 5 edits to same file
- **Pre-completion checklist**: Verifies before marking done
- **Context injection**: Adds environment info at session start
