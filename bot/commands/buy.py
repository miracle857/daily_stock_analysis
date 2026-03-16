# -*- coding: utf-8 -*-
"""
===================================
买入命令
===================================

记录股票买入交易，自动计算加权平均成本。
"""

import re
import logging
from typing import List, Optional

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse

logger = logging.getLogger(__name__)


class BuyCommand(BotCommand):
    """
    买入记录命令

    用法：
        /buy 601899 1000 15.50  - 买入 601899 1000股，价格 15.50
        /buy 601899 1000        - 买入 601899 1000股，自动获取实时价格
    """

    @property
    def name(self) -> str:
        return "buy"

    @property
    def aliases(self) -> List[str]:
        return ["买入", "买"]

    @property
    def description(self) -> str:
        return "记录股票买入"

    @property
    def usage(self) -> str:
        return "/buy <股票代码> <数量> [价格]"

    def validate_args(self, args: List[str]) -> Optional[str]:
        """验证参数"""
        if len(args) < 2:
            return "参数不足。用法: /buy <股票代码> <数量> [价格]\n示例: /buy 601899 1000 15.50"

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
                return "买入数量必须为正整数"
        except ValueError:
            return f"无效的数量: {args[1]}，请输入正整数"

        # 验证价格（可选）
        if len(args) >= 3:
            try:
                price = float(args[2])
                if price <= 0:
                    return "买入价格必须大于 0"
            except ValueError:
                return f"无效的价格: {args[2]}，请输入有效数字"

        return None

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        """执行买入命令"""
        code = args[0]
        quantity = int(args[1])
        price = float(args[2]) if len(args) >= 3 else None

        logger.info(f"[BuyCommand] 买入: {code} {quantity}股 @{price or '实时价格'}")

        try:
            from src.services.portfolio_service import get_portfolio_service

            service = get_portfolio_service()
            user_id = message.user_id or 'default'

            success, msg, txn = service.add_buy_transaction(
                stock_code=code,
                quantity=quantity,
                price=price,
                user_id=user_id
            )

            if not success:
                return BotResponse.error_response(msg)

            # 查询更新后的持仓
            holding = service.get_holding(code, user_id=user_id, with_realtime_price=False)

            # 格式化响应
            text = f"✅ **买入记录成功**\n\n"
            text += f"📊 **交易详情**\n"
            text += f"• 股票: {txn.stock_name} ({txn.stock_code})\n"
            text += f"• 数量: {txn.quantity} 股\n"
            text += f"• 买入价: ¥{txn.price:.2f}\n"
            text += f"• 总成本: ¥{txn.amount:,.2f}\n"
            text += f"• 买入时间: {txn.transaction_time.strftime('%Y-%m-%d %H:%M:%S')}\n"

            if holding:
                text += f"\n💼 **当前持仓**\n"
                text += f"• 累计持仓: {holding.quantity} 股\n"
                text += f"• 平均成本: ¥{holding.avg_cost:.2f}\n"
                text += f"• 总投入: ¥{holding.total_cost:,.2f}\n"

            return BotResponse.markdown_response(text)

        except Exception as e:
            logger.error(f"[BuyCommand] 执行失败: {e}")
            return BotResponse.error_response(f"买入失败: {str(e)[:100]}")
