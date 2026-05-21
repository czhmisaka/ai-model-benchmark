#!/usr/bin/env python3
"""
AI模型速度测试框架 - 主入口
用法: python main.py [--config CONFIG_PATH] [--test-case TEST_CASE_NAME] [--web]
"""
import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional

# 加载 .env 文件
from dotenv import load_dotenv
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ 已加载环境变量: {env_path}")

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.client import ModelClient, StreamChunk
from src.tester import ModelTester, ConcurrentTester
from src.recorder import IORecorder
from src.metrics import MetricsCalculator


def setup_logging(level: str = "INFO"):
    """配置日志系统"""
    # 获取根日志器
    logger = logging.getLogger()
    
    # 清除现有的处理器
    logger.handlers.clear()
    
    # 设置日志级别
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 可选：文件处理器
    log_dir = Path(__file__).parent / "logs"
    if log_dir.exists() or input("是否创建日志文件? (y/n): ").lower() == 'y':
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(
            log_dir / f"test_{Path(__file__).stat().st_mtime:.0f}.log",
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

# Web 模块
from web.emitter import test_emitter
from web.app import app as fastapi_app


def load_config(config_path: str = "config/config.json") -> Dict[str, Any]:
    """加载配置文件 - 从数据库读取 concurrency/output/thresholds"""
    config_file = Path(__file__).parent / config_path
    
    # 首先尝试从JSON文件读取
    config = {}
    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
    
    # 从数据库读取 concurrency、output、thresholds
    import sqlite3
    config_db_path = Path(__file__).parent / "results" / "config.db"
    
    if config_db_path.exists():
        try:
            conn = sqlite3.connect(str(config_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM system_config")
            for row in cursor.fetchall():
                if row["key"] == "concurrency":
                    config["concurrency"] = json.loads(row["value"])
                elif row["key"] == "output":
                    config["output"] = json.loads(row["value"])
                elif row["key"] == "thresholds":
                    config["thresholds"] = json.loads(row["value"])
                elif row["key"] == "test_cases":
                    config["test_cases"] = json.loads(row["value"])
                elif row["key"] == "models":
                    config["models"] = json.loads(row["value"])
            conn.close()
        except Exception as e:
            print(f"从数据库读取配置失败: {e}")
            # 如果数据库读取失败，使用JSON文件中的值
            pass
    
    if not config:
        print(f"配置文件不存在: {config_file}")
        sys.exit(1)
    
    # 调试：打印加载的配置信息
    print(f"✅ 配置加载完成")
    print(f"   - 模型数量: {len(config.get('models', []))}")
    print(f"   - 测试用例数量: {len(config.get('test_cases', []))}")
    
    # 调试：检查是否有测试用例配置了校对功能
    test_cases_with_eval = [tc for tc in config.get('test_cases', []) 
                           if tc.get('eval_model') and tc.get('expected_output')]
    if test_cases_with_eval:
        print(f"   - 需要校对的测试用例数量: {len(test_cases_with_eval)}")
        for tc in test_cases_with_eval:
            print(f"     • {tc.get('name')}: eval_model={tc.get('eval_model')}")
    
    return config


def get_enabled_models(config: Dict[str, Any], model_names: List[str] = None) -> List[Dict]:
    """获取启用的模型列表"""
    models = config.get("models", [])
    enabled_models = []
    
    for model in models:
        # 跳过未启用的模型
        if not model.get("enabled", True):
            continue
        
        # 过滤指定模型
        if model_names and model.get("name") not in model_names:
            continue
        
        enabled_models.append(model)
    
    return enabled_models


def get_enabled_test_cases(config: Dict[str, Any], test_case_ids: List[str] = None) -> List[Dict]:
    """获取启用的测试用例列表"""
    test_cases = config.get("test_cases", [])
    enabled_cases = []
    
    for tc in test_cases:
        # 跳过未启用的测试用例
        if not tc.get("enabled", True):
            continue
        
        # 过滤指定测试用例ID
        if test_case_ids and tc.get("id") not in test_case_ids:
            continue
        
        enabled_cases.append(tc)
    
    return enabled_cases


def get_test_suite_test_cases(config: Dict[str, Any]) -> List[Dict]:
    """根据测试套件配置获取测试用例"""
    test_suite = config.get("test_suite", {})
    enabled_ids = test_suite.get("enabled_test_case_ids", [])
    
    if enabled_ids:
        return get_enabled_test_cases(config, enabled_ids)
    
    # 如果没有配置测试套件，返回所有启用的测试用例
    return get_enabled_test_cases(config)


def create_clients(config: Dict[str, Any], model_names: List[str] = None) -> List[ModelClient]:
    """创建模型客户端
    
    支持两种模式：
    1. 使用原有的 ModelClient（旧版兼容）
    2. 使用新的 Provider 系统（支持多 Provider）
    """
    clients = []
    
    models = get_enabled_models(config, model_names)
    
    for model in models:
        provider = model.get("provider", "openai")
        
        # 尝试使用新的 Provider 系统
        try:
            from src.client_adapter import ProviderAdapter
            adapter = ProviderAdapter(
                name=model["name"],
                provider=provider,
                endpoint=model["endpoint"],
                api_key=model["api_key"],
                model=model["model"],
                temperature=model.get("temperature", 0.7),
                top_p=model.get("top_p", 1.0),
                max_tokens=model.get("max_tokens", 4096),
                presence_penalty=model.get("presence_penalty", 0.0),
                frequency_penalty=model.get("frequency_penalty", 0.0),
                thinking_enabled=model.get("thinking_enabled", True)
            )
            # 将适配器包装为兼容 ModelClient 的接口
            clients.append(adapter)
            print(f"✅ 使用 Provider [{provider}] 创建客户端: {model['name']}")
        except ImportError:
            # 如果 Provider 导入失败，回退到原有的 ModelClient
            print(f"⚠️ Provider [{provider}] 不可用，回退到 ModelClient: {model['name']}")
            client = ModelClient(
                name=model["name"],
                endpoint=model["endpoint"],
                api_key=model["api_key"],
                model=model["model"],
                temperature=model.get("temperature", 0.7),
                top_p=model.get("top_p", 1.0),
                max_tokens=model.get("max_tokens", 4096),
                presence_penalty=model.get("presence_penalty", 0.0),
                frequency_penalty=model.get("frequency_penalty", 0.0),
                thinking_enabled=model.get("thinking_enabled", True)
            )
            clients.append(client)
        except Exception as e:
            # 其他错误，回退到原有的 ModelClient
            print(f"⚠️ Provider [{provider}] 创建失败: {e}，回退到 ModelClient")
            client = ModelClient(
                name=model["name"],
                endpoint=model["endpoint"],
                api_key=model["api_key"],
                model=model["model"],
                temperature=model.get("temperature", 0.7),
                top_p=model.get("top_p", 1.0),
                max_tokens=model.get("max_tokens", 4096),
                presence_penalty=model.get("presence_penalty", 0.0),
                frequency_penalty=model.get("frequency_penalty", 0.0),
                thinking_enabled=model.get("thinking_enabled", True)
            )
            clients.append(client)
    
    return clients


async def run_single_test(
    client: ModelClient,
    recorder: IORecorder,
    test_case: Dict[str, Any],
    rounds: int,
    interval: float
) -> Dict[str, Any]:
    """运行单个测试用例"""
    prompt = test_case.get("prompt")
    messages = test_case.get("messages")
    system_prompt = test_case.get("system_prompt")
    
    test_config = {
        "max_tokens": test_case.get("max_tokens", 500),
        "temperature": test_case.get("temperature", 0.7),
        "stream": test_case.get("stream", True)
    }
    
    print(f"\n{'='*60}")
    print(f"测试用例: {test_case.get('name', '未命名')}")
    print(f"测试类型: {test_case.get('type', 'N/A')}")
    
    if messages:
        print(f"消息数量: {len(messages)}条")
        print(f"最后一条消息: {messages[-1].get('content', '')[:50]}...")
    else:
        print(f"测试Prompt: {prompt[:50] if prompt else 'N/A'}...")
    
    if system_prompt:
        print(f"系统提示词: {system_prompt[:30]}...")
    
    print(f"测试轮次: {rounds}")
    print(f"流式输出: {test_config.get('stream', True)}")
    print(f"{'='*60}\n")
    
    print(f"\n>>> 测试模型: {client.name}")
    
    tester = ModelTester(client, recorder, test_config)
    
    try:
        results = await tester.run_test_rounds(
            prompt=prompt,
            rounds=rounds,
            interval=interval,
            messages=messages,
            system_prompt=system_prompt
        )
        
        # 收集成功的结果
        success_metrics = [r.metrics for r in results if r.success]
        
        if success_metrics:
            aggregated = MetricsCalculator.aggregate_metrics(success_metrics)
            
            print(f"\n[{client.name} - {test_case.get('name', '未命名')} 汇总]:")
            print(f"  首Token时间(TTFT): 平均 {aggregated['ttft']['avg']:.3f}s (最小: {aggregated['ttft']['min']:.3f}s, 最大: {aggregated['ttft']['max']:.3f}s)")
            print(f"  生成时间(TPFT): 平均 {aggregated['tpft']['avg']:.3f}s")
            print(f"  总耗时: 平均 {aggregated['total_time']['avg']:.3f}s")
            print(f"  输出速度: 平均 {aggregated['tokens_per_second']['avg']:.2f} tokens/s")
            
            return {
                "test_case": test_case.get("name", "未命名"),
                "metrics": aggregated,
                "success": True
            }
        else:
            print(f"  所有测试均失败!")
            return {
                "test_case": test_case.get("name", "未命名"),
                "metrics": None,
                "success": False
            }
            
    except Exception as e:
        print(f"  测试出错: {e}")
        return {
            "test_case": test_case.get("name", "未命名"),
            "metrics": None,
            "success": False,
            "error": str(e)
        }


async def run_tests(
    clients: List[ModelClient],
    config: Dict[str, Any],
    test_cases: List[Dict[str, Any]] = None,
    shutdown_event: asyncio.Event = None
):
    """运行测试 - 支持多测试用例遍历"""
    from datetime import datetime
    
    # 测试配置
    conc_config = config.get("concurrency", {})
    rounds = conc_config.get("test_rounds", 10)
    interval = conc_config.get("interval", 1)
    
    # 获取测试用例列表
    if test_cases is None or len(test_cases) == 0:
        test_cases = get_test_suite_test_cases(config)
        if not test_cases:
            test_cases = [{
                "name": "默认测试",
                "prompt": "你好",
                "max_tokens": 500,
                "temperature": 0.7,
                "stream": True,
                "messages": None,
                "system_prompt": None
            }]
    
    # 生成任务标识
    group_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_name = f"{len(clients)}models_{len(test_cases)}cases"
    
    # 初始化记录器
    output_config = config.get("output", {})
    recorder = IORecorder(
        results_dir=output_config.get("results_dir", "results"),
        save_detailed=output_config.get("save_detailed_logs", True),
        group_id=group_id,
        task_name=task_name,
        total_rounds=rounds,
        config={
            "models": [c.name for c in clients],
            "test_cases": [tc.get("name") for tc in test_cases],
            "rounds": rounds
        }
    )
    
    print(f"\n📁 测试记录目录: {recorder.task_dir}")
    
    # 显示总体测试信息
    print(f"\n{'='*60}")
    print(f"AI模型速度测试")
    print(f"{'='*60}")
    print(f"测试用例数量: {len(test_cases)}个")
    print(f"每个测试轮次: {rounds}轮")
    print(f"{'='*60}\n")
    
    all_results = {}
    
    # 遍历每个模型和每个测试用例
    for client in clients:
        client_results = []
        
        for test_case in test_cases:
            result = await run_single_test(
                client, recorder, test_case, rounds, interval
            )
            client_results.append(result)
        
        all_results[client.name] = client_results
        
        # 关闭客户端连接
        try:
            await client.close()
        except Exception as e:
            print(f"  关闭客户端时出错: {e}")
    
    # 输出汇总
    print(f"\n{'='*60}")
    print("最终汇总")
    print(f"{'='*60}")
    
    for model_name, results in all_results.items():
        print(f"\n【{model_name}】")
        
        for result in results:
            test_case_name = result.get("test_case", "未命名")
            print(f"\n  测试用例: {test_case_name}")
            
            if result["success"] and result.get("metrics"):
                stats = result["metrics"]
                print(f"    测试次数: {stats['count']}次")
                print(f"    首Token时间(TTFT): 平均 {stats['ttft']['avg']:.3f}s (最小: {stats['ttft']['min']:.3f}s, 最大: {stats['ttft']['max']:.3f}s)")
                print(f"    生成时间(TPFT): 平均 {stats['tpft']['avg']:.3f}s")
                print(f"    总响应时间: 平均 {stats['total_time']['avg']:.3f}s")
                print(f"    输出速度(吞吐量): 平均 {stats['tokens_per_second']['avg']:.2f} tokens/s")
                print(f"    输出Token数: 平均 {stats['output_tokens']['avg']:.0f}")
            else:
                print(f"    测试失败!")
                if result.get("error"):
                    print(f"    错误: {result['error']}")
    
    # 完成记录
    recorder.finalize()
    
    # 导出CSV
    csv_path = recorder.export_csv()
    if csv_path:
        print(f"\nCSV记录已保存到: {csv_path}")


def list_test_cases(config: Dict[str, Any]):
    """列出所有测试用例"""
    test_cases = config.get("test_cases", [])
    print("\n可用测试用例:")
    for i, tc in enumerate(test_cases):
        status = "✓ 启用" if tc.get("enabled", True) else "✗ 禁用"
        print(f"  {i+1}. {tc.get('name', '未命名')} [{status}]")
        print(f"     ID: {tc.get('id', 'N/A')}")
        print(f"     类型: {tc.get('type', 'N/A')}")
        
        # 处理prompt和messages两种格式
        messages = tc.get("messages")
        prompt = tc.get("prompt")
        
        if messages:
            print(f"     消息数: {len(messages)}条")
            print(f"     最后消息: {messages[-1].get('content', '')[:40]}...")
        elif prompt:
            print(f"     Prompt: {prompt[:50]}...")
        else:
            print(f"     Prompt: N/A")
    print()
    
    # 显示测试套件
    test_suite = config.get("test_suite", {})
    if test_suite:
        print(f"测试套件: {test_suite.get('name', '未命名')}")
        print(f"启用的测试用例: {test_suite.get('enabled_test_case_ids', [])}")
    print()


# 全局变量用于存储客户端列表
_global_clients = []
_global_web_server = None


async def cleanup_clients():
    """清理所有客户端连接"""
    for client in _global_clients:
        try:
            if client._session and not client._session.closed:
                await client._session.close()
        except Exception:
            pass
    _global_clients.clear()


def signal_handler(signum, frame):
    """处理中断信号"""
    print("\n\n检测到中断信号，正在清理资源...")
    # 创建异步任务来清理
    try:
        asyncio.create_task(cleanup_clients())
    except RuntimeError:
        # 如果不在异步上下文中，直接清理
        pass
    sys.exit(0)


# ===== Web 模式测试运行 =====
class WebAwareTester:
    """支持 Web 推送的测试运行器"""
    
    def __init__(
        self, 
        enable_web: bool = True, 
        group_id: str = None, 
        stop_event: asyncio.Event = None, 
        timeout: float = 300.0,
        eval_model_config: Dict[str, Any] = None
    ):
        self.enable_web = enable_web
        self.group_id = group_id
        self.stop_event = stop_event
        self.timeout = timeout  # 超时时间（秒），默认300秒
        self.eval_model_config = eval_model_config  # 校对模型配置
    
    def should_stop(self) -> bool:
        """检查是否应该停止"""
        if self.stop_event and self.stop_event.is_set():
            return True
        # 也检查全局的 _test_running 标志
        try:
            from web.app import _test_running
            if not _test_running:
                return True
        except:
            pass
        return False
    
    async def run_single_test_with_events(
        self,
        client: ModelClient,
        recorder: IORecorder,
        test_case: Dict[str, Any],
        rounds: int,
        interval: float
    ):
        """运行单个测试用例并推送事件"""
        prompt = test_case.get("prompt")
        messages = test_case.get("messages")
        system_prompt = test_case.get("system_prompt")
        test_case_name = test_case.get("name", "未命名")
        
        # 获取校对相关配置
        eval_model = test_case.get("eval_model")  # 校对模型名称
        expected_output = test_case.get("expected_output")  # 标准答案
        
        # 检查是否需要校对
        needs_verification = bool(eval_model and expected_output)
        if needs_verification:
            print(f"📋 校对配置: eval_model={eval_model}, expected_output已配置")
        
        test_config = {
            "max_tokens": test_case.get("max_tokens", 500),
            "temperature": test_case.get("temperature", 0.7),
            "stream": test_case.get("stream", True)
        }
        
        # 推送测试开始
        if self.enable_web:
            await test_emitter.emit_progress(
                model_name=client.name,
                test_case_name=test_case_name,
                current_round=1,
                total_rounds=rounds,
                status="starting"
            )
        
        print(f"\n>>> 测试模型: {client.name}")
        print(f"测试用例: {test_case_name}")
        if needs_verification:
            print(f"📋 需要校对验证")
        
        # 确定用于显示的 prompt
        display_prompt = prompt or (messages[-1]["content"] if messages else "")
        
        # 发送进度事件（包含 prompt）
        if self.enable_web:
            await test_emitter.emit_progress(
                model_name=client.name,
                test_case_name=test_case_name,
                current_round=1,
                total_rounds=rounds,
                status="running",
                prompt=display_prompt
            )
        
        tester = ModelTester(client, recorder, test_config, timeout=self.timeout)
        
        # 自定义流式处理来推送事件
        if test_config.get("stream", True):
            result = await self._run_stream_test_with_events(
                tester, client.name, display_prompt, 
                messages, system_prompt, rounds, interval, test_case_name,
                eval_model=eval_model, expected_output=expected_output,
                test_case=test_case
            )
        else:
            result = await tester.run_test_rounds(
                prompt=prompt,
                rounds=rounds,
                interval=interval,
                messages=messages,
                system_prompt=system_prompt
            )
        
        return result
    
    async def _run_stream_test_with_events(
        self,
        tester: ModelTester,
        model_name: str,
        display_prompt: str,
        messages: list,
        system_prompt: str,
        rounds: int,
        interval: float,
        test_case_name: str,
        eval_model: str = None,
        expected_output: str = None,
        test_case: Dict[str, Any] = None
    ):
        """流式测试并推送事件（带超时控制，支持多步骤 follow-up）"""
        results = []
        
        # 检查是否需要校对
        needs_verification = bool(eval_model and expected_output)
        eval_client = None
        
        # 检查是否为多步骤测试用例
        follow_up_questions = None
        if test_case:
            metadata = test_case.get("metadata", {})
            follow_up_questions = metadata.get("follow_up_questions", [])
            if follow_up_questions:
                print(f"[{model_name}] 📋 检测到多步骤测试: {len(follow_up_questions)}个跟进问题")
        
        # 如果需要校对，创建校对客户端
        if needs_verification and self.eval_model_config:
            try:
                # 从模型列表中找到校对模型对应的配置
                eval_model_cfg = None
                models_list = self.eval_model_config.get("models", [])
                for m in models_list:
                    if m.get("name") == eval_model:
                        eval_model_cfg = m
                        break

                if eval_model_cfg:
                    eval_provider = eval_model_cfg.get("provider", "openai")
                    try:
                        # 尝试使用 ProviderAdapter
                        from src.client_adapter import ProviderAdapter
                        eval_client = ProviderAdapter(
                            name=eval_model,
                            provider=eval_provider,
                            endpoint=eval_model_cfg.get("endpoint"),
                            api_key=eval_model_cfg.get("api_key"),
                            model=eval_model_cfg.get("model", ""),
                            temperature=0.3,  # 校对时使用较低温度
                            top_p=1.0,
                            max_tokens=2048,
                            presence_penalty=0.0,
                            frequency_penalty=0.0,
                            thinking_enabled=False  # 校对时禁用思考
                        )
                        print(f"✅ 已创建校对客户端: {eval_model} (provider={eval_provider})")
                    except (ValueError, ImportError) as adapter_err:
                        # ProviderAdapter 失败时，回退到使用 ModelClient
                        print(f"⚠️ ProviderAdapter 创建失败 ({adapter_err})，回退到 ModelClient")
                        try:
                            from src.client import ModelClient
                            eval_client = ModelClient(
                                name=eval_model,
                                endpoint=eval_model_cfg.get("endpoint"),
                                api_key=eval_model_cfg.get("api_key"),
                                model=eval_model_cfg.get("model", eval_model),
                                temperature=0.3,
                                top_p=1.0,
                                max_tokens=2048,
                                presence_penalty=0.0,
                                frequency_penalty=0.0,
                                thinking_enabled=False
                            )
                            print(f"✅ 已创建校对客户端 (ModelClient): {eval_model}")
                        except Exception as model_err:
                            print(f"⚠️ ModelClient 创建也失败: {model_err}")
                            eval_client = None
                else:
                    print(f"⚠️ 未找到校对模型配置: {eval_model}，尝试使用默认配置")
                    # 如果没找到，尝试使用第一个模型作为校对模型
                    if models_list:
                        eval_model_cfg = models_list[0]
                        eval_provider = eval_model_cfg.get("provider", "openai")
                        try:
                            from src.client_adapter import ProviderAdapter
                            eval_client = ProviderAdapter(
                                name=eval_model,
                                provider=eval_provider,
                                endpoint=eval_model_cfg.get("endpoint"),
                                api_key=eval_model_cfg.get("api_key"),
                                model=eval_model_cfg.get("model", ""),
                                temperature=0.3,
                                top_p=1.0,
                                max_tokens=2048,
                                presence_penalty=0.0,
                                frequency_penalty=0.0,
                                thinking_enabled=False
                            )
                            print(f"✅ 使用默认模型 {eval_model_cfg.get('name')} 作为校对模型")
                        except (ValueError, ImportError):
                            print(f"⚠️ ProviderAdapter 创建失败，回退到 ModelClient")
                            try:
                                from src.client import ModelClient
                                eval_client = ModelClient(
                                    name=eval_model,
                                    endpoint=eval_model_cfg.get("endpoint"),
                                    api_key=eval_model_cfg.get("api_key"),
                                    model=eval_model_cfg.get("model", eval_model_cfg.get("name")),
                                    temperature=0.3,
                                    top_p=1.0,
                                    max_tokens=2048,
                                    presence_penalty=0.0,
                                    frequency_penalty=0.0,
                                    thinking_enabled=False
                                )
                                print(f"✅ 使用默认模型 {eval_model_cfg.get('name')} 作为校对模型 (ModelClient)")
                            except Exception as model_err:
                                print(f"⚠️ ModelClient 创建也失败: {model_err}")
                                eval_client = None
                        except Exception as e:
                            print(f"⚠️ 创建校对客户端失败: {e}")
                            eval_client = None
            except Exception as e:
                print(f"⚠️ 创建校对客户端失败: {e}")
                eval_client = None
        elif needs_verification and self.eval_manager:
            # 使用评估管理器中的客户端
            eval_client = self.eval_manager.eval_client
        
        for i in range(rounds):
            # 检查是否收到停止信号
            if self.should_stop():
                print(f"[{model_name}] 收到停止信号，停止测试...")
                break
            
            # 推送进度
            if self.enable_web:
                await test_emitter.emit_progress(
                    model_name=model_name,
                    test_case_name=test_case_name,
                    current_round=i + 1,
                    total_rounds=rounds,
                    status="running",
                    prompt=display_prompt
                )
            
            print(f"[{model_name}] 第 {i+1}/{rounds} 轮测试...")
            
            # 开始计时
            start_time = asyncio.get_event_loop().time()
            full_content = ""
            think_content_str = ""
            answer_content_str = ""
            first_token_time = None
            stream_completed = False

            try:
                # 使用 asyncio.wait_for 添加超时控制
                async def stream_with_timeout():
                    nonlocal full_content, think_content_str, answer_content_str, first_token_time, stream_completed
                    try:
                        async for chunk in tester.client.chat_stream(
                            prompt=None,
                            max_tokens=tester.test_config.get("max_tokens", 500),
                            temperature=tester.test_config.get("temperature", 0.7),
                            messages=messages,
                            system_prompt=system_prompt
                        ):
                            # 检查是否收到停止信号（在每个 chunk 后检查）
                            if self.should_stop():
                                print(f"[{model_name}] 收到停止信号，正在中断...")
                                break

                            # 记录首 token 时间
                            current_time = asyncio.get_event_loop().time()
                            if first_token_time is None:
                                first_token_time = current_time - start_time

                            full_content += chunk.content

                            # 分离 think 和 answer 内容
                            if chunk.is_think:
                                think_content_str += chunk.content
                            else:
                                answer_content_str += chunk.content

                            # 推送流式块（包含轮次信息）
                            if self.enable_web:
                                await test_emitter.emit_chunk(
                                    content=chunk.content,
                                    is_first=chunk.is_first,
                                    model_name=model_name,
                                    test_case_name=test_case_name,
                                    current_round=i + 1,
                                    total_rounds=rounds
                                )
                    except Exception as stream_err:
                        # 记录流式处理中的错误，但仍然标记为完成
                        print(f"[{model_name}] 流式处理错误: {stream_err}")
                    finally:
                        # 关键修复：无论是否出错，都要标记流式处理已完成
                        # 这样 emit_complete 一定会被调用
                        stream_completed = True
                
                # 等待流式请求完成或超时
                await asyncio.wait_for(stream_with_timeout(), timeout=self.timeout)
                
                # 检查是否因停止信号中断
                if self.should_stop():
                    print(f"[{model_name}] 收到停止信号，正在中断...")
                    # 记录中断结果
                    error_metrics_dict = {
                        "ttft_seconds": 0,
                        "tpft_seconds": 0,
                        "total_time_seconds": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "tokens_per_second": 0,
                        "error": "Test interrupted by user"
                    }
                    if self.enable_web:
                        await test_emitter.emit_complete(
                            model_name=model_name,
                            test_case_name=test_case_name,
                            current_round=i + 1,
                            total_rounds=rounds,
                            metrics=error_metrics_dict,
                            success=False,
                            group_id=self.group_id,
                            prompt=display_prompt,
                            response="Test interrupted",
                            think_content=think_content_str,
                            answer_content=answer_content_str
                        )
                    result = type('TestResult', (), {
                        'success': False,
                        'model_name': model_name,
                        'metrics': None,
                        'error': 'Test interrupted',
                        'prompt': display_prompt
                    })()
                    results.append(result)
                    break
                
                if not stream_completed:
                    # 超时了
                    raise asyncio.TimeoutError(f"Request timeout ({self.timeout}s)")
                
                # 计算指标
                end_time = asyncio.get_event_loop().time()
                from src.metrics import TestMetrics, count_tokens, estimate_input_tokens
                
                metrics = TestMetrics()
                metrics.ttft = first_token_time or 0
                metrics.total_time = end_time - start_time
                metrics.tpft = max(0, metrics.total_time - metrics.ttft)
                
                # 使用 tiktoken 精确计算 output_tokens
                metrics.output_tokens = count_tokens(full_content)
                
                # 估算 input_tokens（使用 display_prompt 作为 prompt）
                if messages:
                    metrics.input_tokens = estimate_input_tokens(messages, system_prompt)
                elif display_prompt:
                    metrics.input_tokens = count_tokens(display_prompt)
                # tokens_per_second 是只读属性，会自动计算
                
                # 检查输出是否为空或过短，如果是则标记为失败
                is_output_valid = len(full_content.strip()) > 0 and metrics.output_tokens > 0
                
                if not is_output_valid:
                    print(f"  ⚠️ 输出为空或无效，标记为失败")
                    if self.enable_web:
                        error_metrics_dict = {
                            "ttft_seconds": metrics.ttft,
                            "tpft_seconds": metrics.tpft,
                            "total_time_seconds": metrics.total_time,
                            "input_tokens": metrics.input_tokens,
                            "output_tokens": metrics.output_tokens,
                            "tokens_per_second": 0,
                            "error": "Empty or invalid output"
                        }
                        await test_emitter.emit_complete(
                            model_name=model_name,
                            test_case_name=test_case_name,
                            current_round=i + 1,
                            total_rounds=rounds,
                            metrics=error_metrics_dict,
                            success=False,
                            group_id=self.group_id,
                            prompt=display_prompt,
                            response=full_content or "No output",
                            think_content=think_content_str,
                            answer_content=answer_content_str
                        )
                    result = type('TestResult', (), {
                        'success': False,
                        'model_name': model_name,
                        'metrics': metrics,
                        'error': 'Empty or invalid output',
                        'prompt': display_prompt
                    })()
                    results.append(result)
                    
                    # 记录到 recorder
                    if hasattr(tester, 'recorder') and tester.recorder:
                        tester.recorder.record(
                            model_name=model_name,
                            prompt=display_prompt,
                            response=full_content or "No output",
                            metrics=error_metrics_dict,
                            metadata={"test_type": "stream", "test_case": test_case_name, "round": i + 1, "error": "Empty output"}
                        )
                    continue
                
                # 记录结果
                result = type('TestResult', (), {
                    'success': True,
                    'model_name': model_name,
                    'metrics': metrics,
                    'response_content': full_content,
                    'prompt': display_prompt
                })()
                results.append(result)
                
                # 保存到记录器（修复：添加 recorder 调用以保存输出内容到文件）
                if hasattr(tester, 'recorder') and tester.recorder:
                    tester.recorder.record(
                        model_name=model_name,
                        prompt=display_prompt,
                        response=full_content,
                        metrics=metrics.to_dict(),
                        metadata={"test_type": "stream", "test_case": test_case_name, "round": i + 1}
                    )
                
                # 打印进度
                output_speed = metrics.tokens_per_second if metrics.tpft > 0 else 0
                print(f"  TTFT: {metrics.ttft:.3f}s, TPFT: {metrics.tpft:.3f}s, "
                      f"总耗时: {metrics.total_time:.3f}s, 输出Token: {metrics.output_tokens}, "
                      f"速度: {output_speed:.2f} tokens/s")
                
                # 校对验证（如果配置了）
                evaluation_result = None
                if needs_verification and eval_client:
                    try:
                        from src.evaluation_service import EvaluationService
                        eval_service = EvaluationService(eval_client)
                        print(f"  📋 正在进行校对验证...")
                        evaluation_result = await eval_service.verify(
                            prompt=display_prompt,
                            model_output=full_content,
                            golden_answer=expected_output
                        )
                        if evaluation_result:
                            is_correct = evaluation_result.get("is_correct", False)
                            rate = evaluation_result.get("rate", 0)
                            reason = evaluation_result.get("reason", "")
                            print(f"  📋 校对结果: {'✅ 正确' if is_correct else '❌ 不正确'}, 评分: {rate}/10")
                            if reason:
                                print(f"  📋 评价: {reason[:100]}...")
                        else:
                            print(f"  ⚠️ 校对失败，未获取到结果")
                    except Exception as eval_err:
                        print(f"  ⚠️ 校对失败: {eval_err}")
                        evaluation_result = {
                            "is_correct": False,
                            "rate": 0,
                            "reason": f"校对异常: {str(eval_err)}"
                        }
                
                # 推送完成事件
                if self.enable_web:
                    await test_emitter.emit_complete(
                        model_name=model_name,
                        test_case_name=test_case_name,
                        current_round=i + 1,
                        total_rounds=rounds,
                        metrics=metrics.to_dict(),
                        success=True,
                        group_id=self.group_id,
                        prompt=display_prompt,
                        response=full_content,
                        evaluation=evaluation_result,
                        think_content=think_content_str,
                        answer_content=answer_content_str
                    )
                    
            except Exception as e:
                print(f"  错误: {e}")
                error_msg = str(e)
                
                if self.enable_web:
                    # 发送错误事件（显示 toast 通知）
                    await test_emitter.emit_error(error_msg, model_name)
                    
                    # 关键修复：发送 complete 事件标记该轮次已完成（失败）
                    # 这样前端会更新轮次状态为 error，并检查是否全部完成
                    error_metrics = {
                        "ttft_seconds": 0,
                        "tpft_seconds": 0,
                        "total_time_seconds": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "tokens_per_second": 0,
                        "error": error_msg
                    }
                    await test_emitter.emit_complete(
                        model_name=model_name,
                        test_case_name=test_case_name,
                        current_round=i + 1,
                        total_rounds=rounds,
                        metrics=error_metrics,
                        success=False,  # 标记为失败
                        group_id=self.group_id,
                        prompt=display_prompt,
                        response=f"Error: {error_msg}",
                        think_content=think_content_str,
                        answer_content=answer_content_str
                    )
                
                # 记录失败结果到 recorder（保存到文件）
                if hasattr(tester, 'recorder') and tester.recorder:
                    error_metrics = {
                        "ttft_seconds": 0,
                        "tpft_seconds": 0,
                        "total_time_seconds": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "tokens_per_second": 0,
                        "error": error_msg
                    }
                    tester.recorder.record(
                        model_name=model_name,
                        prompt=display_prompt,
                        response=f"Error: {error_msg}",
                        metrics=error_metrics,
                        metadata={"test_type": "stream", "test_case": test_case_name, "round": i + 1, "error": error_msg}
                    )
                
                # 记录失败结果
                result = type('TestResult', (), {
                    'success': False,
                    'model_name': model_name,
                    'metrics': None,
                    'error': error_msg,
                    'prompt': display_prompt
                })()
                results.append(result)
            
            # 间隔 - 也检查停止信号
            if i < rounds - 1 and interval > 0:
                # 分多次等待，以便能及时响应停止信号
                for _ in range(int(interval * 10)):
                    if self.should_stop():
                        break
                    await asyncio.sleep(0.1)
        
        return results


async def run_concurrent_tests(
    clients: List[ModelClient],
    config: Dict[str, Any],
    test_cases: List[Dict[str, Any]] = None
):
    """运行增强的并发测试 - 多模型+多轮并发"""
    from src.tester import ConcurrentTester
    from datetime import datetime
    
    conc_config = config.get("concurrency", {})
    max_concurrent = conc_config.get("max_concurrent", 3)
    rounds = conc_config.get("test_rounds", 10)
    interval = conc_config.get("interval", 1)
    
    # 获取测试用例
    if not test_cases:
        test_cases = get_test_suite_test_cases(config)
    
    # 生成任务标识
    group_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_name = f"{len(clients)}models_{len(test_cases)}cases"
    
    # 初始化记录器
    output_config = config.get("output", {})
    recorder = IORecorder(
        results_dir=output_config.get("results_dir", "results"),
        save_detailed=output_config.get("save_detailed_logs", True),
        group_id=group_id,
        task_name=task_name,
        total_rounds=rounds,
        config={
            "models": [c.name for c in clients],
            "test_cases": [tc.get("name") for tc in test_cases],
            "rounds": rounds,
            "concurrency": max_concurrent
        }
    )
    
    print(f"\n{'='*60}")
    print(f"AI模型速度测试 (增强并发模式)")
    print(f"{'='*60}")
    print(f"📁 测试记录目录: {recorder.task_dir}")
    print(f"模型数量: {len(clients)}个")
    print(f"每轮并发数: {max_concurrent}")
    print(f"测试轮次: {rounds}")
    print(f"每轮间隔: {interval}s")
    print(f"{'='*60}\n")
    
    # 为每个测试用例创建并发测试
    for test_case in test_cases:
        prompt = test_case.get("prompt")
        messages = test_case.get("messages")
        system_prompt = test_case.get("system_prompt")
        display_prompt = prompt or (messages[-1]["content"] if messages else "测试")
        
        test_config = {
            "max_tokens": test_case.get("max_tokens", 500),
            "temperature": test_case.get("temperature", 0.7),
            "stream": test_case.get("stream", True)
        }
        
        print(f"\n>>> 测试用例: {test_case.get('name', '未命名')}")
        print(f"    Prompt: {display_prompt[:50]}...")
        
        # 创建增强的并发测试器
        tester = ConcurrentTester(clients, recorder, test_config)
        
        # 运行增强的并发测试（多模型+多轮并发）
        results = await tester.run_concurrent_test(
            prompt=display_prompt,
            concurrency=max_concurrent,
            rounds=rounds,
            interval=interval,
            messages=messages,
            system_prompt=system_prompt
        )
        
        # 输出汇总结果
        print(f"\n{'='*60}")
        print("测试汇总")
        print(f"{'='*60}")
        
        for model_name, model_results in results.items():
            success_count = sum(1 for r in model_results if r.success)
            print(f"\n【{model_name}】成功: {success_count}/{len(model_results)}")
            
            if success_count > 0:
                success_metrics = [r.metrics for r in model_results if r.success]
                if success_metrics:
                    aggregated = MetricsCalculator.aggregate_metrics(success_metrics)
                    print(f"  TTFT: 平均 {aggregated['ttft']['avg']:.3f}s (最小: {aggregated['ttft']['min']:.3f}s, 最大: {aggregated['ttft']['max']:.3f}s)")
                    print(f"  TPFT: 平均 {aggregated['tpft']['avg']:.3f}s")
                    print(f"  总耗时: 平均 {aggregated['total_time']['avg']:.3f}s")
                    print(f"  吞吐量: 平均 {aggregated['tokens_per_second']['avg']:.2f} tokens/s")
                    print(f"  输出Token: 平均 {aggregated['output_tokens']['avg']:.0f}")
            else:
                print(f"  所有测试均失败!")
    
    # 关闭所有客户端
    for client in clients:
        try:
            await client.close()
        except Exception as e:
            print(f"关闭客户端时出错: {e}")
    
    print(f"\n{'='*60}")
    print("增强并发测试完成")
    print(f"{'='*60}")
    
    # 完成记录
    recorder.finalize()


async def run_tests_with_web(
    clients: List[ModelClient],
    config: Dict[str, Any],
    test_cases: List[Dict[str, Any]] = None,
    enable_web: bool = True,
    stop_event: asyncio.Event = None
):
    """运行测试 - 支持 Web 推送"""
    from datetime import datetime
    
    # 测试配置
    conc_config = config.get("concurrency", {})
    rounds = conc_config.get("test_rounds", 10)
    interval = conc_config.get("interval", 1)
    max_concurrent = conc_config.get("max_concurrent", 3)
    
    # 获取测试用例列表
    if test_cases is None or len(test_cases) == 0:
        test_cases = get_test_suite_test_cases(config)
        if not test_cases:
            test_cases = [{
                "name": "默认测试",
                "prompt": "你好",
                "max_tokens": 500,
                "temperature": 0.7,
                "stream": True,
                "messages": None,
                "system_prompt": None
            }]
    
    # 用于存储 group_id
    group_id = None
    
    # 重置发射器
    if enable_web:
        test_emitter.reset()
        test_emitter.set_current_test({
            "models": [c.name for c in clients],
            "test_cases": test_cases
        })
        start_config = {
            "models": [c.name for c in clients],
            "test_cases": [tc.get("name") for tc in test_cases],
            "total_rounds": rounds
        }
        # emit_start 现在返回 group_id
        group_id = await test_emitter.emit_start(start_config)
    
    # 生成任务标识
    task_group_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_name = f"{len(clients)}models_{len(test_cases)}cases"
    
    # 检查是否收到停止信号
    def should_stop() -> bool:
        if stop_event and stop_event.is_set():
            return True
        # 也检查全局的 _test_running 标志
        from web.app import _test_running
        if not _test_running:
            return True
        return False
    
    # 初始化记录器
    output_config = config.get("output", {})
    recorder = IORecorder(
        results_dir=output_config.get("results_dir", "results"),
        save_detailed=output_config.get("save_detailed_logs", True),
        group_id=task_group_id,
        task_name=task_name,
        total_rounds=rounds,
        config={
            "models": [c.name for c in clients],
            "test_cases": [tc.get("name") for tc in test_cases],
            "rounds": rounds,
            "concurrency": max_concurrent
        }
    )
    
    print(f"\n{'='*60}")
    print(f"AI模型速度测试 (Web模式)")
    print(f"{'='*60}")
    print(f"📁 测试记录目录: {recorder.task_dir}")
    print(f"测试用例数量: {len(test_cases)}个")
    print(f"每个测试轮次: {rounds}轮")
    if enable_web:
        print(f"Web界面: http://localhost:15010")
    print(f"{'='*60}\n")
    
    # 获取模型配置列表（包含所有模型的配置，用于校对时查找）
    models_config = config.get("models", [])
    
    # 传递模型列表配置，以便 WebAwareTester 能根据 eval_model 名称找到对应配置
    web_tester = WebAwareTester(
        enable_web=enable_web, 
        group_id=group_id, 
        stop_event=stop_event,
        eval_model_config={"models": models_config}  # 传递模型列表供校对时查找
    )

    # 获取最大并发数
    max_concurrent = conc_config.get("max_concurrent", 3)
    
    # 遍历每个模型，并发执行所有测试用例
    for client in clients:
        client_results = []
        
        # 为每个测试用例创建独立的客户端
        async def run_test_case(test_case, client_model):
            # 为每个测试用例创建新的客户端
            test_client = ModelClient(
                name=client_model["name"],
                endpoint=client_model["endpoint"],
                api_key=client_model["api_key"],
                model=client_model["model"],
                temperature=client_model.get("temperature", 0.7),
                top_p=client_model.get("top_p", 1.0),
                max_tokens=client_model.get("max_tokens", 4096),
                presence_penalty=client_model.get("presence_penalty", 0.0),
                frequency_penalty=client_model.get("frequency_penalty", 0.0),
                thinking_enabled=client_model.get("thinking_enabled", True)
            )
            try:
                if enable_web:
                    # 传递 test_case 中的校对配置（eval_model 名称）给 web_tester
                    results = await web_tester.run_single_test_with_events(
                        test_client, recorder, test_case, rounds, interval
                    )
                else:
                    result = await run_single_test(
                        test_client, recorder, test_case, rounds, interval
                    )
                    results = [result]
                return results
            finally:
                # 确保关闭客户端
                try:
                    await test_client.close()
                except:
                    pass
        
        # 获取客户端的模型配置
        client_model = None
        for m in config.get("models", []):
            if m.get("name") == client.name:
                client_model = m
                break
        
        if not client_model:
            continue
        
        # 使用 asyncio.gather 并发执行所有测试用例
        tasks = [run_test_case(tc, client_model) for tc in test_cases]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 收集结果
        for results in results_list:
            if isinstance(results, Exception):
                print(f"测试执行出错: {results}")
            else:
                client_results.extend(results)
        
        all_results[client.name] = client_results
        
        # 关闭原始客户端
        try:
            await client.close()
        except Exception as e:
            print(f"关闭客户端时出错: {e}")
    
    # 输出汇总
    print(f"\n{'='*60}")
    print("最终汇总")
    print(f"{'='*60}")
    
    for model_name, results in all_results.items():
        print(f"\n【{model_name}】")
        
        success_metrics = [r.metrics for r in results if hasattr(r, 'success') and r.success and r.metrics]
        
        if success_metrics:
            from src.metrics import MetricsCalculator
            aggregated = MetricsCalculator.aggregate_metrics(success_metrics)
            
            print(f"  测试次数: {aggregated['count']}次")
            print(f"  首Token时间(TTFT): 平均 {aggregated['ttft']['avg']:.3f}s")
            print(f"  生成时间(TPFT): 平均 {aggregated['tpft']['avg']:.3f}s")
            print(f"  输出速度: 平均 {aggregated['tokens_per_second']['avg']:.2f} tokens/s")
    
    # 推送汇总
    if enable_web:
        await test_emitter.emit_summary(group_id=group_id)
    
    # 保存汇总结果
    summary_file = Path(output_config.get("results_dir", "results")) / "summary.json"
    serializable_results = {}
    for model_name, results in all_results.items():
        serializable_results[model_name] = []
        for result in results:
            metrics = getattr(result, 'metrics', None)
            # 将 TestMetrics 转换为字典
            if metrics is not None and hasattr(metrics, 'to_dict'):
                metrics = metrics.to_dict()
            serializable_results[model_name].append({
                "success": getattr(result, 'success', False),
                "metrics": metrics,
                "error": getattr(result, 'error', None)
            })
    
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(serializable_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n汇总结果已保存到: {summary_file}")
    
    # 完成记录
    recorder.finalize()


def start_web_server(port: int = 15010):
    """在后台线程启动 Web 服务器"""
    import uvicorn
    from web.app import app
    
    def run():
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def main():
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    parser = argparse.ArgumentParser(description="AI模型速度测试框架")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别 (默认: INFO)"
    )
    parser.add_argument(
        "--config", 
        default="config/config.json",
        help="配置文件路径"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        help="指定要测试的模型名称"
    )
    parser.add_argument(
        "--test-case",
        dest="test_case",
        help="指定测试用例名称"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有测试用例"
    )
    parser.add_argument(
        "--concurrent",
        action="store_true",
        default=True,
        help="运行并发测试模式 (默认启用)"
    )
    parser.add_argument(
        "--no-concurrent",
        action="store_true",
        help="禁用并发测试模式，使用顺序测试"
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="启动Web可视化界面"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=15010,
        help="Web服务端口号 (默认: 15010)"
    )
    parser.add_argument(
        "--no-web",
        action="store_true",
        help="不启动Web界面（即使使用--web模式）"
    )
    
    args = parser.parse_args()
    
    # 配置日志
    log_level = args.log_level or os.environ.get("LOG_LEVEL", "INFO")
    logger = setup_logging(log_level)
    logger.info(f"日志级别: {log_level}")
    
    # 加载配置
    config = load_config(args.config)
    
    # 列出测试用例
    if args.list:
        list_test_cases(config)
        return
    
    # 获取测试用例列表
    test_cases = None
    if args.test_case:
        # 支持按名称或ID查找单个测试用例
        for tc in config.get("test_cases", []):
            if tc.get("name") == args.test_case or tc.get("id") == args.test_case:
                test_cases = [tc]
                break
        if test_cases is None:
            print(f"未找到测试用例: {args.test_case}")
            list_test_cases(config)
            sys.exit(1)
    else:
        # 如果没有指定测试用例，使用测试套件中的所有测试用例
        test_cases = get_test_suite_test_cases(config)
        print(f"将运行测试套件中的 {len(test_cases)} 个测试用例")
    
    # 创建客户端
    clients = create_clients(config, args.models)
    
    # 保存到全局变量以便信号处理时访问
    global _global_clients
    _global_clients = clients
    
    if not clients:
        print("没有找到可用的模型客户端!")
        sys.exit(1)
    
    print(f"将测试 {len(clients)} 个模型: {[c.name for c in clients]}")
    
    # 启动 Web 服务器
    if args.web and not args.no_web:
        print(f"\n🚀 启动Web服务器: http://localhost:{args.port}")
        web_thread = start_web_server(port=args.port)
    
    # 运行测试（并发模式默认启用）
    use_concurrent = args.concurrent and not args.no_concurrent
    
    if use_concurrent:
        # 并发测试模式 - 使用 asyncio.run 执行
        asyncio.run(run_concurrent_tests(clients, config, test_cases))
    else:
        if args.web and not args.no_web:
            asyncio.run(run_tests_with_web(clients, config, test_cases, enable_web=True))
        else:
            asyncio.run(run_tests(clients, config, test_cases))


if __name__ == "__main__":
    main()
