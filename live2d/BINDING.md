# 瑠璃乃 Cubism 绑定操作单

素材已核对（`refined/Rurino_Repaired_Layers.psd`）：画布 **1536 × 2048**，12 组、29 层，
`Eye_L_Closed` / `Eye_R_Closed` / `Mouth_Open` / `Approved_Reference` 默认隐藏。
分组：`01_Back_Hair` `02_Legs` `03_Arms` `04_Body` `05_Hands` `06_Neck` `07_Head`
`08_Face` `09_Front_Hair` `10_Flowers` `00_Joint_Overlaps` `99_Reference`。

## 1. 安装与导入

1. 下载 Cubism Editor（免费版够用）：<https://www.live2d.com/cubism/download/editor/>，需要登录 Live2D 账号。
2. 新建模型 → 导入 `refined/Rurino_Repaired_Layers.psd`，画布按 PSD 尺寸。
3. 另存为 `Rurino.cmo3`，**不要**用改后缀的方式冒充工程文件。
4. 导入后先确认：默认姿态与 `rurino_master.png` 一致；闭眼/张嘴层是关闭的；参考层关闭。

## 2. 变形器层级（自上而下）

```
Root
└ Body (ParamBodyAngleX, ParamBreath)
  ├ Skirt, Legs
  ├ Arm_L / Arm_R → Hand_L / Hand_R（Wrist_Overlap_* 挂在对应手掌下，压在袖口后）
  └ Head (ParamAngleX/Y/Z)
    ├ Hair_Back_L / Hair_Back_R（ParamHairSwing，最慢的摆动）
    ├ Neck
    ├ Face_Skin
    │ ├ Brow_L / Brow_R
    │ ├ Eye_L_White_Lash + Eye_L_Iris, Eye_R_White_Lash + Eye_R_Iris
    │ ├ Eye_L_Closed / Eye_R_Closed（默认隐藏）
    │ └ Mouth_Closed / Mouth_Open
    ├ Hair_Front_L / Hair_Front_R（跟随头部，轻微延迟）
    ├ Hair_Lock_R
    └ Flower_L / Flower_R
```

先只做 `Root → Body → Head` 三层，部件网格建完再补中间层；不要一上来堆满。

## 3. 参数与层对应

| 参数 | 范围 | 做法 |
| --- | --- | --- |
| `ParamEyeLOpen` / `ParamEyeROpen` | 0–1 | 睁开层不透明度 1→0、闭眼层 0→1，交叉在 0.5 附近；两眼分别做 |
| `ParamEyeBallX` / `ParamEyeBallY` | −1–1 | 只移动 `Eye_*_Iris`，位移不超过眼白包围盒 |
| `ParamMouthOpenY` | 0–1 | `Mouth_Closed` 不透明度反向、`Mouth_Open` 正向；也可对 Open 层做网格形变 |
| `ParamAngleX` | −15–15 | Head 变形器 + 面部轻微水平偏移；检查耳朵/发际线不露缝 |
| `ParamAngleY` | −10–10 | Head 上下位移；下巴与颈部交界处补 `Neck` 跟随 |
| `ParamAngleZ` | −8–8 | Head 旋转，花饰与后发跟随 |
| `ParamBodyAngleX` | −5–5 | Body 轻微倾斜，脚与裙摆保持接地 |
| `ParamBreath` | 0–1 | 胸肩缩放 + 头部 1–2 px 上浮；**不要整体平移整张图** |
| `ParamHairSwing` | −1–1 | 后发左右摆动，与头部角度反向轻微滞后 |

眼白/虹膜/睫毛是三层，眼型变形优先动 `Eye_*_White_Lash`，虹膜单独跟随 `ParamEyeBall*`。

## 4. 网格建议

- 脸与身体：8×8 以上，下巴、鼻翼、肩线加密。
- 发丝：沿走向长条切分（每条 4–6 段），摆动端点加权。
- 手臂：沿肘部两段，避免弯曲时接缝张开。
- 花饰：独立网格，随头部移动，不要与头发共用顶点。
- 嘴/眼：小网格 + 不透明度关键形，不要用位移做开合。

## 5. 导出

导出 `.moc3`、`.model3.json`、纹理（1024 或 2048 均可，注意体积），
有物理时一并导出 `.physics3.json`。模型文件夹整体复制，不要只拿 JSON。

导出后必须能被下面这条检查通过（`FileReferences` 全部相对路径、资源齐全）：

```powershell
.venv\Scripts\python.exe tests\smoke_live2d.py <模型文件夹>\Rurino.model3.json
```

## 6. 验收清单

- [ ] `ParamEyeLOpen=0` 时没有旧眼睛残影，睫毛位置正确
- [ ] 闭眼 + `ParamAngleZ=±8` 组合不露裂缝
- [ ] `ParamMouthOpenY=1` 时牙齿/舌头区域没有空洞或色块
- [ ] 张嘴 + 歪头、张嘴 + 转头组合无穿模
- [ ] `ParamHairSwing=±1` 时后发不穿身体，花饰不飘走
- [ ] 极限值（所有参数同取最大/最小）下画布边缘不出黑边
- [ ] 程序内：透明背景、拖动、缩放、置顶、静音、嘴型归零

## 7. 导出后交给程序这边

把 `.model3.json` 的完整路径给出即可，程序会自动记住。随后需要复测：
真实音色合成的嘴型联动、目光跟随、透明窗口拖动，以及聊天时字幕与语音的同步。
