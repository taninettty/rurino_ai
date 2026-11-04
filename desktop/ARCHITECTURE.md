# 桌宠架构（定稿）

> 一句话：**一个入口、两个窗口、三层边界**。先跑通最小闭环，再往上加功能。
> 任何与本文冲突的旧代码都以本文为准，冲突的旧文件按「删除清单」处理。

## 1. 进程与窗口

```
ruri.exe  （PyQt5 托盘程序，唯一入口）
├─ Kernel（Python，后台线程）      ← 决策层，不碰像素
├─ Stage 窗口（WebView2）          ← 只渲染角色，不许有业务逻辑
├─ Chat 窗口（WebView2）           ← 独立聊天界面
└─ StaticServer（同进程，随机端口） ← 只给上面两个窗口供静态资源
```

- **只有一个可执行入口**：`main.py`。其它 `*.py` 不得自带 `if __name__ == '__main__'` 的启动逻辑。
- **两个窗口各自独立**：桌宠窗口小、透明、置顶；聊天窗口正常大小，从托盘打开。
- **语音服务是子进程**，由 Kernel 托管（健康检查 + 退避重启），不属于窗口。

## 2. 三层边界

| 层 | 目录 | 可以依赖 | 绝对不可以 |
|---|---|---|---|
| **决策层** | `kernel/` | config、states、scheduler、persona、chat_client | 不 import Qt、不碰 DOM |
| **宿主层** | `host/` | PyQt5、pywebview、kernel 的公开接口 | 不写业务规则 |
| **表现层** | `web/`（pet.html / chat.html） | 只认命令协议 | 不发明状态、不直接读文件 |

依赖方向永远向内：`web → host → kernel`，反向禁止。

## 3. 目录

```
desktop/
├─ main.py                # 唯一入口：装配 + 生命周期
├─ kernel/
│   ├─ config.py          # 路径/端点/时序（已有）
│   ├─ states.py          # 状态机（已有）
│   ├─ scheduler.py       # 何时说（已有）
│   ├─ persona.py         # 说话规则（已有）
│   ├─ announcer.py       # 逐句合成与播放（已有）
│   ├─ chat_client.py     # Ollama / OpenAI 兼容（已有）
│   ├─ speech.py          # 语音服务托管（新增）
│   └─ bus.py             # 内核事件总线（新增）
├─ host/
│   ├─ tray.py            # 托盘与菜单
│   ├─ stage.py           # Stage 窗口 + JS 桥
│   ├─ chat.py            # Chat 窗口 + JS 桥
│   └─ server.py          # 内置静态服务（单例，随机端口）
├─ web/
│   ├─ pet.html + pet.js  # 只有角色和字幕
│   └─ chat.html + chat.js
├─ data/                  # 台词、配置
└─ tests/
    └─ acceptance.py      # 唯一验收脚本（替代全部探针）
```

## 4. 命令协议（host → web）

Stage 只认这几个命令，全部通过 `evaluate_js` 下发：

```js
window.pet.load(modelUrl)        // 由页面自己发起，host 不参与
window.pet.say(ja, zh)           // 说话 + 字幕
window.pet.idle()                // 回到待机
window.pet.mood(name)            // 可选：表情
window.pet.ready                 // 布尔量，页面置位
```

约束：
- **异步调用必须包 `setTimeout(..., 0)`**，否则 `evaluate_js` 会等 Promise 卡死。
- 页面要回传 `window.petLog`（数组），host 每 5 秒读一次做健康判断。

## 5. 内核事件

```python
bus.emit('speak', ja=..., zh=...)   # 调度器 → 播报
bus.emit('state', State.SPEAKING)   # 状态变化
bus.emit('error', stage='speech')   # 降级信号
```

- 聊天窗口与 Stage **都订阅同一个总线**，所以聊天回复能同时出现在窗口和角色身上。
- 语音失败 → `error` 事件 → 只显示文字，不中断对话。

## 6. 生命周期

```
启动 → config.check() → 拉语音服务 → 开 StaticServer → 开 Stage → LOADING
     → 页面 ready → IDLE → 调度器 tick(30s)
退出 → 停调度 → 排空播报 → 停语音服务 → 关窗口
```

`config.check()` 不通过 → 弹一次说明并退出，不进入半可用状态。

## 7. 验收（唯一标准）

`tests/acceptance.py` 必须一次跑完并全绿：

1. 起 Stage，页面 `ready` 在 30 秒内为真；
2. 下发 `say()`，2 秒内截到角色画面（Win32 真实矩形）；
3. 调度器给一个早晨上下文，能返回一句带小时的台词；
4. 语音服务被杀后 5 秒内被拉回；
5. 聊天窗口能收到一条流式回复（本地假服务）。

**这五条不过，不算跑通；过了才允许加新功能。**

## 8. 删除清单（迁移后立即执行）

- `app.py`、`sprite_pet.py`、`sprites.py`、`model_support.py`（Live2D 旧栈）
- `tests/pet_stage.py`、`pet_stage2.py`、`webview_probe.py`、`webview2_probe.py`
- `spine-tools/` 整个目录
- 根目录下所有 `dbg_*.py`、`show_*.py`、`extract_*.py`、`check_*.py`

保留：`kernel/*`、`host/*`、`web/*`、`data/*`、`tests/acceptance.py`、`tests/test_*.py`（单测）。

## 9. 已知风险

| 风险 | 依据 | 对策 |
|---|---|---|
| 页面模块不执行 | `pet.html/pet.js` 实测 `module-start` 从未出现 | 第一步就用 CDP 抓控制台，不许再猜 |
| 模型加载 20–120 秒 | 实测波动 | 专用 `pet.js` 只加载 idle 一个动作，砍掉几十 MB JSON |
| WebView2 透明窗口兼容性 | 未在干净机器验证 | 降级为无边框不透明卡片 |
| 打包体积 | three.js + 模型约 300 MB | 按需裁剪模型与动作 |
