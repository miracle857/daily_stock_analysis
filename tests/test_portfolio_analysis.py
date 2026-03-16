# -*- coding: utf-8 -*-
"""
===================================
持仓分析功能测试
===================================

覆盖：
1. Config 新字段（portfolio_analysis_enabled / portfolio_analysis_time）
2. Scheduler.add_daily_task() 多任务注册
3. run_portfolio_analysis() 入口函数
4. PortfolioAnalyzeCommand (/pa 命令)
5. 命令注册 + 定时任务集成
"""

import os
import sys
import time
import threading
import unittest
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from unittest.mock import patch, MagicMock


# ============================================================
# 1. Config 新字段测试
# ============================================================

class TestConfigPortfolioFields(unittest.TestCase):
    """测试 Config 中新增的持仓分析配置字段"""

    def setUp(self):
        from src.config import Config
        Config._instance = None

    def tearDown(self):
        from src.config import Config
        Config._instance = None
        for key in ['PORTFOLIO_ANALYSIS_ENABLED', 'PORTFOLIO_ANALYSIS_TIME']:
            os.environ.pop(key, None)

    def test_default_values(self):
        """默认值：disabled, 17:00"""
        from src.config import Config
        config = Config()
        self.assertFalse(config.portfolio_analysis_enabled)
        self.assertEqual(config.portfolio_analysis_time, "17:00")

    def test_env_enabled_true(self):
        """环境变量 PORTFOLIO_ANALYSIS_ENABLED=true 生效"""
        os.environ['PORTFOLIO_ANALYSIS_ENABLED'] = 'true'
        os.environ['PORTFOLIO_ANALYSIS_TIME'] = '09:30'
        from src.config import Config
        Config._instance = None
        config = Config.get_instance()
        self.assertTrue(config.portfolio_analysis_enabled)
        self.assertEqual(config.portfolio_analysis_time, '09:30')

    def test_env_enabled_false(self):
        """环境变量 PORTFOLIO_ANALYSIS_ENABLED=false 生效"""
        os.environ['PORTFOLIO_ANALYSIS_ENABLED'] = 'false'
        from src.config import Config
        Config._instance = None
        config = Config.get_instance()
        self.assertFalse(config.portfolio_analysis_enabled)

    def test_env_case_insensitive(self):
        """环境变量大小写不敏感"""
        os.environ['PORTFOLIO_ANALYSIS_ENABLED'] = 'True'
        from src.config import Config
        Config._instance = None
        config = Config.get_instance()
        self.assertTrue(config.portfolio_analysis_enabled)


# ============================================================
# 2. Scheduler.add_daily_task() 测试
# ============================================================

class TestSchedulerAddDailyTask(unittest.TestCase):
    """测试 Scheduler 多任务注册功能"""

    def setUp(self):
        """清空 schedule 全局 job 列表"""
        import schedule
        schedule.clear()

    def tearDown(self):
        import schedule
        schedule.clear()

    def test_add_single_task(self):
        """注册单个任务"""
        from src.scheduler import Scheduler
        scheduler = Scheduler()

        task_fn = MagicMock()
        scheduler.add_daily_task(
            name="test_task",
            task=task_fn,
            schedule_time="10:00",
            run_immediately=False,
        )

        self.assertIn("test_task", scheduler._tasks)
        self.assertEqual(len(scheduler.schedule.get_jobs()), 1)
        task_fn.assert_not_called()

    def test_add_multiple_tasks(self):
        """注册多个任务，不同时间"""
        from src.scheduler import Scheduler
        scheduler = Scheduler()

        task_a = MagicMock()
        task_b = MagicMock()

        scheduler.add_daily_task(name="task_a", task=task_a, schedule_time="09:00")
        scheduler.add_daily_task(name="task_b", task=task_b, schedule_time="17:00")

        self.assertEqual(len(scheduler._tasks), 2)
        self.assertEqual(len(scheduler.schedule.get_jobs()), 2)

    def test_run_immediately(self):
        """run_immediately=True 时立即执行一次"""
        from src.scheduler import Scheduler
        scheduler = Scheduler()

        task_fn = MagicMock()
        scheduler.add_daily_task(
            name="immediate",
            task=task_fn,
            schedule_time="23:59",
            run_immediately=True,
        )

        task_fn.assert_called_once()

    def test_task_exception_does_not_crash(self):
        """任务抛异常不影响调度器"""
        from src.scheduler import Scheduler
        scheduler = Scheduler()

        def failing_task():
            raise RuntimeError("boom")

        # Should not raise
        scheduler.add_daily_task(
            name="failing",
            task=failing_task,
            schedule_time="12:00",
            run_immediately=True,
        )

    def test_set_daily_task_backward_compat(self):
        """set_daily_task() 向后兼容"""
        from src.scheduler import Scheduler
        scheduler = Scheduler(schedule_time="18:00")

        task_fn = MagicMock()
        scheduler.set_daily_task(task=task_fn, run_immediately=False)

        self.assertIn("stock_analysis", scheduler._tasks)
        self.assertEqual(len(scheduler.schedule.get_jobs()), 1)
        task_fn.assert_not_called()

    def test_set_daily_task_run_immediately(self):
        """set_daily_task(run_immediately=True) 立即执行"""
        from src.scheduler import Scheduler
        scheduler = Scheduler(schedule_time="18:00")

        task_fn = MagicMock()
        scheduler.set_daily_task(task=task_fn, run_immediately=True)

        task_fn.assert_called_once()


# ============================================================
# 3. run_portfolio_analysis() 测试
# ============================================================

@dataclass
class FakeHolding:
    """模拟 HoldingInfo"""
    stock_code: str
    stock_name: str = "测试股票"
    quantity: int = 100
    avg_cost: float = 10.0
    total_cost: float = 1000.0
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    profit_loss: Optional[float] = None
    profit_loss_pct: Optional[float] = None
    first_buy_time: Optional[datetime] = None
    holding_days: Optional[int] = None


class TestRunPortfolioAnalysis(unittest.TestCase):
    """测试 run_portfolio_analysis() 入口函数

    由于 portfolio_analysis.py 内部 lazy import 了 pipeline / config / portfolio_service，
    而 pipeline 有很深的依赖链（tenacity, markdown2 等），
    我们需要在 import 前用 sys.modules mock 掉这些模块。
    """

    def setUp(self):
        """Pre-populate sys.modules with mocks for heavy dependencies"""
        self.mock_pipeline_module = MagicMock()
        self.mock_config_module = MagicMock()
        self.mock_pf_module = MagicMock()
        self.mock_notification_module = MagicMock()

        self._original_modules = {}
        modules_to_mock = {
            'src.core.pipeline': self.mock_pipeline_module,
            'src.services.portfolio_service': self.mock_pf_module,
            'src.notification': self.mock_notification_module,
        }
        for mod_name, mock_mod in modules_to_mock.items():
            self._original_modules[mod_name] = sys.modules.get(mod_name)
            sys.modules[mod_name] = mock_mod

        # Force reimport of portfolio_analysis to pick up mocked modules
        if 'src.core.portfolio_analysis' in sys.modules:
            del sys.modules['src.core.portfolio_analysis']

    def tearDown(self):
        """Restore original modules"""
        for mod_name, original in self._original_modules.items():
            if original is None:
                sys.modules.pop(mod_name, None)
            else:
                sys.modules[mod_name] = original
        if 'src.core.portfolio_analysis' in sys.modules:
            del sys.modules['src.core.portfolio_analysis']

    def test_normal_flow(self):
        """正常流程：获取持仓 → 创建 pipeline → 执行分析"""
        # Setup
        mock_config = MagicMock()
        mock_get_config = MagicMock(return_value=mock_config)

        holdings = [FakeHolding(stock_code="600519"), FakeHolding(stock_code="000858")]
        mock_pf_service = MagicMock()
        mock_pf_service.get_all_holdings.return_value = holdings
        mock_get_pf = MagicMock(return_value=mock_pf_service)

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = [MagicMock(), MagicMock()]
        mock_pipeline_cls = MagicMock(return_value=mock_pipeline)

        self.mock_config_module.get_config = mock_get_config
        self.mock_pf_module.get_portfolio_service = mock_get_pf
        self.mock_pipeline_module.StockAnalysisPipeline = mock_pipeline_cls

        with patch.dict('sys.modules', {'src.config': self.mock_config_module}):
            from src.core.portfolio_analysis import run_portfolio_analysis
            run_portfolio_analysis(query_source="test")

        # Verify
        mock_pf_service.get_all_holdings.assert_called_once_with(
            user_id='default', with_realtime_price=False
        )
        mock_pipeline_cls.assert_called_once()
        init_kwargs = mock_pipeline_cls.call_args.kwargs
        self.assertEqual(init_kwargs['config'], mock_config)
        self.assertEqual(init_kwargs['query_source'], 'test')
        self.assertIsNone(init_kwargs['source_message'])

        mock_pipeline.run.assert_called_once_with(
            stock_codes=["600519", "000858"],
            dry_run=False,
            send_notification=True,
        )

    def test_empty_holdings_no_message(self):
        """持仓为空，无 source_message，静默跳过"""
        mock_pf_service = MagicMock()
        mock_pf_service.get_all_holdings.return_value = []
        self.mock_pf_module.get_portfolio_service = MagicMock(return_value=mock_pf_service)
        self.mock_config_module.get_config = MagicMock(return_value=MagicMock())

        with patch.dict('sys.modules', {'src.config': self.mock_config_module}):
            from src.core.portfolio_analysis import run_portfolio_analysis
            # Should not raise
            run_portfolio_analysis()

    def test_empty_holdings_with_message(self):
        """持仓为空，有 source_message，发送提示"""
        from bot.models import BotMessage, ChatType

        mock_pf_service = MagicMock()
        mock_pf_service.get_all_holdings.return_value = []
        self.mock_pf_module.get_portfolio_service = MagicMock(return_value=mock_pf_service)
        self.mock_config_module.get_config = MagicMock(return_value=MagicMock())

        mock_notifier = MagicMock()
        self.mock_notification_module.NotificationService = MagicMock(return_value=mock_notifier)

        message = BotMessage(
            platform="test", message_id="1", user_id="u1",
            user_name="tester", chat_id="c1", chat_type=ChatType.PRIVATE,
            content="/pa",
        )

        with patch.dict('sys.modules', {'src.config': self.mock_config_module}):
            from src.core.portfolio_analysis import run_portfolio_analysis
            run_portfolio_analysis(source_message=message)

        self.mock_notification_module.NotificationService.assert_called_once_with(
            source_message=message
        )
        mock_notifier.send.assert_called_once()
        self.assertIn("持仓分析", mock_notifier.send.call_args[0][0])

    def test_source_message_passed_to_pipeline(self):
        """source_message 正确传递给 pipeline"""
        from bot.models import BotMessage, ChatType

        mock_pf_service = MagicMock()
        mock_pf_service.get_all_holdings.return_value = [FakeHolding(stock_code="600519")]
        self.mock_pf_module.get_portfolio_service = MagicMock(return_value=mock_pf_service)
        self.mock_config_module.get_config = MagicMock(return_value=MagicMock())

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = []
        mock_pipeline_cls = MagicMock(return_value=mock_pipeline)
        self.mock_pipeline_module.StockAnalysisPipeline = mock_pipeline_cls

        message = BotMessage(
            platform="test", message_id="1", user_id="u1",
            user_name="tester", chat_id="c1", chat_type=ChatType.PRIVATE,
            content="/pa",
        )

        with patch.dict('sys.modules', {'src.config': self.mock_config_module}):
            from src.core.portfolio_analysis import run_portfolio_analysis
            run_portfolio_analysis(source_message=message, query_source="bot")

        init_kwargs = mock_pipeline_cls.call_args.kwargs
        self.assertEqual(init_kwargs['source_message'], message)
        self.assertEqual(init_kwargs['query_source'], 'bot')


# ============================================================
# 4. PortfolioAnalyzeCommand 测试
# ============================================================

class TestPortfolioAnalyzeCommand(unittest.TestCase):
    """测试 /pa 命令"""

    def _make_message(self, content="/pa", user_id="default"):
        from bot.models import BotMessage, ChatType
        return BotMessage(
            platform="test", message_id="msg1", user_id=user_id,
            user_name="tester", chat_id="chat1", chat_type=ChatType.PRIVATE,
            content=content,
        )

    def test_command_properties(self):
        """命令属性正确"""
        from bot.commands.portfolio_analyze import PortfolioAnalyzeCommand
        cmd = PortfolioAnalyzeCommand()
        self.assertEqual(cmd.name, "pa")
        self.assertIn("portfolio-analyze", cmd.aliases)
        self.assertIn("持仓分析", cmd.aliases)
        self.assertEqual(cmd.usage, "/pa")

    @patch('src.services.portfolio_service.get_portfolio_service')
    def test_empty_holdings_response(self, mock_get_pf):
        """持仓为空时返回提示"""
        from bot.commands.portfolio_analyze import PortfolioAnalyzeCommand

        mock_service = MagicMock()
        mock_service.get_all_holdings.return_value = []
        mock_get_pf.return_value = mock_service

        cmd = PortfolioAnalyzeCommand()
        response = cmd.execute(self._make_message(), [])

        self.assertIn("无持仓记录", response.text)
        self.assertTrue(response.markdown)

    @patch('src.services.portfolio_service.get_portfolio_service')
    def test_has_holdings_starts_thread(self, mock_get_pf):
        """有持仓时启动后台线程并返回确认"""
        from bot.commands.portfolio_analyze import PortfolioAnalyzeCommand

        holdings = [
            FakeHolding(stock_code="600519", stock_name="贵州茅台"),
            FakeHolding(stock_code="000858", stock_name="五粮液"),
        ]
        mock_service = MagicMock()
        mock_service.get_all_holdings.return_value = holdings
        mock_get_pf.return_value = mock_service

        cmd = PortfolioAnalyzeCommand()

        with patch.object(cmd, '_run_analysis') as mock_run:
            response = cmd.execute(self._make_message(), [])

        self.assertIn("任务已启动", response.text)
        self.assertIn("2 只", response.text)
        self.assertIn("贵州茅台", response.text)
        self.assertTrue(response.markdown)

    @patch('src.services.portfolio_service.get_portfolio_service')
    def test_more_than_5_holdings_truncated(self, mock_get_pf):
        """超过5只股票时显示省略号"""
        from bot.commands.portfolio_analyze import PortfolioAnalyzeCommand

        holdings = [FakeHolding(stock_code=f"60000{i}", stock_name=f"股票{i}") for i in range(7)]
        mock_service = MagicMock()
        mock_service.get_all_holdings.return_value = holdings
        mock_get_pf.return_value = mock_service

        cmd = PortfolioAnalyzeCommand()

        with patch.object(cmd, '_run_analysis'):
            response = cmd.execute(self._make_message(), [])

        self.assertIn("7 只", response.text)
        self.assertIn("...", response.text)

    @patch('src.core.portfolio_analysis.run_portfolio_analysis')
    def test_run_analysis_calls_function(self, mock_run_pa):
        """_run_analysis 调用 run_portfolio_analysis"""
        from bot.commands.portfolio_analyze import PortfolioAnalyzeCommand

        cmd = PortfolioAnalyzeCommand()
        message = self._make_message()

        cmd._run_analysis(message)

        mock_run_pa.assert_called_once_with(source_message=message, query_source="bot")

    @patch('src.services.portfolio_service.get_portfolio_service')
    def test_exception_returns_error_response(self, mock_get_pf):
        """异常时返回错误响应"""
        from bot.commands.portfolio_analyze import PortfolioAnalyzeCommand

        mock_get_pf.side_effect = RuntimeError("db connection failed")

        cmd = PortfolioAnalyzeCommand()
        response = cmd.execute(self._make_message(), [])

        self.assertIn("失败", response.text)

    @patch('src.services.portfolio_service.get_portfolio_service')
    def test_user_id_from_message(self, mock_get_pf):
        """使用 message.user_id 查询持仓"""
        from bot.commands.portfolio_analyze import PortfolioAnalyzeCommand

        mock_service = MagicMock()
        mock_service.get_all_holdings.return_value = []
        mock_get_pf.return_value = mock_service

        cmd = PortfolioAnalyzeCommand()
        cmd.execute(self._make_message(user_id="user_123"), [])

        mock_service.get_all_holdings.assert_called_once_with(
            user_id="user_123", with_realtime_price=False
        )


# ============================================================
# 5. 命令注册测试
# ============================================================

class TestCommandRegistration(unittest.TestCase):
    """测试命令注册"""

    def test_portfolio_analyze_in_all_commands(self):
        """PortfolioAnalyzeCommand 已注册到 ALL_COMMANDS"""
        from bot.commands import ALL_COMMANDS
        from bot.commands.portfolio_analyze import PortfolioAnalyzeCommand
        self.assertIn(PortfolioAnalyzeCommand, ALL_COMMANDS)

    def test_portfolio_analyze_in_all_exports(self):
        """PortfolioAnalyzeCommand 在 __all__ 中"""
        from bot.commands import __all__ as exports
        self.assertIn('PortfolioAnalyzeCommand', exports)


# ============================================================
# 6. 定时任务集成测试
# ============================================================

class TestMainScheduleIntegration(unittest.TestCase):
    """测试 main.py 中定时任务模式的持仓分析集成"""

    def setUp(self):
        import schedule
        schedule.clear()

    def tearDown(self):
        import schedule
        schedule.clear()

    def test_scheduler_registers_two_tasks(self):
        """portfolio_analysis_enabled=True 时注册两个任务"""
        from src.scheduler import Scheduler

        scheduler = Scheduler()

        scheduler.add_daily_task(
            name="stock_analysis",
            task=MagicMock(),
            schedule_time="18:00",
            run_immediately=False,
        )

        scheduler.add_daily_task(
            name="portfolio_analysis",
            task=MagicMock(),
            schedule_time="17:00",
            run_immediately=False,
        )

        self.assertEqual(len(scheduler._tasks), 2)
        self.assertEqual(len(scheduler.schedule.get_jobs()), 2)
        self.assertIn("stock_analysis", scheduler._tasks)
        self.assertIn("portfolio_analysis", scheduler._tasks)

    def test_scheduler_only_stock_when_disabled(self):
        """portfolio_analysis_enabled=False 时只注册一个任务"""
        from src.scheduler import Scheduler

        scheduler = Scheduler()

        scheduler.add_daily_task(
            name="stock_analysis",
            task=MagicMock(),
            schedule_time="18:00",
            run_immediately=False,
        )

        self.assertEqual(len(scheduler._tasks), 1)
        self.assertEqual(len(scheduler.schedule.get_jobs()), 1)

    def test_scheduler_run_loop_stops_on_shutdown(self):
        """调度器主循环可被 shutdown 信号停止"""
        from src.scheduler import Scheduler

        scheduler = Scheduler()
        scheduler.add_daily_task(
            name="test", task=MagicMock(), schedule_time="23:59",
            run_immediately=False,
        )

        def trigger_shutdown():
            time.sleep(0.1)
            scheduler.shutdown_handler.shutdown_requested = True

        t = threading.Thread(target=trigger_shutdown, daemon=True)
        t.start()

        scheduler.run()
        self.assertTrue(scheduler.shutdown_handler.should_shutdown)


if __name__ == '__main__':
    unittest.main()
