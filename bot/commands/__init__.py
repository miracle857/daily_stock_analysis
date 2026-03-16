# -*- coding: utf-8 -*-
"""
===================================
命令处理器模块
===================================

包含所有机器人命令的实现。
"""

from bot.commands.base import BotCommand
from bot.commands.help import HelpCommand
from bot.commands.status import StatusCommand
from bot.commands.analyze import AnalyzeCommand
from bot.commands.market import MarketCommand
from bot.commands.batch import BatchCommand
from bot.commands.buy import BuyCommand
from bot.commands.sell import SellCommand
from bot.commands.portfolio import PortfolioCommand
from bot.commands.portfolio_analyze import PortfolioAnalyzeCommand

# 所有可用命令（用于自动注册）
ALL_COMMANDS = [
    HelpCommand,
    StatusCommand,
    AnalyzeCommand,
    MarketCommand,
    BatchCommand,
    BuyCommand,
    SellCommand,
    PortfolioCommand,
    PortfolioAnalyzeCommand,
]

__all__ = [
    'BotCommand',
    'HelpCommand',
    'StatusCommand',
    'AnalyzeCommand',
    'MarketCommand',
    'BatchCommand',
    'BuyCommand',
    'SellCommand',
    'PortfolioCommand',
    'PortfolioAnalyzeCommand',
    'ALL_COMMANDS',
]
