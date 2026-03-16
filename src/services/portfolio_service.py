# -*- coding: utf-8 -*-
"""
===================================
持仓管理服务
===================================

职责：
1. 管理用户持仓记录（买入、卖出、查询）
2. 计算加权平均成本
3. 计算盈亏
4. 提供交易历史查询
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from sqlalchemy import select, and_, desc
from sqlalchemy.exc import IntegrityError

from src.storage import get_db, PortfolioHolding, PortfolioTransaction
from src.analyzer import get_stock_name_multi_source

logger = logging.getLogger(__name__)


@dataclass
class HoldingInfo:
    """持仓信息数据类"""
    stock_code: str
    stock_name: str
    quantity: int
    avg_cost: float
    total_cost: float
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    profit_loss: Optional[float] = None
    profit_loss_pct: Optional[float] = None
    first_buy_time: Optional[datetime] = None
    holding_days: Optional[int] = None


@dataclass
class TransactionInfo:
    """交易记录数据类"""
    stock_code: str
    stock_name: str
    transaction_type: str
    quantity: int
    price: float
    amount: float
    transaction_time: datetime
    profit_loss: Optional[float] = None
    profit_loss_pct: Optional[float] = None


class PortfolioService:
    """
    持仓管理服务

    提供持仓的增删改查、盈亏计算等功能
    """

    def __init__(self):
        """初始化持仓服务"""
        self.db = get_db()

    def _get_realtime_price(self, stock_code: str) -> Optional[float]:
        """
        获取股票实时价格

        Args:
            stock_code: 股票代码

        Returns:
            实时价格，获取失败返回 None
        """
        try:
            from src.services.stock_service import StockService

            service = StockService()
            quote = service.get_realtime_quote(stock_code)

            if quote and quote.get('current_price'):
                price = float(quote['current_price'])
                if price > 0:
                    return price

            logger.warning(f"获取 {stock_code} 实时价格失败")
            return None

        except Exception as e:
            logger.error(f"获取实时价格异常: {e}")
            return None

    def add_buy_transaction(
        self,
        stock_code: str,
        quantity: int,
        price: Optional[float] = None,
        user_id: str = 'default'
    ) -> Tuple[bool, str, Optional[TransactionInfo]]:
        """
        记录买入交易

        Args:
            stock_code: 股票代码
            quantity: 买入数量
            price: 买入价格（可选，不填则自动获取实时价格）
            user_id: 用户 ID

        Returns:
            (成功标志, 消息, 交易信息)
        """
        try:
            # 1. 获取价格
            if price is None:
                price = self._get_realtime_price(stock_code)
                if price is None:
                    return False, "无法获取实时价格，请手动指定买入价格", None

            # 2. 获取股票名称
            stock_name = get_stock_name_multi_source(stock_code)

            # 3. 计算交易���额
            amount = price * quantity

            with self.db.get_session() as session:
                # 4. 查询现有持仓
                stmt = select(PortfolioHolding).where(
                    and_(
                        PortfolioHolding.user_id == user_id,
                        PortfolioHolding.stock_code == stock_code
                    )
                )
                holding = session.execute(stmt).scalar_one_or_none()

                # 5. 计算新的持仓数据
                now = datetime.now()
                if holding:
                    # 已有持仓，加权平均计算新成本
                    new_quantity = holding.quantity + quantity
                    new_total_cost = holding.total_cost + amount
                    new_avg_cost = new_total_cost / new_quantity

                    holding.quantity = new_quantity
                    holding.total_cost = new_total_cost
                    holding.avg_cost = new_avg_cost
                    holding.stock_name = stock_name  # 更新名称
                    holding.last_update_time = now
                else:
                    # 新建持仓
                    holding = PortfolioHolding(
                        user_id=user_id,
                        stock_code=stock_code,
                        stock_name=stock_name,
                        quantity=quantity,
                        avg_cost=price,
                        total_cost=amount,
                        first_buy_time=now,
                        last_update_time=now
                    )
                    session.add(holding)

                # 6. 插入交易记录
                transaction = PortfolioTransaction(
                    user_id=user_id,
                    stock_code=stock_code,
                    stock_name=stock_name,
                    transaction_type='buy',
                    quantity=quantity,
                    price=price,
                    amount=amount,
                    transaction_time=now
                )
                session.add(transaction)

                # 7. 提交事务
                session.commit()

                # 8. 构建返回信息
                txn_info = TransactionInfo(
                    stock_code=stock_code,
                    stock_name=stock_name,
                    transaction_type='buy',
                    quantity=quantity,
                    price=price,
                    amount=amount,
                    transaction_time=now
                )

                logger.info(f"[Portfolio] 买入成功: {stock_name}({stock_code}) {quantity}股 @¥{price:.2f}")
                return True, "买入记录成功", txn_info

        except Exception as e:
            logger.error(f"[Portfolio] 买入失败: {e}")
            return False, f"买入失败: {str(e)}", None

    def add_sell_transaction(
        self,
        stock_code: str,
        quantity: int,
        price: Optional[float] = None,
        user_id: str = 'default'
    ) -> Tuple[bool, str, Optional[TransactionInfo]]:
        """
        记录卖出交易

        Args:
            stock_code: 股票代码
            quantity: 卖出数量
            price: 卖出价格（可选，不填则自动获取实时价格）
            user_id: 用户 ID

        Returns:
            (成功标志, 消息, 交易信息)
        """
        try:
            # 1. 获取价格
            if price is None:
                price = self._get_realtime_price(stock_code)
                if price is None:
                    return False, "无法获取实时价格，请手动指定卖出价格", None

            with self.db.get_session() as session:
                # 2. 查询持仓
                stmt = select(PortfolioHolding).where(
                    and_(
                        PortfolioHolding.user_id == user_id,
                        PortfolioHolding.stock_code == stock_code
                    )
                )
                holding = session.execute(stmt).scalar_one_or_none()

                if not holding:
                    return False, f"您未持有 {stock_code}，无法卖出", None

                if holding.quantity < quantity:
                    return False, f"持仓不足：当前持有 {holding.quantity} 股，无法卖出 {quantity} 股", None

                # 3. 计算盈亏
                amount = price * quantity
                profit_loss = (price - holding.avg_cost) * quantity
                profit_loss_pct = ((price - holding.avg_cost) / holding.avg_cost) * 100

                # 4. 更新持仓
                now = datetime.now()
                new_quantity = holding.quantity - quantity

                if new_quantity == 0:
                    # 清空持仓
                    session.delete(holding)
                    logger.info(f"[Portfolio] 清空持仓: {holding.stock_name}({stock_code})")
                else:
                    # 减少持仓（成本价不变）
                    holding.quantity = new_quantity
                    holding.total_cost = holding.avg_cost * new_quantity
                    holding.last_update_time = now

                # 5. 插入交易记录
                transaction = PortfolioTransaction(
                    user_id=user_id,
                    stock_code=stock_code,
                    stock_name=holding.stock_name,
                    transaction_type='sell',
                    quantity=quantity,
                    price=price,
                    amount=amount,
                    transaction_time=now,
                    profit_loss=profit_loss,
                    profit_loss_pct=profit_loss_pct
                )
                session.add(transaction)

                # 6. 提交事务
                session.commit()

                # 7. 构建返回信息
                txn_info = TransactionInfo(
                    stock_code=stock_code,
                    stock_name=holding.stock_name,
                    transaction_type='sell',
                    quantity=quantity,
                    price=price,
                    amount=amount,
                    transaction_time=now,
                    profit_loss=profit_loss,
                    profit_loss_pct=profit_loss_pct
                )

                logger.info(f"[Portfolio] 卖出成功: {holding.stock_name}({stock_code}) {quantity}股 @¥{price:.2f}, 盈亏: {profit_loss:+.2f} ({profit_loss_pct:+.2f}%)")
                return True, "卖出记录成功", txn_info

        except Exception as e:
            logger.error(f"[Portfolio] 卖出失败: {e}")
            return False, f"卖出失败: {str(e)}", None

    def get_holding(
        self,
        stock_code: str,
        user_id: str = 'default',
        with_realtime_price: bool = True
    ) -> Optional[HoldingInfo]:
        """
        查询单只股票持仓

        Args:
            stock_code: 股票代码
            user_id: 用户 ID
            with_realtime_price: 是否获取实时价格并计算盈亏

        Returns:
            持仓信息，未持有返回 None
        """
        try:
            with self.db.get_session() as session:
                stmt = select(PortfolioHolding).where(
                    and_(
                        PortfolioHolding.user_id == user_id,
                        PortfolioHolding.stock_code == stock_code
                    )
                )
                holding = session.execute(stmt).scalar_one_or_none()

                if not holding:
                    return None

                # 构建基础信息
                info = HoldingInfo(
                    stock_code=holding.stock_code,
                    stock_name=holding.stock_name,
                    quantity=holding.quantity,
                    avg_cost=holding.avg_cost,
                    total_cost=holding.total_cost,
                    first_buy_time=holding.first_buy_time
                )

                # 计算持有天数
                if holding.first_buy_time:
                    info.holding_days = (datetime.now() - holding.first_buy_time).days

                # 获取实时价格并计算盈亏
                if with_realtime_price:
                    current_price = self._get_realtime_price(stock_code)
                    if current_price:
                        info.current_price = current_price
                        info.market_value = current_price * holding.quantity
                        info.profit_loss = (current_price - holding.avg_cost) * holding.quantity
                        info.profit_loss_pct = ((current_price - holding.avg_cost) / holding.avg_cost) * 100

                return info

        except Exception as e:
            logger.error(f"[Portfolio] 查询持仓失败: {e}")
            return None

    def get_all_holdings(
        self,
        user_id: str = 'default',
        with_realtime_price: bool = True
    ) -> List[HoldingInfo]:
        """
        查询所有持仓

        Args:
            user_id: 用户 ID
            with_realtime_price: 是否获取实时价格并计算盈亏

        Returns:
            持仓列表
        """
        try:
            with self.db.get_session() as session:
                stmt = select(PortfolioHolding).where(
                    PortfolioHolding.user_id == user_id
                ).order_by(PortfolioHolding.last_update_time.desc())

                holdings = session.execute(stmt).scalars().all()

                result = []
                for holding in holdings:
                    info = HoldingInfo(
                        stock_code=holding.stock_code,
                        stock_name=holding.stock_name,
                        quantity=holding.quantity,
                        avg_cost=holding.avg_cost,
                        total_cost=holding.total_cost,
                        first_buy_time=holding.first_buy_time
                    )

                    if holding.first_buy_time:
                        info.holding_days = (datetime.now() - holding.first_buy_time).days

                    if with_realtime_price:
                        current_price = self._get_realtime_price(holding.stock_code)
                        if current_price:
                            info.current_price = current_price
                            info.market_value = current_price * holding.quantity
                            info.profit_loss = (current_price - holding.avg_cost) * holding.quantity
                            info.profit_loss_pct = ((current_price - holding.avg_cost) / holding.avg_cost) * 100

                    result.append(info)

                return result

        except Exception as e:
            logger.error(f"[Portfolio] 查询所有持仓失败: {e}")
            return []

    def calculate_portfolio_summary(
        self,
        user_id: str = 'default'
    ) -> Dict[str, Any]:
        """
        计算持仓汇总数据

        Args:
            user_id: 用户 ID

        Returns:
            汇总数据字典
        """
        holdings = self.get_all_holdings(user_id, with_realtime_price=True)

        if not holdings:
            return {
                'total_stocks': 0,
                'total_investment': 0.0,
                'total_market_value': 0.0,
                'total_profit_loss': 0.0,
                'total_profit_loss_pct': 0.0,
            }

        total_investment = sum(h.total_cost for h in holdings)
        total_market_value = sum(h.market_value or 0 for h in holdings)
        total_profit_loss = sum(h.profit_loss or 0 for h in holdings)

        total_profit_loss_pct = 0.0
        if total_investment > 0:
            total_profit_loss_pct = (total_profit_loss / total_investment) * 100

        return {
            'total_stocks': len(holdings),
            'total_investment': total_investment,
            'total_market_value': total_market_value,
            'total_profit_loss': total_profit_loss,
            'total_profit_loss_pct': total_profit_loss_pct,
        }

    def get_transaction_history(
        self,
        stock_code: Optional[str] = None,
        user_id: str = 'default',
        limit: int = 50
    ) -> List[TransactionInfo]:
        """
        查询交易历史

        Args:
            stock_code: 股票代码（可选，不填则查询所有）
            user_id: 用户 ID
            limit: 返回记录数

        Returns:
            交易记录列表
        """
        try:
            with self.db.get_session() as session:
                stmt = select(PortfolioTransaction).where(
                    PortfolioTransaction.user_id == user_id
                )

                if stock_code:
                    stmt = stmt.where(PortfolioTransaction.stock_code == stock_code)

                stmt = stmt.order_by(desc(PortfolioTransaction.transaction_time)).limit(limit)

                transactions = session.execute(stmt).scalars().all()

                result = []
                for txn in transactions:
                    info = TransactionInfo(
                        stock_code=txn.stock_code,
                        stock_name=txn.stock_name,
                        transaction_type=txn.transaction_type,
                        quantity=txn.quantity,
                        price=txn.price,
                        amount=txn.amount,
                        transaction_time=txn.transaction_time,
                        profit_loss=txn.profit_loss,
                        profit_loss_pct=txn.profit_loss_pct
                    )
                    result.append(info)

                return result

        except Exception as e:
            logger.error(f"[Portfolio] 查询交易历史失败: {e}")
            return []


# 单例访问
_portfolio_service: Optional[PortfolioService] = None


def get_portfolio_service() -> PortfolioService:
    """获取持仓服务单例"""
    global _portfolio_service
    if _portfolio_service is None:
        _portfolio_service = PortfolioService()
    return _portfolio_service
