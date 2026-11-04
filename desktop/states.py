"""桌宠状态机：把"正在加载 / 待机 / 说话 / 离开 / 出错"变成显式状态。

以前各模块各记各的布尔量（was_speaking、loaded、broken…），容易出现
"正在说话却又被调度器触发""加载失败还在播报"这类互相打架的情况。
这里用一张允许转换表把它们收拢：不合法转换返回 False，不抛异常。
"""
from enum import Enum


class State(Enum):
    LOADING = 'loading'
    IDLE = 'idle'
    SPEAKING = 'speaking'
    AWAY = 'away'
    ERROR = 'error'


# 谁可以转到谁；ERROR 可以从任何状态进入，也只能由显式 reset 离开
ALLOWED = {
    State.LOADING: {State.IDLE, State.ERROR},
    State.IDLE: {State.SPEAKING, State.AWAY, State.LOADING, State.ERROR},
    State.SPEAKING: {State.IDLE, State.ERROR},
    State.AWAY: {State.IDLE, State.ERROR},
    State.ERROR: {State.LOADING},
}


class StateMachine:
    def __init__(self, initial=State.LOADING):
        self._state = initial
        self._listeners = []

    @property
    def state(self):
        return self._state

    def on_change(self, callback):
        self._listeners.append(callback)
        return callback

    def can(self, target):
        return target in ALLOWED[self._state]

    def to(self, target):
        """转换成功返回 True；不允许的转换返回 False 且状态不变。"""
        if target is self._state:
            return True
        if not self.can(target):
            return False
        previous, self._state = self._state, target
        for callback in list(self._listeners):
            callback(previous, target)
        return True

    def reset(self):
        return self.to(State.LOADING)

    # 便捷判断
    def is_speaking(self):
        return self._state is State.SPEAKING

    def is_idle(self):
        return self._state is State.IDLE
