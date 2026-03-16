# -*- coding: utf-8 -*-
"""
===================================
持仓分析模块
===================================

职责：
获取用户持仓中的所有股票代码，调用 StockAnalysisPipeline 进行分析并推送结果。
"""

import logging
import uuid
from typing import Optional

from bot.models import BotMessage

logger = logging.getLogger(__name__)


def run_portfolio_analysis(
    source_message: Optional[BotMessage] = None,
    query_source: str = "system"
):
    """
    Execute analysis for all stocks in the user's portfolio.

    Flow:
    1. Fetch all holdings from PortfolioService
    2. Extract stock codes
    3. Run StockAnalysisPipeline with those codes
    4. Results are automatically pushed via the pipeline's notification mechanism

    Args:
        source_message: originating bot message (for reply context)
        query_source: request source identifier (schedule/bot/cli)
    """
    from src.config import get_config
    from src.services.portfolio_service import get_portfolio_service
    from src.core.pipeline import StockAnalysisPipeline

    config = get_config()
    pf_service = get_portfolio_service()

    # Fetch all holdings (skip realtime price — pipeline will fetch it)
    holdings = pf_service.get_all_holdings(user_id='default', with_realtime_price=False)

    if not holdings:
        logger.warning("[PortfolioAnalysis] 持仓为空，跳过分析")
        if source_message:
            from src.notification import NotificationService
            notifier = NotificationService(source_message=source_message)
            notifier.send("💼 持仓分析：当前无持仓记录，请先使用 /buy 记录买入。")
        return

    stock_codes = [h.stock_code for h in holdings]
    logger.info(f"[PortfolioAnalysis] 开始分析 {len(stock_codes)} 只持仓股票: {stock_codes}")

    pipeline = StockAnalysisPipeline(
        config=config,
        source_message=source_message,
        query_id=uuid.uuid4().hex,
        query_source=query_source,
    )

    results = pipeline.run(
        stock_codes=stock_codes,
        dry_run=False,
        send_notification=True,
    )

    logger.info(f"[PortfolioAnalysis] 分析完成，成功 {len(results)}/{len(stock_codes)} 只")
