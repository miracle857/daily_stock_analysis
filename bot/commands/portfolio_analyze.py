# -*- coding: utf-8 -*-
"""
===================================
持仓分析命令
===================================

分析持仓中所有股票并推送结果。
"""

import logging
import threading
from typing import List

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse

logger = logging.getLogger(__name__)


class PortfolioAnalyzeCommand(BotCommand):
    """
    持仓分析命令

    分析用户持仓中的所有股票，生成分析报告并推送。

    用法：
        /pa - 分析所有持仓股票
    """

    @property
    def name(self) -> str:
        return "pa"

    @property
    def aliases(self) -> List[str]:
        return ["portfolio-analyze", "持仓分析"]

    @property
    def description(self) -> str:
        return "分析持仓股票"

    @property
    def usage(self) -> str:
        return "/pa"

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        """Execute portfolio analysis command."""
        try:
            from src.services.portfolio_service import get_portfolio_service

            service = get_portfolio_service()
            user_id = message.user_id or 'default'
            holdings = service.get_all_holdings(user_id=user_id, with_realtime_price=False)

            if not holdings:
                return BotResponse.markdown_response(
                    "💼 **持仓分析**\n\n"
                    "当前无持仓记录。\n"
                    "请先使用 `/buy <股票代码> <数量> [价格]` 记录买入。"
                )

            stock_names = [f"{h.stock_name}({h.stock_code})" for h in holdings]
            logger.info(f"[PortfolioAnalyzeCommand] 开始分析 {len(holdings)} 只持仓股票")

            # Run analysis in background thread
            thread = threading.Thread(
                target=self._run_analysis,
                args=(message,),
                daemon=True,
            )
            thread.start()

            display_list = ', '.join(stock_names[:5])
            suffix = '...' if len(stock_names) > 5 else ''

            return BotResponse.markdown_response(
                f"✅ **持仓分析任务已启动**\n\n"
                f"• 分析数量: {len(holdings)} 只\n"
                f"• 持仓列表: {display_list}{suffix}\n\n"
                f"分析完成后将自动推送报告。"
            )

        except Exception as e:
            logger.error(f"[PortfolioAnalyzeCommand] 执行失败: {e}")
            return BotResponse.error_response(f"持仓分析失败: {str(e)[:100]}")

    def _run_analysis(self, message: BotMessage) -> None:
        """Background thread: run portfolio analysis."""
        try:
            from src.core.portfolio_analysis import run_portfolio_analysis
            run_portfolio_analysis(source_message=message, query_source="bot")
        except Exception as e:
            logger.error(f"[PortfolioAnalyzeCommand] 持仓分析失败: {e}")
            logger.exception(e)
