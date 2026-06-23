"""
多模态适配冒烟脚本

不依赖外部 API，专门验证 commit 956dae8 引入的多模态代码层：
  - ContentPart / MessageContent 类型
  - normalize_content / has_image_parts / extract_text_for_log 辅助函数
  - BaseLLMProvider.supports_vision / validate_vision_capability 入口校验

可作为离线回归测试快速跑通。涉及网络的部分用环境变量启用：
  SMOKE_LIVE=1 时调用 BaseLLMProvider 真实校验路径

退出码：0 通过 / 1 失败
"""
import asyncio
import os
import sys
from pathlib import Path

# 允许从项目根目录直接运行
PROJECT_ROOT = Path(__file__).resolve().parent.parent / "model_speed_test"
sys.path.insert(0, str(PROJECT_ROOT))


# ====== 纯函数层冒烟 ======

def test_normalize_content():
    from src.providers.base import normalize_content

    # None
    assert normalize_content(None) == [{"type": "text", "text": ""}]
    # str
    assert normalize_content("hello") == [{"type": "text", "text": "hello"}]
    # list 原样返回
    parts = [{"type": "text", "text": "x"}, {"type": "image_url", "image_url": {"url": "http://a"}}]
    assert normalize_content(parts) is parts
    # 其他类型兜底
    assert normalize_content(123) == [{"type": "text", "text": "123"}]
    print("  ✓ normalize_content")


def test_has_image_parts():
    from src.providers.base import has_image_parts

    assert has_image_parts("纯文本") is False
    assert has_image_parts(None) is False
    assert has_image_parts([{"type": "text", "text": "no image"}]) is False
    assert has_image_parts([{"type": "image_url", "image_url": {"url": "http://a"}}]) is True
    # Anthropic 风格 image + source
    assert has_image_parts([{"type": "image", "source": {"type": "base64", "data": "..."}}]) is True
    # 混合
    mixed = [
        {"type": "text", "text": "看图"},
        {"type": "image_url", "image_url": {"url": "http://a"}},
    ]
    assert has_image_parts(mixed) is True
    print("  ✓ has_image_parts")


def test_extract_text_for_log():
    from src.providers.base import extract_text_for_log

    assert extract_text_for_log("hello world") == "hello world"
    assert extract_text_for_log(None) == ""
    assert extract_text_for_log([
        {"type": "text", "text": "前 "},
        {"type": "image_url", "image_url": {"url": "http://x"}},
        {"type": "text", "text": "后"},
    ]) == "前 后"
    print("  ✓ extract_text_for_log")


def test_content_part_roundtrip():
    from src.providers.base import ContentPart

    p1 = ContentPart(type="text", text="hi")
    assert p1.to_dict() == {"type": "text", "text": "hi"}

    p2 = ContentPart(type="image_url", image_url={"url": "http://a"})
    assert p2.to_dict() == {"type": "image_url", "image_url": {"url": "http://a"}}

    # 从 dict 反序列化
    p3 = ContentPart.from_dict({"type": "text", "text": "x"})
    assert p3.type == "text" and p3.text == "x"

    p4 = ContentPart.from_dict({"type": "image_url", "image_url": {"url": "http://b"}})
    assert p4.type == "image_url" and p4.image_url == {"url": "http://b"}

    # 非 dict 输入兜底
    p5 = ContentPart.from_dict("bad input")  # type: ignore[arg-type]
    assert p5.type == "text" and p5.text == "bad input"
    print("  ✓ ContentPart to_dict / from_dict")


def test_message_content_compat():
    """Message.content 兼容 str 与 list 两种形态（向后兼容旧数据）"""
    from src.providers.base import Message

    # 旧数据：str
    m1 = Message(role="user", content="legacy prompt")
    d1 = m1.to_dict()
    assert d1["content"] == "legacy prompt"

    # 新数据：list
    parts = [{"type": "text", "text": "看"}, {"type": "image_url", "image_url": {"url": "http://a"}}]
    m2 = Message(role="user", content=parts)
    d2 = m2.to_dict()
    assert d2["content"] is parts  # 透传

    # from_dict 不做格式转换，接收什么就给什么
    m3 = Message.from_dict({"role": "user", "content": "x"})
    assert m3.content == "x"
    m4 = Message.from_dict({"role": "user", "content": [{"type": "text", "text": "y"}]})
    assert m4.content == [{"type": "text", "text": "y"}]
    print("  ✓ Message content str / list 双向兼容")


# ====== Provider 校验层冒烟 ======

def _make_cfg(extra_params=None, provider_cap_vision=False):
    """构造一个最小 ModelConfig，仅 supports_vision 校验使用"""
    from src.providers.base import ModelConfig, ProviderCapability

    cap = ProviderCapability(
        name="test",
        display_name="Test",
        api_format="openai",
        supports_vision=provider_cap_vision,
    )
    cfg = ModelConfig(
        name="test-model",
        provider="custom",
        model="test-model",
        endpoint="http://localhost",
        api_key="x",
        extra_params=extra_params or {},
    )
    cfg.provider_capability = cap
    return cfg


from src.providers.base import BaseLLMProvider  # noqa: E402  必须在 _DummyProvider 之前


class _DummyProvider:
    """最小 stub，用于实例化后调用 BaseLLMProvider 的实例方法"""

    def __init__(self, cfg):
        self.config = cfg
        self.provider_capability = cfg.provider_capability

    # 直接把 BaseLLMProvider 的实例方法搬过来，避免实现完整的 __init__ / chat
    supports_vision = BaseLLMProvider.supports_vision
    validate_vision_capability = BaseLLMProvider.validate_vision_capability


def test_supports_vision_from_extra_params():
    # 1. extra_params 优先
    cfg = _make_cfg(extra_params={"supports_vision": True}, provider_cap_vision=False)
    assert _DummyProvider(cfg).supports_vision() is True

    cfg2 = _make_cfg(extra_params={"supports_vision": False}, provider_cap_vision=True)
    assert _DummyProvider(cfg2).supports_vision() is False

    # 2. 缺失时回退到 provider_capability
    cfg3 = _make_cfg(extra_params={}, provider_cap_vision=True)
    assert _DummyProvider(cfg3).supports_vision() is True

    cfg4 = _make_cfg(extra_params=None, provider_cap_vision=False)
    assert _DummyProvider(cfg4).supports_vision() is False
    print("  ✓ supports_vision (extra_params 优先 + 能力回退)")


def test_validate_vision_capability_rejects_text_only_model():
    from src.providers.base import Message

    # 模型不支持 vision，但消息含图 → 抛 ValueError
    cfg = _make_cfg(extra_params={}, provider_cap_vision=False)
    msgs = [Message(role="user", content=[
        {"type": "text", "text": "看图"},
        {"type": "image_url", "image_url": {"url": "http://a"}},
    ])]
    raised = False
    try:
        _DummyProvider(cfg).validate_vision_capability(msgs)
    except ValueError as e:
        raised = True
        assert "supports_vision=true" in str(e), f"错误信息应提示设置 supports_vision=true, 实际: {e}"
    assert raised, "应抛出 ValueError"

    # 文本消息 + 不支持 vision → 通过
    msgs_text = [Message(role="user", content="纯文本")]
    _DummyProvider(cfg).validate_vision_capability(msgs_text)  # 不应抛
    print("  ✓ validate_vision_capability 拒绝无 vision 模型的图片请求")


def test_validate_vision_capability_passes_for_enabled_model():
    from src.providers.base import Message

    cfg = _make_cfg(extra_params={"supports_vision": True})
    msgs = [Message(role="user", content=[
        {"type": "image_url", "image_url": {"url": "http://a"}},
    ])]
    _DummyProvider(cfg).validate_vision_capability(msgs)  # 不应抛
    print("  ✓ validate_vision_capability 放行已启用 vision 的模型")


# ====== _collect_input_images (tester.py) ======

def test_collect_input_images():
    sys.path.insert(0, str(PROJECT_ROOT))
    from src.tester import _collect_input_images

    # 纯文本
    msgs_text = [{"role": "user", "content": "hi"}]
    assert _collect_input_images(msgs_text) == []

    # 多模态
    msgs_mm = [
        {"role": "system", "content": "你是助手"},
        {"role": "user", "content": [
            {"type": "text", "text": "看图"},
            {"type": "image_url", "image_url": {"url": "http://a"}},
            {"type": "image_url", "image_url": {"url": "http://b"}},
        ]},
    ]
    imgs = _collect_input_images(msgs_mm)
    assert len(imgs) == 2
    assert imgs[0]["image_url"]["url"] == "http://a"

    # None / 空
    assert _collect_input_images(None) == []
    assert _collect_input_images([]) == []
    print("  ✓ _collect_input_images 正确抽取 image_url parts")


# ====== Provider capability 挂载回归 ======

def test_registry_create_attaches_capability():
    """
    回归测试：registry.create() 应挂载 provider_capability，
    否则 supports_vision 的能力回退路径永远失效。
    """
    from src.providers import get_provider_registry
    from src.providers.base import ModelConfig

    registry = get_provider_registry()
    # PROVIDER_CAPABILITIES 中键名为: openai/anthropic/gemini/local/azure
    # registry 注册名: openai/anthropic/gemini/azure/lmstudio/ollama
    # lmstudio/ollama 共享 capability key "local"
    for name, expected_vision in [
        ("openai", True),
        ("anthropic", True),
        ("gemini", True),
        ("azure", True),
    ]:
        cfg = ModelConfig(
            name=f"test-{name}",
            provider=name,
            model="m",
            endpoint="http://x",
            api_key="k",
            extra_params={},  # 不声明，走 capability 回退
        )
        provider = registry.create(name, cfg)
        assert provider is not None, f"{name}: 未找到 Provider 类"
        cap = getattr(provider, "provider_capability", None)
        assert cap is not None, f"{name}: provider_capability 未挂载"
        assert provider.supports_vision() is expected_vision, (
            f"{name}: supports_vision() 应为 {expected_vision}, 实际 {provider.supports_vision()}"
        )
    print("  ✓ registry.create 挂载 provider_capability，supports_vision 默认值正确（4 个 vision provider）")


def test_registry_local_and_aliases_attach_capability():
    """
    回归测试：lmstudio/ollama（共享 capability）以及别名
    （minimax/custom/compatible/claude）也必须挂上 capability。
    否则将来添加新能力时会留下未挂载的"幽灵" provider。
    """
    from src.providers import get_provider_registry
    from src.providers.base import ModelConfig

    registry = get_provider_registry()
    # 注册名 → 期望 vision 默认值
    # lmstudio/ollama 默认无 vision；别名共享上游 capability
    for name, want_vision in [
        ("lmstudio", False),
        ("ollama", False),
        ("minimax", True),     # 共享 openai capability
        ("custom", True),      # 共享 openai capability
        ("compatible", True),  # 共享 openai capability
        ("claude", True),      # 共享 anthropic capability
    ]:
        cfg = ModelConfig(
            name=f"test-{name}", provider=name, model="m",
            endpoint="http://x", api_key="k", extra_params={},
        )
        provider = registry.create(name, cfg)
        assert provider is not None, f"{name}: 未找到 Provider 类"
        cap = getattr(provider, "provider_capability", None)
        assert cap is not None, f"{name}: provider_capability 未挂载（gap）"
        assert provider.supports_vision() is want_vision, (
            f"{name}: supports_vision() 应为 {want_vision}, 实际 {provider.supports_vision()}"
        )
    print("  ✓ lmstudio/ollama 及别名（minimax/custom/compatible/claude）均正确挂载 capability")


def test_modelclient_extra_params_none_does_not_crash():
    """
    回归测试：ModelClient(extra_params=None) 不再导致 anthropic/gemini 崩溃。
    """
    from src.client import ModelClient

    for prov in ["openai", "anthropic", "gemini", "azure"]:
        client = ModelClient(
            name=f"test-{prov}",
            endpoint="http://x",
            api_key="k",
            model="m",
            provider=prov,
            extra_params=None,  # 显式 None 之前会崩
        )
        assert client.provider is not None
    print("  ✓ ModelClient(extra_params=None) 不再崩溃")


def test_modelclient_supports_vision_default():
    """
    回归测试：未在 extra_params 显式声明 supports_vision 时，
    ModelClient 的 provider 应通过 PROVIDER_CAPABILITIES 自动判定。
    """
    from src.client import ModelClient

    expected = {"openai": True, "anthropic": True, "gemini": True, "azure": True}
    for prov, want in expected.items():
        client = ModelClient(
            name=f"test-{prov}",
            endpoint="http://x",
            api_key="k",
            model="m",
            provider=prov,
            extra_params={},
        )
        got = client.provider.supports_vision()
        assert got is want, f"{prov}: supports_vision 应为 {want}, 实际 {got}"
    print("  ✓ ModelClient 默认 supports_vision 通过 PROVIDER_CAPABILITIES 判定")


def test_modelclient_extra_params_supports_vision_overrides_capability():
    """
    extra_params.supports_vision 显式声明应优先于 PROVIDER_CAPABILITIES。
    例如 local provider 默认无 vision，但用户可显式启用。
    """
    from src.client import ModelClient

    # lmstudio 默认 False，显式 True 覆盖
    client = ModelClient(
        name="lmstudio-vision",
        endpoint="http://x",
        api_key="k",
        model="llava",
        provider="lmstudio",
        extra_params={"supports_vision": True},
    )
    assert client.provider.supports_vision() is True

    # openai 默认 True，显式 False 也能覆盖
    client2 = ModelClient(
        name="openai-text",
        endpoint="http://x",
        api_key="k",
        model="gpt-3.5",
        provider="openai",
        extra_params={"supports_vision": False},
    )
    assert client2.provider.supports_vision() is False
    print("  ✓ extra_params.supports_vision 优先于 PROVIDER_CAPABILITIES")


def test_provider_adapter_attaches_capability():
    """
    ProviderAdapter 也应让 provider 拿到 capability（registry.create 已修，验证一下）。
    """
    from src.client_adapter import ProviderAdapter

    adapter = ProviderAdapter(
        name="test", provider="anthropic",
        endpoint="http://x", api_key="k", model="claude",
        extra_params={},
    )
    assert adapter._provider.provider_capability is not None
    assert adapter._provider.supports_vision() is True
    print("  ✓ ProviderAdapter 的 provider 挂载 capability")


# ====== 主入口 ======

def main():
    print("=" * 60)
    print("多模态适配冒烟测试 (offline)")
    print("=" * 60)

    failures = []

    cases = [
        ("纯函数层", [
            test_normalize_content,
            test_has_image_parts,
            test_extract_text_for_log,
            test_content_part_roundtrip,
            test_message_content_compat,
        ]),
        ("Provider 校验层", [
            test_supports_vision_from_extra_params,
            test_validate_vision_capability_rejects_text_only_model,
            test_validate_vision_capability_passes_for_enabled_model,
        ]),
        ("Tester 适配层", [
            test_collect_input_images,
        ]),
        ("Provider capability 挂载（回归）", [
            test_registry_create_attaches_capability,
            test_registry_local_and_aliases_attach_capability,
            test_modelclient_extra_params_none_does_not_crash,
            test_modelclient_supports_vision_default,
            test_modelclient_extra_params_supports_vision_overrides_capability,
            test_provider_adapter_attaches_capability,
        ]),
    ]

    for group_name, fns in cases:
        print(f"\n[{group_name}]")
        for fn in fns:
            try:
                fn()
            except AssertionError as e:
                failures.append((fn.__name__, f"断言失败: {e}"))
                print(f"  ✗ {fn.__name__}: {e}")
            except Exception as e:
                failures.append((fn.__name__, f"异常: {type(e).__name__}: {e}"))
                print(f"  ✗ {fn.__name__}: {type(e).__name__}: {e}")

    print("\n" + "=" * 60)
    if failures:
        print(f"❌ 失败 {len(failures)} 项:")
        for name, msg in failures:
            print(f"   - {name}: {msg}")
        return 1
    print("✅ 全部通过")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
