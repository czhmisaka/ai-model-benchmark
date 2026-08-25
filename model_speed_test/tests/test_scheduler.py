"""
调度器测试（ScheduleConfig / cron 解析）
覆盖：ONCE 一次性、daily/weekly/monthly、cron 5字段解析、月末 clamp
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime
from src.scheduler import ScheduleConfig, cron_next_run, _monthly_next_run


class TestScheduleConfig:
    """ScheduleConfig.get_next_run_time 测试"""
    
    def test_once_returns_none(self):
        """ONCE 类型应返回 None（执行一次后不再调度）"""
        config = ScheduleConfig(schedule_type="once")
        assert config.get_next_run_time() is None
    
    def test_daily(self):
        """每日：当天已过 → 明天"""
        config = ScheduleConfig(schedule_type="daily", hour=2, minute=0)
        n = config.get_next_run_time(datetime(2026, 8, 25, 10, 0))
        assert n == datetime(2026, 8, 26, 2, 0)
    
    def test_daily_same_day_future(self):
        """每日：当天未到 → 今天"""
        config = ScheduleConfig(schedule_type="daily", hour=2, minute=0)
        n = config.get_next_run_time(datetime(2026, 8, 25, 1, 0))
        assert n == datetime(2026, 8, 25, 2, 0)
    
    def test_weekly(self):
        """每周：下一个匹配的星期几"""
        config = ScheduleConfig(schedule_type="weekly", weekday=0, hour=9, minute=0)
        # 2026-08-25 是周二，下个周一 = 08-31
        n = config.get_next_run_time(datetime(2026, 8, 25, 10, 0))
        assert n == datetime(2026, 8, 31, 9, 0)
    
    def test_monthly_clamp(self):
        """每月：31日在2月 clamp 到月末"""
        n = _monthly_next_run(datetime(2026, 2, 1, 12, 0), day=31, hour=2, minute=0)
        assert n == datetime(2026, 2, 28, 2, 0)
    
    def test_monthly_next_month(self):
        """每月：当天已过 → 下个月"""
        n = _monthly_next_run(datetime(2026, 2, 28, 12, 0), day=15, hour=2, minute=0)
        assert n == datetime(2026, 3, 15, 2, 0)
    
    def test_cron_invalid_returns_none(self):
        """cron 表达式非法 → 返回 None（不抛异常）"""
        config = ScheduleConfig(schedule_type="cron", cron_expression="bad expr")
        assert config.get_next_run_time() is None


class TestCronNextRun:
    """cron_next_run 测试"""
    
    def test_daily_at_2am(self):
        n = cron_next_run("0 2 * * *", datetime(2026, 8, 25, 10, 0))
        assert n == datetime(2026, 8, 26, 2, 0)
    
    def test_every_5_minutes(self):
        n = cron_next_run("*/5 * * * *", datetime(2026, 8, 25, 10, 3))
        assert n == datetime(2026, 8, 25, 10, 5)
    
    def test_weekly_monday(self):
        """cron 周字段：1=周一（cron 语义 0=周日）"""
        n = cron_next_run("0 9 * * 1", datetime(2026, 8, 25, 10, 0))
        assert n == datetime(2026, 8, 31, 9, 0)
    
    def test_range_hours(self):
        n = cron_next_run("30 2-4 * * *", datetime(2026, 8, 25, 10, 0))
        assert n == datetime(2026, 8, 26, 2, 30)
    
    def test_same_day_later_minute(self):
        n = cron_next_run("30 * * * *", datetime(2026, 8, 25, 10, 20))
        assert n == datetime(2026, 8, 25, 10, 30)
    
    def test_sunday_semantics(self):
        """cron 0=周日 应映射到 Python weekday 6"""
        n = cron_next_run("0 8 * * 0", datetime(2026, 8, 25, 10, 0))  # 下个周日 = 8/30
        assert n == datetime(2026, 8, 30, 8, 0)
    
    def test_bad_expression_raises(self):
        with pytest.raises(ValueError):
            cron_next_run("bad", datetime(2026, 8, 25, 10, 0))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
