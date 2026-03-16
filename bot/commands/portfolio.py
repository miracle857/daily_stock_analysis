# -*- coding: utf-8 -*-
"""
===================================
持仓查询命令
===================================

查看持仓列表和盈亏情况。
"""

import logging
from typing import List, Optional

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse

logger = logging.getLogger(__name__)


class PortfolioCommand(BotCommand):
    """
    持仓查询命令

    用法：
        /portfolio          - 查看所有持仓
        /portfolio 601899   - 查看单只股票持仓详情
    """

    @property
    def name(self) -> str:
        return "portfolio"

    @property
    def aliases(self) -> List[str]:
        return ["p", "持仓", "仓位"]

    @property
    def description(self) -> str:
        return "查看持仓"

    @property
    def usage(self) -> str:
        return "/portfolio [股票代码]"

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        """执行持仓查询命令"""
        try:
            from src.services.portfolio_service import get_portfolio_service
            from datetime import datetime

            service = get_portfolio_service()
            user_id = message.user_id or 'default'

            # 单只股票查询
            if args:
                stock_code = args[0]
                return self._show_single_holding(service, stock_code, user_id)

            # 查询所有持仓
            holdings = service.get_all_holdings(user_id, with_realtime_price=True)

            if not holdings:
                return BotResponse.markdown_response(
                    "💼 **我的持仓**\n\n"
                    "暂无持仓记录。\n\n"
                    "使用 `/buy <股票代码> <数量> [价格]` 记录买入。"
                )

            # 计算汇总数据
            summary = service.calculate_portfolio_summary(user_id)

            # 格式化输出
            text = f"💼 **我的持仓** ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n"
            text += "📈 **持仓明细**\n"

            for idx, h in enumerate(holdings, 1):
                emoji = "🟢" if (h.profit_loss or 0) >= 0 else "🔴"
                text += f"\n{idx}. **{h.stock_name}** ({h.stock_code}) {emoji}\n"
                text += f"   持仓: {h.quantity} 股 | 成本: ¥{h.avg_cost:.2f}"

                if h.current_price:
                    text += f" | 现价: ¥{h.current_price:.2f}\n"
                    if h.profit_loss is not None:
                        sign = '+' if h.profit_loss >= 0 else ''
                        text += f"   盈亏: {sign}¥{h.profit_loss:,.2f} ({sign}{h.profit_loss_pct:.2f}%)\n"
                else:
                    text += "\n   (无法获取实时价格)\n"

            # 汇总数据
            text += f"\n💰 **汇总数据**\n"
            text += f"• 总投资: ¥{summary['total_investment']:,.2f}\n"
            text += f"• 总市值: ¥{summary['total_market_value']:,.2f}\n"

            total_pl = summary['total_profit_loss']
            total_pl_pct = summary['total_profit_loss_pct']
            emoji = "🟢" if total_pl >= 0 else "🔴"
            sign = '+' if total_pl >= 0 else ''
            text += f"• 总盈亏: {sign}¥{total_pl:,.2f} ({sign}{total_pl_pct:.2f}%) {emoji}\n"
            text += f"• 持仓股票数: {summary['total_stocks']}\n"

            return BotResponse.markdown_response(text)

        except Exception as e:
            logger.error(f"[PortfolioCommand] 执行失败: {e}")
            return BotResponse.error_response(f"查询持仓失败: {str(e)[:100]}")

    def _show_single_holding(
        self,
        service,
        stock_code: str,
        user_id: str
    ) -> BotResponse:
        """显示单只股票持仓详情"""
        holding = service.get_holding(stock_code, user_id=user_id, with_realtime_price=True)

        if not holding:
            return BotResponse.markdown_response(
                f"💼 **持仓查询**\n\n"
                f"您未持有 {stock_code}。"
            )

        # 格式化输出
        text = f"💼 **持仓详情: {holding.stock_name}** ({holding.stock_code})\n\n"
        text += f"📊 **持仓信息**\n"
        text += f"• 持仓数量: {holding.quantity} 股\n"
        text += f"• 平均成本: ¥{holding.avg_cost:.2f}\n"
        text += f"• 总投入: ¥{holding.total_cost:,.2f}\n"

        if holding.current_price:
            text += f"• 当前价格: ¥{holding.current_price:.2f}\n"
            text += f"• 持仓市值: ¥{holding.market_value:,.2f}\n"

        if holding.profit_loss is not None:
            emoji = "🟢" if holding.profit_loss >= 0 else "🔴"
            sign = '+' if holding.profit_loss >= 0 else ''
            text += f"\n💰 **盈亏分析** {emoji}\n"
            text += f"• 盈亏金额: {sign}¥{holding.profit_loss:,.2f}\n"
            text += f"• 盈亏比例: {sign}{holding.profit_loss_pct:.2f}%\n"

        if holding.first_buy_time:
            text += f"• 首次买入: {holding.first_buy_time.strftime('%Y-%m-%d %H:%M')}\n"
        if holding.holding_days is not None:
            text += f"• 持有天数: {holding.holding_days} 天\n"

        # 查询交易历史
        transactions = service.get_transaction_history(stock_code=stock_code, user_id=user_id, limit=5)
        if transactions:
            text += f"\n📈 **最近交易** (最多显示5条)\n"
            for txn in transactions:
                txn_type = "买入" if txn.transaction_type == 'buy' else "卖出"
                time_str = txn.transaction_time.strftime('%m-%d %H:%M')
                text += f"• {time_str} {txn_type} {txn.quantity}股 @¥{txn.price:.2f}\n"

        return BotResponse.markdown_response(text)
