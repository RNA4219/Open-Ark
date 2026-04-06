# tests/conftest.py
"""
pytest fixtures and configuration for Open-Ark tests.

Layer separation:
- Layer 1 (unconditional): Minimal mocks for core deletion detection tests
- Layer 2 (opt-in): Heavy mocks for LLM/integration tests via marker/fixture

Mock categories:
- send2trash: Used by room_manager.py - keep unconditional (rarely installed in test env)
- gradio: Used by memory_manager.py, ui_handlers.py - opt-in for integration tests
- langchain*: Used by entity_tools.py, llm_factory.py - opt-in for LLM tests
- google.*: Used by gemini_api.py - opt-in for Gemini tests
- filetype/tiktoken/httpx/PIL: Used by gemini_api.py - opt-in for Gemini tests
"""

import importlib.util
import sys
from unittest.mock import MagicMock
import pytest


# =============================================================================
# Layer 1: Unconditional Mocks (Core Detection)
# =============================================================================
# These are required for tests to run even without optional packages installed.
# They should NOT hide dependencies for integration-level tests.

def _module_exists(module_name: str) -> bool:
    """対象モジュールが実環境に存在するかを判定する。"""
    return importlib.util.find_spec(module_name) is not None


def _set_mock_module(module_name: str, module_obj, previous_modules: dict):
    """既存モジュールを退避しつつ sys.modules にモックを設定する。"""
    if module_name not in previous_modules:
        previous_modules[module_name] = sys.modules.get(module_name)
    sys.modules[module_name] = module_obj


def _restore_modules(previous_modules: dict):
    """退避していた sys.modules を元に戻す。"""
    for module_name, previous in previous_modules.items():
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous


# send2trash: room_manager.py dependency
# Keep unconditional only when missing from the environment.
if not _module_exists("send2trash"):
    _send2trash_prev = {}
    mock_send2trash = MagicMock()
    _set_mock_module('send2trash', mock_send2trash, _send2trash_prev)
    _set_mock_module('send2trash.send2trash', mock_send2trash.send2trash, _send2trash_prev)


# =============================================================================
# Layer 2: Opt-in Mocks (LLM/Integration Tests)
# =============================================================================
# Use via:
#   - @pytest.mark.llm_mock decorator
#   - llm_mocks fixture
#   - autouse=True only for specific test classes

class MockTool:
    """Mock class that simulates LangChain tool behavior."""
    def __init__(self, func):
        self.func = func
        self.name = func.__name__
        self.description = func.__doc__ or ""

    def invoke(self, args):
        """Simulate the invoke method of LangChain tools."""
        if isinstance(args, dict):
            return self.func(**args)
        return self.func(args)


def mock_tool_decorator(*args, **kwargs):
    """Decorator that wraps a function in a MockTool."""
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return MockTool(args[0])
    else:
        def wrapper(func):
            return MockTool(func)
        return wrapper


def _apply_llm_mocks():
    """Apply LLM-related mocks to sys.modules and return previous values."""
    previous_modules = {}

    # gradio
    mock_gradio = MagicMock()
    _set_mock_module('gradio', mock_gradio, previous_modules)
    _set_mock_module('gradio.Blocks', MagicMock(), previous_modules)
    _set_mock_module('gradio.components', MagicMock(), previous_modules)

    # langchain_google_genai
    mock_langchain_google_genai = MagicMock()
    mock_langchain_google_genai.ChatGoogleGenerativeAI = MagicMock()
    mock_langchain_google_genai.HarmBlockThreshold = MagicMock()
    mock_langchain_google_genai.HarmCategory = MagicMock()
    mock_langchain_google_genai.chat_models = MagicMock()
    mock_langchain_google_genai.chat_models.ChatGoogleGenerativeAIError = MagicMock()
    _set_mock_module('langchain_google_genai', mock_langchain_google_genai, previous_modules)
    _set_mock_module('langchain_google_genai.chat_models', mock_langchain_google_genai.chat_models, previous_modules)

    # langchain_openai
    mock_langchain_openai = MagicMock()
    mock_langchain_openai.ChatOpenAI = MagicMock()
    _set_mock_module('langchain_openai', mock_langchain_openai, previous_modules)

    # langchain_core
    mock_langchain_core = MagicMock()
    mock_langchain_core.messages = MagicMock()
    mock_langchain_core.messages.HumanMessage = MagicMock
    mock_langchain_core.messages.AIMessage = MagicMock
    mock_langchain_core.messages.SystemMessage = MagicMock
    mock_langchain_core.messages.ToolMessage = MagicMock
    mock_langchain_core.messages.AIMessageChunk = MagicMock
    mock_langchain_core.tools = MagicMock()
    mock_langchain_core.tools.BaseTool = MockTool
    mock_langchain_core.tools.InjectedToolArg = MagicMock
    mock_langchain_core.tools.InjectedToolCallId = MagicMock
    mock_langchain_core.tools.ToolException = Exception
    mock_langchain_core.tools.tool = mock_tool_decorator
    _set_mock_module('langchain_core', mock_langchain_core, previous_modules)
    _set_mock_module('langchain_core.messages', mock_langchain_core.messages, previous_modules)
    _set_mock_module('langchain_core.tools', mock_langchain_core.tools, previous_modules)

    # langchain
    mock_langchain = MagicMock()
    mock_langchain.tools = MagicMock()
    mock_langchain.tools.tool = mock_tool_decorator
    _set_mock_module('langchain', mock_langchain, previous_modules)
    _set_mock_module('langchain.tools', mock_langchain.tools, previous_modules)

    # filetype
    mock_filetype = MagicMock()
    _set_mock_module('filetype', mock_filetype, previous_modules)

    # tiktoken
    mock_tiktoken = MagicMock()
    _set_mock_module('tiktoken', mock_tiktoken, previous_modules)

    # httpx
    mock_httpx = MagicMock()
    _set_mock_module('httpx', mock_httpx, previous_modules)

    # PIL
    mock_pil = MagicMock()
    mock_pil.Image = MagicMock()
    _set_mock_module('PIL', mock_pil, previous_modules)
    _set_mock_module('PIL.Image', mock_pil.Image, previous_modules)

    # google.genai
    mock_google_genai = MagicMock()
    mock_google_genai.errors = MagicMock()
    _set_mock_module('google.genai', mock_google_genai, previous_modules)
    _set_mock_module('google.genai.errors', mock_google_genai.errors, previous_modules)

    # google.api_core
    mock_google_api_core = MagicMock()
    mock_google_api_core.exceptions = MagicMock()
    mock_google_api_core.exceptions.ResourceExhausted = Exception
    mock_google_api_core.exceptions.ServiceUnavailable = Exception
    mock_google_api_core.exceptions.InternalServerError = Exception
    _set_mock_module('google.api_core', mock_google_api_core, previous_modules)
    _set_mock_module('google.api_core.exceptions', mock_google_api_core.exceptions, previous_modules)

    return previous_modules

def _remove_llm_mocks(previous_modules):
    """Restore LLM-related modules in sys.modules."""
    _restore_modules(previous_modules)


@pytest.fixture
def llm_mocks():
    """
    Fixture that applies LLM-related mocks for the duration of the test.

    Use this when testing modules that depend on langchain, google.genai, etc.
    These modules import heavy dependencies that may not be installed.
    """
    previous_modules = _apply_llm_mocks()
    yield
    _remove_llm_mocks(previous_modules)


# =============================================================================
# Pytest Hooks
# =============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "llm_mock: Tests that require LLM-related mocks (langchain, google.genai, etc.)"
    )
    config.addinivalue_line(
        "markers", "unit: Unit tests with minimal dependencies"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests that require real dependencies"
    )


def pytest_collection_modifyitems(config, items):
    """
    Auto-apply llm_mocks fixture to tests marked with @pytest.mark.llm_mock.
    """
    for item in items:
        if item.get_closest_marker('llm_mock'):
            # Apply llm_mocks fixture via fixturenames
            if 'llm_mocks' not in item.fixturenames:
                item.fixturenames.append('llm_mocks')


# =============================================================================
# Workspace Fixtures
# =============================================================================

@pytest.fixture
def workspace_tmp_path():
    """workspace 配下に安定したテスト用一時ディレクトリを作る。"""
    import uuid
    import shutil
    from pathlib import Path

    base_dir = Path(__file__).resolve().parents[3] / "tmp_scratch" / "open_ark_tests"
    base_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = base_dir / f"test_{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def local_adapter_config(workspace_tmp_path, monkeypatch):
    """LocalAdapter 使用の設定"""
    import config_manager
    from adapters.memory_adapter import reset_adapter

    monkeypatch.setattr("constants.ROOMS_DIR", str(workspace_tmp_path / "characters"))
    config_manager.CONFIG_GLOBAL = {
        "memx_settings": {
            "use_memx": False,
            "memx_api_addr": "http://127.0.0.1:7766",
            "memx_db_path_template": "{room_dir}/memx",
            "memx_request_timeout_sec": 10,
            "gc_execute_enabled": False,
            "phase3_settings": {
                "advanced_resolver_enabled": False,
                "deprecation": {}
            }
        }
    }
    reset_adapter()
    yield
    reset_adapter()


@pytest.fixture
def memx_server_available():
    """memx-resolver API が到達可能かチェック"""
    try:
        import requests
        response = requests.post(
            "http://127.0.0.1:7766/v1/notes:search",
            json={"query": "health_check", "top_k": 1},
            timeout=5
        )
        return response.status_code == 200
    except Exception:
        return False


@pytest.fixture
def real_api_config(workspace_tmp_path, monkeypatch, memx_server_available):
    """実 MemxAdapter 使用の設定"""
    import config_manager
    from adapters.memory_adapter import reset_adapter

    monkeypatch.setattr("constants.ROOMS_DIR", str(workspace_tmp_path / "characters"))
    config_manager.CONFIG_GLOBAL = {
        "memx_settings": {
            "use_memx": True,
            "memx_api_addr": "http://127.0.0.1:7766",
            "memx_db_path_template": "{room_dir}/memx",
            "memx_request_timeout_sec": 10,
            "gc_execute_enabled": False,
            "phase3_settings": {
                "advanced_resolver_enabled": False,
                "deprecation": {}
            }
        }
    }
    reset_adapter()
    yield memx_server_available
    reset_adapter()
