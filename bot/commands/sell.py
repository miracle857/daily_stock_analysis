# -*- coding: utf-8 -*-
"""
===================================
卖出命令
===================================

记录股票卖出交易，自动计算盈亏。
"""

import re
import logging
from typing import List, Optional

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse

logger = logging.getLogger(__name__)


class SellCommand(BotCommand):
    """
    卖出记录命令

    用法：
        /sell 601899 500 16.20  - 卖出 601899 500股，价格 16.20
        /sell 601899 500        - 卖出 601899 500股，自动获取实时价格
    """

    @property
    def name(self) -> str:
        return "sell"

    @property
    def aliases(self) -> List[str]:
        return ["卖出", "卖"]

    @property
    def description(self) -> str:
        return "记录股票卖出"

    @property
    def usage(self) -> str:
        return "/sell <股票代码> <数量> [价格]"

    def validate_args(self, args: List[str]) -> Optional[str]:
        """验证参数"""
        if len(args) < 2:
            return "参数不足。用法: /sell <股票代码> <数量> [价格]\n示例: /sell 601899 500 16.20"

        code = args[0].upper()

        # 验证股票代码格式
        is_a_stock = re.match(r'^\d{6}$', code)
        is_hk_stock = re.match(r'^HK\d{5}$', code)
        is_us_stock = re.match(r'^[A-Z]{1,5}(\.[A-Z]{1,2})?$', code)

        if not (is_a_stock or is_hk_stock or is_us_stock):
            return f"无效的股票代码: {code}（A股6位数字 / 港股HK+5位数字 / 美股1-5个字母）"

        # 验证数量
        try:
            quantity = int(args[1])
            if quantity <= 0:
                return "卖出数量必须为正整数"
        except ValueError:
            return f"无效的数量: {args[1]}，请输入正整数"

        # 验证价格（可选）
        if len(args) >= 3:
            try:
                price = float(args[2])
                if price <= 0:
                    return "卖出价格必须大于 0"
            except ValueError:
                return f"无效的价格: {args[2]}，请输入有效数字"

        return None

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        """执行卖出命令"""
        code = args[0]
        quantity = int(args[1])
        price = float(args[2]) if len(args) >= 3 else None

        logger.info(f"[SellCommand] 卖出: {code} {quantity}股 @{price or '实时价格'}")

        try:
            from src.services.portfolio_service import get_portfolio_service

            service = get_portfolio_service()
            user_id = message.user_id or 'default'

            success, msg, txn = service.add_sell_transaction(
                stock_code=code,
                quantity=quantity,
                price=price,
                user_id=user_id
            )

            if not success:
                return BotResponse.error_response(msg)

            # 格式化响应
            text = f"✅ **卖出记录成功**\n\n"
            text += f"📊 **交易详情**\n"
            text += f"• 股票: {txn.stock_name} ({txn.stock_code})\n"
            text += f"• 数量: {txn.quantity} 股\n"
            text += f"• 卖出价: ¥{txn.price:.2f}\n"
            text += f"• 总收入: ¥{txn.amount:,.2f}\n"

            # 盈亏信息
            if txn.profit_loss is not None:
                emoji = "🟢" if txn.profit_loss >= 0 else "🔴"
                text += f"\n💰 **本次盈亏** {emoji}\n"
                text += f"• 盈亏金额: {'+' if txn.profit_loss >= 0 else ''}¥{txn.profit_loss:,.2f}\n"
                text += f"• 盈亏比例: {'+' if txn.profit_loss_pct >= 0 else ''}{txn.profit_loss_pct:.2f}%\n"

            # 查询剩余持仓
            holding = service.get_holding(code, user_id=user_id, with_realtime_price=False)
            if holding:
                text += f"\n💼 **剩余持仓**\n"
                text += f"• 持仓数量: {holding.quantity} 股\n"
                text += f"• 平均成本: ¥{holding.avg_cost:.2f}\n"
            else:
                text += f"\n💼 已清空 {txn.stock_name} 全部持仓\n"

            return BotResponse.markdown_response(text)

        except Exception as e:
            logger.error(f"[SellCommand] 执行失败: {e}")
            return BotResponse.error_response(f"卖出失败: {str(e)[:100]}")
