# harness/provider/factory.py
# Provider 工厂 - 一行代码切换模型

import os
from typing import Optional

from .base import BaseProvider
from .claude import ClaudeProvider
from .openai_compat import (
    OpenAICompatProvider,
    DoubaoProvider,
    QwenProvider,
    DeepSeekProvider,
    VolcenginePlanProvider,
)


def create_provider(provider_type: str, **kwargs) -> BaseProvider:
    """
    Provider 工厂函数
    
    Usage:
        # 使用 Claude
        provider = create_provider("claude", api_key="sk-ant-...")
        
        # 使用 OpenAI
        provider = create_provider("openai", api_key="sk-...", model="gpt-4o")
        
        # 使用豆包（ByteDance）
        provider = create_provider(
            "doubao",
            api_key="...",
            model="doubao-pro-32k",
        )
        
        # 使用 Qwen
        provider = create_provider(
            "qwen",
            api_key="sk-...",
            model="qwen-max",
        )
        
        # 使用 DeepSeek
        provider = create_provider(
            "deepseek",
            api_key="sk-...",
            model="deepseek-chat",
        )
    """
    providers = {
        "claude": ClaudeProvider,
        "openai": OpenAICompatProvider,
        "openai_compat": OpenAICompatProvider,
        "doubao": DoubaoProvider,
        "qwen": QwenProvider,
        "deepseek": DeepSeekProvider,
        "volcengine_plan": VolcenginePlanProvider,
        "volcengine-plan": VolcenginePlanProvider,
        "volcengine_coding": VolcenginePlanProvider,
    }
    
    if provider_type not in providers:
        available = ", ".join(providers.keys())
        raise ValueError(f"未知 Provider 类型: {provider_type}。可用: {available}")
    
    # provider_type 只是用来选择 Provider 类，不是 Provider 构造函数的参数
    kwargs.pop("provider_type", None)
    return providers[provider_type](**kwargs)


def load_provider_from_config(config: dict, provider_name: str = None) -> BaseProvider:
    """
    从配置字典加载 Provider
    
    Args:
        config: 配置字典，格式如下：
            {
                "default_provider": "claude",
                "providers": {
                    "claude": {
                        "type": "claude",
                        "api_key": "${ANTHROPIC_API_KEY}",
                        "model": "claude-opus-4-5",
                    },
                    ...
                }
            }
        provider_name: 要使用的 Provider 名称，默认使用 default_provider
    """
    default_provider = config.get("default_provider", "claude")
    provider_name = provider_name or default_provider
    
    provider_config = config["providers"][provider_name].copy()
    
    # 展开环境变量
    for key, value in provider_config.items():
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            provider_config[key] = os.environ.get(env_var, "")
    
    # 移除非 Provider 参数
    provider_type = provider_config.pop("type", provider_name)
    
    # 通用 Provider 参数
    common_keys = {"api_key", "model", "timeout", "max_retries"}
    
    # 各 Provider 特殊参数
    provider_specific_keys = {
        "claude": {"thinking_enabled", "thinking_budget_tokens", "max_tokens"},
        "doubao": set(),  # 豆包只接受 api_key 和 model
        "qwen": set(),
        "deepseek": {"base_url"},
        "openai": {"base_url"},
        "volcengine_plan": set(),  # Coding Plan 只接受 api_key 和 model
        "volcengine-plan": set(),
        "volcengine_coding": set(),
    }
    
    allowed_keys = common_keys | provider_specific_keys.get(provider_type, set())
    filtered_config = {k: v for k, v in provider_config.items() if k in allowed_keys}
    
    return create_provider(provider_type, **filtered_config)


def load_provider_from_yaml(config_path: str, provider_name: str = None) -> BaseProvider:
    """
    从 YAML 配置文件加载 Provider
    
    Args:
        config_path: 配置文件路径
        provider_name: 要使用的 Provider 名称
    """
    try:
        import yaml
    except ImportError:
        raise ImportError("请安装 pyyaml: pip install pyyaml")
    
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    return load_provider_from_config(config, provider_name)


# 预设 Provider 快捷方式
def claude(api_key: str = None, model: str = "claude-opus-4-5", **kwargs) -> ClaudeProvider:
    """快速创建 Claude Provider"""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("请提供 api_key 或设置 ANTHROPIC_API_KEY 环境变量")
    return ClaudeProvider(api_key=api_key, model=model, **kwargs)


def openai(api_key: str = None, model: str = "gpt-4o", **kwargs) -> OpenAICompatProvider:
    """快速创建 OpenAI Provider"""
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("请提供 api_key 或设置 OPENAI_API_KEY 环境变量")
    return OpenAICompatProvider(api_key=api_key, model=model, **kwargs)


def doubao(api_key: str = None, model: str = "doubao-pro-32k", **kwargs) -> DoubaoProvider:
    """快速创建豆包 Provider"""
    api_key = api_key or os.environ.get("DOUBAO_API_KEY")
    if not api_key:
        raise ValueError("请提供 api_key 或设置 DOUBAO_API_KEY 环境变量")
    return DoubaoProvider(api_key=api_key, model=model, **kwargs)


def qwen(api_key: str = None, model: str = "qwen-max", **kwargs) -> QwenProvider:
    """快速创建 Qwen Provider"""
    api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError("请提供 api_key 或设置 DASHSCOPE_API_KEY 环境变量")
    return QwenProvider(api_key=api_key, model=model, **kwargs)


def deepseek(api_key: str = None, model: str = "deepseek-chat", **kwargs) -> DeepSeekProvider:
    """快速创建 DeepSeek Provider"""
    api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("请提供 api_key 或设置 DEEPSEEK_API_KEY 环境变量")
    return DeepSeekProvider(api_key=api_key, model=model, **kwargs)


def volcengine_plan(api_key: str = None, model: str = "ark-code-latest", **kwargs) -> VolcenginePlanProvider:
    """快速创建火山引擎 Coding Plan Provider"""
    api_key = api_key or os.environ.get("VOLCANO_ENGINE_API_KEY")
    if not api_key:
        raise ValueError("请提供 api_key 或设置 VOLCANO_ENGINE_API_KEY 环境变量")
    return VolcenginePlanProvider(api_key=api_key, model=model, **kwargs)
