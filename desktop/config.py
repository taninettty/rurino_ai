"""配置集中：路径、端点、时序只在这里定义一次。

以前端口和路径散落在 chat.py / launcher.py / 各处脚本里，改一个要搜全仓库。
现在统一从 `Config.load()` 取，环境变量可覆盖，测试里可直接构造。

环境变量：
    RURINO_OLLAMA         聊天后端（ollama 模式），默认 http://127.0.0.1:11434
    RURINO_SPEECH         语音服务，默认 http://127.0.0.1:8765
    RURINO_STAGE          3D 舞台端口，默认 8771
    RURINO_DATA           数据目录，默认 desktop/data
    RURINO_CHAT_PROVIDER  ollama | deepseek，默认 ollama
    RURINO_CHAT_BASE      远程端点，默认 https://api.deepseek.com
    RURINO_CHAT_MODEL     模型名，默认 qwen3:1.7b / deepseek-chat
    RURINO_DEEPSEEK_KEY   DeepSeek 密钥（只从环境变量读，绝不写进代码）
"""
from dataclasses import dataclass, field
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _env(name, default):
    value = os.environ.get(name)
    return value if value else default


@dataclass(frozen=True)
class Endpoints:
    ollama: str = 'http://127.0.0.1:11434'
    speech: str = 'http://127.0.0.1:8765'
    stage_port: int = 8771

    @classmethod
    def load(cls):
        return cls(
            ollama=_env('RURINO_OLLAMA', cls.ollama),
            speech=_env('RURINO_SPEECH', cls.speech),
            stage_port=int(_env('RURINO_STAGE', cls.stage_port)),
        )


@dataclass(frozen=True)
class Timings:
    tick_seconds: int = 30            # 调度器轮询
    min_gap_seconds: int = 25 * 60    # 两次播报的最小间隔
    away_seconds: int = 20 * 60       # 多久算离开
    rest_after_seconds: int = 90 * 60 # 久坐提醒
    first_audio_budget: float = 1.5   # 首句出声预算（秒，见 VOICE.md）


@dataclass(frozen=True)
class ChatBackend:
    """聊天后端：本地 Ollama，或远程 OpenAI 兼容端点（DeepSeek 等）。

    DeepSeek 的延迟在网络：首 token 常见 0.5–2 秒，波动比本地 GPU 大。
    所以它适合"聊天"，不适合"首句必须 1.5 秒内出声"的播报——
    播报继续走模板，聊天才走这个后端。
    """
    provider: str = 'ollama'
    base: str = 'http://127.0.0.1:11434'
    model: str = 'qwen3:1.7b'
    path: str = '/api/chat'
    key_env: str = ''

    @classmethod
    def load(cls):
        provider = _env('RURINO_CHAT_PROVIDER', 'ollama').lower()
        if provider == 'deepseek':
            return cls(provider='deepseek',
                       base=_env('RURINO_CHAT_BASE', 'https://api.deepseek.com'),
                       model=_env('RURINO_CHAT_MODEL', 'deepseek-chat'),
                       path='/v1/chat/completions',
                       key_env='RURINO_DEEPSEEK_KEY')
        return cls(base=_env('RURINO_OLLAMA', cls.base),
                   model=_env('RURINO_CHAT_MODEL', cls.model))

    @property
    def chat_url(self):
        return self.base.rstrip('/') + self.path

    def api_key(self):
        if not self.key_env:
            return ''
        return os.environ.get(self.key_env, '').strip()


@dataclass(frozen=True)
class Config:
    root: Path = ROOT
    data_dir: Path = ROOT / 'data'
    models_dir: Path = ROOT / 'model_assets'
    lines_file: Path = ROOT / 'data' / 'rurino-lines.json'
    endpoints: Endpoints = field(default_factory=Endpoints)
    timings: Timings = field(default_factory=Timings)
    chat: ChatBackend = field(default_factory=ChatBackend)

    @classmethod
    def load(cls):
        data = Path(_env('RURINO_DATA', str(ROOT / 'data')))
        return cls(data_dir=data, lines_file=data / 'rurino-lines.json',
                   endpoints=Endpoints.load(), chat=ChatBackend.load())

    def check(self):
        """启动前自检：返回缺失项列表，空列表表示可以启动。"""
        missing = []
        if not self.data_dir.is_dir():
            missing.append(f'数据目录不存在: {self.data_dir}')
        if not self.lines_file.is_file():
            missing.append(f'台词库不存在: {self.lines_file}')
        if self.chat.provider == 'deepseek' and not self.chat.api_key():
            missing.append('未设置 RURINO_DEEPSEEK_KEY（DeepSeek 需要密钥）')
        return missing


DEFAULT = Config()
