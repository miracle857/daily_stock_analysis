# Daily Stock Analysis - 项目指南

## 项目概述

A股/港股/美股自选股智能分析系统，基于 AI 大模型（Gemini/OpenAI/Claude）进行多维度股票分析，自动生成「决策仪表盘」并推送到多个通知渠道。

技术栈：Python 3.10+, FastAPI, SQLAlchemy (SQLite), schedule, 多数据源 (AkShare/Tushare/Pytdx/Baostock/YFinance)

## 项目结构

```
daily_stock_analysis/
├── main.py                    # 主入口：CLI 参数解析、模式分发（定时/单次/API/回测）
├── server.py                  # FastAPI 独立启动入口（uvicorn server:app）
├── analyzer_service.py        # 分析服务（旧版兼容入口）
├── .env                       # 环境变量配置（敏感信息，不入库）
│
├── src/                       # 核心业务逻辑
│   ├── config.py              # 配置管理（单例模式，从 .env 加载所有配置项）
│   ├── analyzer.py            # AI 分析层（封装 Gemini/OpenAI/Claude API 调用，生成分析报告）
│   ├── notification.py        # 通知层（多渠道推送：企微/飞书/Telegram/邮件/Pushover/Discord 等）
│   ├── storage.py             # 存储层（SQLAlchemy ORM，SQLite，股票日线/分析历史/持仓/回测等表）
│   ├── scheduler.py           # 定时调度（基于 schedule 库，每日定时执行，优雅退出）
│   ├── stock_analyzer.py      # 趋势分析器（MA 多头排列、乖离率、量价分析、买入信号评分）
│   ├── market_analyzer.py     # 大盘复盘分析器（市场概览、板块涨跌、北向资金）
│   ├── search_service.py      # 搜索服务（Tavily/SerpAPI/Bocha/Brave 多维度情报搜索）
│   ├── formatters.py          # 格式化��具（Markdown 转飞书/企微等平台格式）
│   ├── feishu_doc.py          # 飞书云文档生成
│   ├── enums.py               # 枚举定义（ReportType: simple/full）
│   ├── logging_config.py      # 日志配置
│   │
│   ├── core/
│   │   ├── pipeline.py        # **核心分析流水线** StockAnalysisPipeline
│   │   │                      #   流程：实时行情 → 筹码分布 → 趋势分析 → 情报搜索 → AI 分析 → 保存 → 推送
│   │   ├── market_review.py   # 大盘复盘入口函数 run_market_review()
│   │   └── backtest_engine.py # 回测引擎
│   │
│   ├── services/
│   │   ├── task_service.py    # 异步任务服务（线程池管理，submit_analysis 提交分析任务）
│   │   ├── portfolio_service.py # 持仓管理（买入/卖出/查询/盈亏计算，SQLite 存储）
│   │   ├── stock_service.py   # 股票数据服务（实时行情查询）
│   │   ├── analysis_service.py # 分析服务层
│   │   ├── history_service.py # 历史记录服务
│   │   └── backtest_service.py # 回测服务
│   │
│   └── repositories/
│       ├── analysis_repo.py   # 分析记录仓储
│       ├── stock_repo.py      # 股票数据仓储
│       └── backtest_repo.py   # 回测数据仓储
│
├── data_provider/             # 数据源抽象层
│   ├── base.py                # DataFetcherManager（统一入口，自动故障切换）
│   ├── akshare_fetcher.py     # AkShare 数据源
│   ├── tushare_fetcher.py     # Tushare Pro 数据源
│   ├── pytdx_fetcher.py       # 通达信数据源
│   ├── baostock_fetcher.py    # Baostock 数据源
│   ├── yfinance_fetcher.py    # YFinance 数据源（港股/美股）
│   ├── efinance_fetcher.py    # Efinance 数据源
│   ���── realtime_types.py      # 实时行情统一类型定义
│
├── bot/                       # 机器人模块（多平台命令交互）
│   ├── handler.py             # Webhook 统一处理入口（解析请求 → 分发命令）
│   ├── dispatcher.py          # 命令分发器（注册命令、频率限制、权限检查）
│   ├── models.py              # 消息模型（BotMessage, BotResponse, WebhookResponse）
│   ├── platforms/
│   │   ├── base.py            # 平台适配器基类
│   │   ├── dingtalk.py        # 钉钉 Webhook 适配器
│   │   ├── dingtalk_stream.py # 钉钉 Stream 长连接模式
│   │   ├── feishu_stream.py   # 飞书 Stream 长连接模式
│   │   └── discord.py         # Discord 适配器
│   └── commands/
│       ├── base.py            # 命令基类 BotCommand
│       ├── analyze.py         # /a, /analyze <代码> — 分析指定股票（调用 TaskService）
│       ├── market.py          # /market — 大盘复盘
│       ├── batch.py           # /batch — 批量分析自选股
│       ├── buy.py             # /buy <代码> <数量> [价格] — 记录买入
│       ├── sell.py            # /sell <代码> <数量> [价格] — 记录卖出
│       ��── portfolio.py       # /p, /portfolio — 查看持仓
│       ├── help.py            # /help — 帮助信息
│       └── status.py          # /status — 系统状态
│
├── api/                       # FastAPI REST API
│   ├── app.py                 # FastAPI 应用实例
│   ├── deps.py                # 依赖注入
│   ├── middlewares/
│   │   └── error_handler.py   # 全局错误处理
│   └── v1/
│       ├── router.py          # 路由注册
│       ├── endpoints/
│       │   ├── analysis.py    # /api/v1/analysis/* — 分析接口
│       │   ├── stocks.py      # /api/v1/stocks/* — 股票数据接口
│       │   ├── history.py     # /api/v1/history/* — 历史记录接口
│       │   ├── backtest.py    # /api/v1/backtest/* — 回测接口
│       │   └── health.py      # /api/v1/health — 健康检查
│       └── schemas/           # Pydantic 请求/响应模型
│
├── apps/
│   ├── dsa-web/               # 前端 WebUI（Vue/React + TypeScript + Tailwind）
│   └── dsa-desktop/           # Electron 桌面客户端
│
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml     # analyzer（定时模式）+ server（API 模式）
│
├── tests/                     # 测试
├── scripts/                   # 构建脚本
└── .github/workflows/         # CI/CD（daily_analysis.yml 每日定时分析）
```

## 核心流程

### 1. 个股分析流水线 (`src/core/pipeline.py` → `StockAnalysisPipeline`)

这是系统最核心的类，完整流程：

1. `fetch_and_save_stock_data()` — 获取 30 天日线数据（支持断点续传）
2. `analyze_stock()` — 单股分析：
   - 获取实时行情（量比/换手率/PE/PB）→ `DataFetcherManager.get_realtime_quote()`
   - 获取筹码分布 → `DataFetcherManager.get_chip_distribution()`
   - 趋势分析（MA 多头排列、乖离率、买入信号评分）→ `StockTrendAnalyzer.analyze()`
   - 多维度情报搜索（新闻/风险/业绩）→ `SearchService.search_comprehensive_intel()`
   - 注入持仓信息 → `PortfolioService.get_holding()`
   - AI 综合分析 → `GeminiAnalyzer.analyze()`
   - 保存分析历史 → `storage.save_analysis_history()`
3. `run()` — 批量分析：线程池并发 → 收集结果 → 生成决策仪表盘 → 多渠道推送

### 2. 运行模式 (`main.py`)

| 模式 | 启动方式 | 说明 |
|------|---------|------|
| 单次分析 | `python main.py` | 分析 STOCK_LIST 中所有股票，推送后退出 |
| 指定股票 | `python main.py --stocks 600519,000001` | 分析指定股票 |
| 定时任务 | `python main.py --schedule` | 每日 SCHEDULE_TIME 定时执行 |
| API 服务 | `python main.py --serve-only` | 仅启动 FastAPI，通过 API 触发分析 |
| API+分析 | `python main.py --serve` | 启动 API 并执行一次分析 |
| 大盘复盘 | `python main.py --market-review` | 仅运行大盘复盘 |
| 回测 | `python main.py --backtest` | 对历史分析结果进行回测评估 |

### 3. 通知推送 (`src/notification.py` → `NotificationService`)

支持的渠道（可同时配置多个）：
- 企业微信 Webhook（`WECHAT_WEBHOOK_URL`）
- 飞书 Webhook（`FEISHU_WEBHOOK_URL`）
- Telegram Bot（`TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`）
- 钉钉自定义 Webhook（通过 `CUSTOM_WEBHOOK_URLS`）
- 邮件 SMTP（`EMAIL_SENDER` + `EMAIL_PASSWORD`）
- Pushover / PushPlus / Server酱3
- Discord Bot / Webhook
- AstrBot
- 自定义 Webhook（`CUSTOM_WEBHOOK_URLS`，支持 Bearer Token 认证）

推送模式：
- 汇总推送（默认）：所有股票分析完后生成决策仪表盘一次性推送
- 单股推送（`SINGLE_STOCK_NOTIFY=true`）：每分析完一只立即推送

### 4. 机器人命令 (`bot/`)

通过钉钉/飞书/Discord 等平台的机器人交互：

| 命令 | 别名 | 功能 |
|------|------|------|
| `/analyze <代码>` | `/a` | 分析指定股票 |
| `/market` | | 大盘复盘 |
| `/batch` | | 批量分析自选股 |
| `/buy <代码> <数量> [价格]` | | 记录买入 |
| `/sell <代码> <数量> [价格]` | | 记录卖出 |
| `/portfolio` | `/p` | 查看持仓 |
| `/help` | | 帮助信息 |
| `/status` | | 系统状态 |

命令处理链路：`Webhook → handler.py → dispatcher.py → commands/*.py → TaskService → Pipeline`

### 5. 持仓管理 (`src/services/portfolio_service.py`)

- 数据存储在 SQLite（`PortfolioHolding` + `PortfolioTransaction` 表）
- 支持买入/卖出记录、加权平均成本计算、实时盈亏计算
- 持仓信息会注入到 AI 分析上下文中，影响操作建议
- 通过 `/buy`, `/sell`, `/portfolio` 命令交互

### 6. 定时调度 (`src/scheduler.py`)

- 基于 `schedule` 库，每日指定时间执行
- 配置项：`SCHEDULE_ENABLED=true`, `SCHEDULE_TIME=18:00`
- 支持优雅退出（SIGTERM/SIGINT 信号处理）
- 启动时可选立即执行一次

## 关键配置项 (`src/config.py`)

所有配置通过 `.env` 文件或环境变量加载，核心配置：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `STOCK_LIST` | `600519,000001,300750` | 自选股列表（逗号分隔） |
| `GEMINI_API_KEY` | - | Gemini API Key（主模型） |
| `OPENAI_API_KEY` | - | OpenAI 兼容 API Key（备选） |
| `ANTHROPIC_API_KEY` | - | Claude API Key（备选） |
| `SCHEDULE_ENABLED` | `false` | 是否启用定时任务 |
| `SCHEDULE_TIME` | `18:00` | 每日执行时间 |
| `SINGLE_STOCK_NOTIFY` | `false` | 单股推送模式 |
| `REPORT_TYPE` | `simple` | 报告类型（simple/full） |
| `DATABASE_PATH` | `./data/stock_analysis.db` | SQLite 数据库路径 |
| `MAX_WORKERS` | `3` | 并发线程数 |
| `DINGTALK_STREAM_ENABLED` | `false` | 钉钉 Stream 模式 |
| `FEISHU_STREAM_ENABLED` | `false` | 飞书 Stream 模式 |
| `BACKTEST_ENABLED` | `true` | 自动回测 |

## 开发规范

- 代码注释使用英文
- commit message 使用英文，不添加 Co-Authored-By
- 行宽 120，遵循 black + isort + flake8
- 新增功能需考虑与现有架构的一致性（单例模式、服务层分离、命令注册机制）
- 通知渠道新增需在 `NotificationService` 和 `NotificationChannel` 枚举中注册
- 机器人命令新增需在 `bot/commands/` 下创建并在 `__init__.py` 的 `ALL_COMMANDS` 中注册

## 快速检查

```bash
python -m py_compile main.py src/*.py data_provider/*.py
flake8 main.py src/ --max-line-length=120
./test.sh syntax
```
