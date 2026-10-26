# 瑠璃乃 Live2D 桌宠程序 · 接入版

本目录提供真正的 Cubism 模型播放器，以及已确认形象的导入界面。**瑠璃乃模型仍待 Cubism 绑定，当前包不是完整桌宠成品。** 没有模型时显示导入窗口；不会把立绘变成晃动的截图桌宠，也不包含此前被拒绝的举手动画。

[下载本地对话版](https://github.com/taninettty/rurino_ai/releases/tag/desktop-chat-v0.2.1) · [Ollama、录音和语音服务配置](CHAT.md)

新增本地对话窗口：文字或按次录音提问，说完停顿会自动发送，Ollama 流式回复，用户日语音色按句合成，可随时打断，并可显示中文字幕、保存称呼与少量备注。没有导出角色模型时也能先聊天。CPU 下合成有明显延迟，实际 Windows / Ollama 整链路尚待验收；详见上述说明。

[v0.3 已完成改进与下一步建议](IMPROVEMENTS.md)

## Windows 使用

1. 确认已有 64 位 Python 3.11 或更新版本（推荐 3.12，保留 Python Launcher）；**已经装了就跳过这一步**，没装才需要安装。`live2d-py` 提供 `cp311-abi3` 轮子，3.11 及以上可直接使用；安装脚本会优先选 3.12，并把过程写入 `install.log`。
2. 完整解压下载的程序包，双击 `Install-Windows.cmd`。它在本目录创建独立 `.venv`，联网从 PyPI 安装固定版本的主要依赖，不修改语音训练环境。
3. 双击 `Start-Windows.cmd`。没有导出模型时可以确认形象、试听现有音色。
4. 将 Cubism 导出的完整模型文件夹保存在固定位置，选择其中的 `.model3.json`。不要只复制这个 JSON；`.moc3`、纹理和引用的动作、物理等文件都要保留。
5. 首次成功加载后自动记住路径，下次启动直接进入桌宠。文件移动或加载失败时返回导入窗口。

依赖 Windows x64、可用的 OpenGL 显卡驱动。这是 Python 源码与启动脚本包，**不是免安装 EXE**。安装脚本已在 Windows 11 + Python 3.11.9 实机跑通；透明窗口与音频输出尚未在 Windows 实机验证。

## 已实现的功能

- 实际 `.moc3` 网格渲染、透明背景，使用 `live2d-py==1.0.0`。
- 左键拖动位置，滚轮缩放，右键置顶、静音、目光跟随、切换模型、退出。
- 有系统托盘时可隐藏与恢复；窗口位置、大小和设置会保存。
- 点击人物进入聊天；空格或右键“打招呼”播放原有问候。`M` 切换静音，`Esc` 打断当前对话。
- 聊天窗口：说完停顿自动发送（0.6 / 0.9 / 1.5 秒可选，可关闭）、中文字幕（日文回复后额外一次本地翻译，只显示不朗读）、可编辑的本地记忆（称呼与备注，存在 `%LOCALAPPDATA%\RurinoLive2D\memory.json`，整段聊天不落盘）。
- 使用 WAV 振幅控制 `ParamMouthOpenY`；播放结束、停止或静音后复位。它是振幅嘴型，不是按日语音素生成的多嘴型动画。
- 自动眨眼、呼吸和目光跟随依赖模型实际绑定的标准参数。只有模型带 `Idle` 动作组时才播放对应动作；程序不会自动制作挥手或歪头关键形。
- 导入前检查 JSON 结构、资源是否齐全、资源是否在模型目录内、MOC3 文件头。此检查不替代 Cubism 对模型内部结构的验证。

程序播放附带问候及本地语音服务合成的回复，不额外播放第三方模型动作中的声音。

## 给负责 Cubism 的 AI

先读 [制作交接说明](https://github.com/taninettty/rurino_ai/blob/live2d-handoff/live2d/HANDOFF.md)，从 [素材 Release](https://github.com/taninettty/rurino_ai/releases/tag/live2d-prep-v0.2) 下载 PSD 并完成绑定。

导出时包括 `.moc3`、`.model3.json`、纹理，以及确实使用的物理、姿态和动作文件。重点检查 `ParamEyeLOpen`、`ParamEyeROpen`、`ParamMouthOpenY`、头部角度、眼球和呼吸参数。不要把其他模型或测试截图当作瑠璃乃成品。

完成导出后在本程序中测试默认姿态、眨眼、目光跟随、语音嘴型、参数极限组合，再在 Windows 检查透明背景、拖动、缩放、置顶、静音和关闭。模型变形是否自然仍需要人工验收。

## 开发与验证

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
.venv\Scripts\python.exe tests\smoke_chat.py
.venv\Scripts\python.exe tests\smoke_live2d.py C:\Models\Test\Test.model3.json
```

第二项用本地协议测试服务跑完整个聊天窗口流程（含自动发送、字幕、记忆注入），不需要 Ollama 或麦克风。第三项需要真实模型与可用的 OpenGL 上下文；测试应在隔离桌面执行，会创建并关闭测试窗口，使用临时设置，不写入正常桌宠设置。测试模型需有 `ParamMouthOpenY`。模型不随本包分发。

验证记录：42 项单元测试通过（协议、模型校验、语音服务缓存、停顿判定、本地记忆）；Qt 聊天流程通过；安装脚本在仅装 Python 3.11 的 Windows 上跑通；真实 Ollama（qwen3:1.7b，RTX 4060 GPU）对话与中文字幕实测通过。真实渲染记录来自此前 Linux Xvfb / Mesa 下的 Haru 测试资源，该资源不含动作/物理，因此尚不能证明完整动作和物理播放，也不能证明瑠璃乃绑定效果。

Windows 日志：`%LOCALAPPDATA%\RurinoLive2D\desktop.log`；原生库输出：同目录 `runtime.log`。遇到启动问题可在此目录运行 `.venv\Scripts\python.exe app.py` 查看终端输出。

运行库来自 [live2d-py](https://github.com/Arkueid/live2d-py)，基于 Live2D Cubism SDK。依赖与 SDK 的使用、再分发遵循各自许可；本包不包含 Cubism Editor 或第三方测试模型。
