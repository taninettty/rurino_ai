# 给负责 Windows / Cubism 的 AI

## 用户授权与当前方向

用户要求做 Windows Live2D 桌宠，并授权把当前工作上传 GitHub，让另一个 AI 安装 Cubism 后接手。用户已确认 `rurino_master.png` 中的自然站姿，不要再次改变人物身份。

官方形象参考来自：https://www.youtube.com/watch?v=ltAEA_Lq5Js 。语音来自用户训练的 `taninettty/rurino_ai`，不是随机生成的替代音色。问候台词为「こんにちは！会えてうれしいな。」。

用户明确拒绝双手举起的截图动画桌宠。旧 Qt 截图原型已停止，不作为交付物、不自动启动，也不要用它冒充真正的 Live2D。

## 素材包布局

配套 `Rurino-Live2D-Handoff.zip` 的根目录包含：

- `rurino_master.png`：确认过的正常站姿原图。
- `official_video_reference.png`：已确认身份的官方视频截图。
- `layers/`：初次原图拆层，保留同画布位置，供对照和脚本重建。
- `refined/Rurino_Repaired_Layers.psd`：第二版修整稿，建议从这里接手。
- `refined/layers/`：第二版独立部件。
- `refined/repair_report.json`：补画像素数、默认姿态与 PSD 读回检查。
- `*_underpaint*.png`、`expression*.png`：LibTV 补画原件及对齐素材。
- `audio/rurino_hello_3s.wav`：现有语音模型生成的 3.2 秒问候。
- `production/`：可重建的处理脚本。
- `SHA256SUMS.json`：包内文件哈希。

左右 L/R 均以观看者视角命名。所有部件基准画布为 1536 × 2048。

## 首先安装并导入

1. 检查 Windows 上是否已有 Cubism Editor；有则复用。没有则从官方页面下载：https://www.live2d.com/zh-CHS/cubism/download/editor/ 。按安装程序要求处理许可与首次启动，不需要替用户购买订阅。
2. 将 `refined/Rurino_Repaired_Layers.psd` 导入为新模型，保存 `Rurino.cmo3`。不要把 PSD 改后缀当作 Cubism 工程。
3. 在 Editor 里核对默认形象。隐藏参考层默认关闭，闭眼与张嘴层也默认关闭。不要同时打开睁眼与闭眼图层。
4. 记录安装版本与真实导入结果。当前执行环境只有 Linux，尚未做 Windows Cubism 导入验证。

## 修整稿仍需人工核验的地方

第二版实际完成了补画应用，但没有经历 Cubism 网格变形测试，不要直接标成完工。

- 后发只将 LibTV 的补画用于被原部件遮住的区域，使用人工选取的三个控制点。要逐一移开身体、手臂，检查内侧发丝连续性。
- 脸部底图按鼻子与下巴缩放对齐。检查移动眉毛、眼睛和嘴巴时，底下是否残留线条、色差或遮挡边缘。
- 花饰下的前发扩展是邻近颜色延伸；近看可能有多余色块。花饰与对应头部共用父级，前发摆动前先细修附件附近。
- 手腕增加了独立的 `Wrist_Overlap_L/R`。它们应跟随对应手掌或手臂父级，并保持在袖口后面。
- 肩根和袖子边界需做小角度极限检查；宽幅挥手还没有补画和绑骨支撑。
- 当前双眼闭合、张嘴是独立表情贴图。还需绑定网格或可控不透明度关键形，不能把“有贴图”当作“已绑定”。

## 建模顺序

先创建 ArtMesh 和父级变形器，完成眨眼与嘴型，再做头部小幅歪转、身体呼吸和后发轻摆。不要先做大动作。

建议基础参数：

| ID | 范围 | 说明 |
| --- | --- | --- |
| ParamEyeLOpen / ParamEyeROpen | 0–1 | 左右眼分别绑定闭合与睁开 |
| ParamEyeBallX / ParamEyeBallY | -1–1 | 虹膜小幅移动，限制在眼白内 |
| ParamMouthOpenY | 0–1 | 现有闭嘴与张嘴形态 |
| ParamAngleX | -15–15 | 小幅转头，需检查透视和遮挡 |
| ParamAngleY | -10–10 | 小幅抬头、低头 |
| ParamAngleZ | -8–8 | 歪头 |
| ParamBodyAngleX | -5–5 | 上身轻动 |
| ParamBreath | 0–1 | 胸肩呼吸，不能只平移整张图 |
| ParamHairSwing | -1–1 | 自定义后发摆动参数 |

上述参数是制作计划，不是现有模型文件中已创建的参数。

## 验收与导出

- 检查每个参数的最小／中间／最大值与常用组合，特别是闭眼同时转头、张嘴同时歪头。
- 不允许露出透明裂缝、旧眼睛、旧嘴巴或错位花饰。
- 保存真实 `.cmo3` 工程，再由 Editor 导出 `.moc3`、`.model3.json`、纹理；有物理时导出 `.physics3.json`。
- 导出的模型必须在 Cubism 或真实运行库中加载并检查，才能集成 Windows 透明桌宠。
- 最终桌宠再接入拖动、置顶、静音、缩放和用户音色；不要播放之前被拒绝的举手序列帧。

## 重建图层（可选，不是 Cubism 自动绑定）

在素材包根目录创建 Python 3.12 环境，安装 `requirements-artifacts.txt`。依次运行：

```powershell
python production/align_supplements.py
python production/build_layers.py
python production/refine_layers.py
```

不要在现有语音环境中随意升级 NumPy。图像处理和语音推理应使用独立环境。

这些脚本只生成图片与 PSD，不产生 `.cmo3` 或 `.moc3`。当前已经验证的是静止合成和 PSD 保存读回；绑定、动作质量及 Windows 运行验证仍由接手方完成。
