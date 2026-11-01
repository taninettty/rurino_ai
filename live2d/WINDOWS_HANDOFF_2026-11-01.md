# Windows AI 续作交接 · 2026-11-01

这是现有成果与未完成工作的交接，不是成品发布。用户要求上传到 GitHub 后由 Windows 上的 AI 继续制作。请先读本文，不要按旧 Release 或旧文档中的“下一步”重做。

下载：[本次交接 Release](https://github.com/taninettty/rurino_ai/releases/tag/windows-handoff-2026-11-01)。完整解压 `Rurino_Windows_AI_Handoff_2026-11-01.zip`，先运行 `python verify_handoff.py` 校验包内哈希。包内含桌宠程序、可编辑模型、PSD、透明图层、审计和实际运行预览；不含 Cubism Editor、SDK 安装包或语音大权重。现有语音权重继续使用本仓库 main 分支的模型，勿重新训练。

## 唯一续作入口

以解压根目录为工作目录，以下简写 `B = rurino_assets/desktop_live2d/rebuild_v3_4`。

| 路径 | 实际状态 |
|---|---|
| `B/front_right_hair_v4/Rurino_RightHair_v034.cmo3` | 最新已保存、关闭、重开、再次导出并验证的原生工程。**从这里另存后继续。** |
| `B/front_right_hair_v4/Rurino_Front_RightHair_v034.psd` | 配套的完整受控 PSD。后续材料修改以此为基底。 |
| `B/front_right_hair_v4/runtime/Rurino_RightHair_v034.model3.json` | 可加载的真实模型。必须连同 moc3、cdi3 和纹理目录一起使用。 |
| `B/front_tails_v5/Rurino_Front_Tails_v034.psd` | 最新四马尾完整材料；仅通过材料检查，**没有保存成功的 v5 原生绑定**。 |
| `B/front_tails_v5/layers/` | 四马尾颜色、独立线稿及后发补底 PNG。 |
| `B/front_layer_cleanup_v3/layer-audit/` | 43个图层实例的历史审计及8页图片。需结合 v4 修复记录判断，不能把旧缺陷清单当成全部仍未改。 |

v4 CMO3 SHA256：`b22b0d644438cb313291a88e3245ce314ea938838b26e437332f8f5839e82e6f`。

**中断说明：** 上次在编辑器内导入了 v5 PSD，并暂时建立右大马尾线稿网格；尚未完成父级绑定、保存或导出。2026-11-01 检查时编辑器会话已不存在，磁盘上的 `front_tails_v5/Rurino_Tails_v034.cmo3` 与 v4 哈希完全相同。因此它只是 v4 副本，不是完成的 v5。交接包排除此易混淆副本。请从 v4 重做 v5 导入，不要把内存操作当作已落盘成果。

## 已验证成果与边界

- v4 完整替换右贴脸发和细长卷发，加入各自独立黑线与右衣服补底；其他41个 PSD 实例精确保留。细长发尖保留至原图 y2272，没有裁到2048边界。
- 两组颜色/黑线各289顶点、512三角形。CheekLock_R/Ink_CheekLock_R 同属 HeadPitch_Surface，绘制顺序504/505；FrontLock_R_Long/Ink_FrontLock_R_Long 同属 HeadPitch_Attachments，502/503；Clothing_Right_Hair_Underpaint 属 ChestBreath，501。右刘海506/507、花饰508、眉毛509。
- 实际 SDK 185组组合检查通过，未改网格位移0，无新翻折；5个目标层覆盖无遗漏；颜色/线稿最大对应误差小于0.065原图像素。保存重开后的4个导出文件逐字节一致。证据见 v4 `qa-runtime/`。
- `qa-runtime/right-hair-pitch-comparison.mp4` 是12秒360帧真实 SDK 对照；仅俯仰参数变化，不是综合物理或语音验收。
- v4 继承之前正面眨眼、口型、视线、身体轻摆和俯仰修订。眼距问题曾修正；不要以整脸缩放重做。**AngleX 实测0位移，左右转头仍未绑定。整体抬低头体积与视觉效果仍未验收。**
- v4 原生运行包仅含模型、MOC3、CDI和纹理；旧阶段的外部 idle/physics 不得自动宣称随包包含。恢复物理时须重新验证，不能直接覆盖当前模型。

## Windows AI 第一批工作：完成 v5 四马尾

1. 安装/使用官方 Cubism Editor（此前使用5.3.04 FREE，SDK4.2导出）。打开 v4 CMO3，另存为新 v5 工程，保留原版。
2. 在该模型打开 v5 PSD，选择合入当前模型，再选择替换 `Rurino_Front_RightHair_v034.psd`；不要新建无绑定模型，也不要把所有层当新 ArtMesh 添加。
3. 核对7个替换层：SideHair_L/R、Ink_SideHair_L/R、Ponytail_L/R、BackHair_Concealed_Support；新增2层：Ink_Ponytail_L/R。39个其他 PSD 实例应原样保留。
4. 为四对颜色/黑线建立覆盖完整图像的网格。**大马尾延伸到文档外，不能按2048画布裁切。** PSD已记录偏移；PNG为3456×2816，正面原点在PNG的 x=704。PNG的 x 坐标减704才是 PSD 坐标，后发 PNG 则是2048画布无偏移。

| 部件 | 原 PSD 坐标包围盒（左、上、右、下） |
|---|---|
| SideHair_L | 173, 193, 643, 1038 |
| SideHair_R | 1396, 196, 1876, 1038 |
| Ponytail_L | -158, 323, 882, 2582 |
| Ponytail_R | 1163, 323, 2183, 2572 |
| BackHair_Concealed_Support | 587, 109, 1463, 1218 |

5. 核对父级：小马尾颜色/线稿继承 HeadPitch_Surface；大马尾颜色/线稿成对挂 LargeTail_L/R，沿用原颜色层父级。新增线稿初始在 Root，必须修正。后发继承 Pitch_BackHair_Occlusion。大马尾原颜色顺序480，可先将线稿设481，再实际检查后发、肩颈遮挡，不盲套数字。
6. FREE 版不能复制粘贴网格（提示 PRO），请手动制作配对网格。此前使用相同范围四角网格并细分4次作为过渡基础；矩形透明网格范围不是矩形切画。仍需检查发流和形变，不能以顶点数判定精修完成。
7. 在纹理图集界面把新增未分配图层加入图集，再自动布局；此前单张2048图集可用。不要只布局而忘记加入新线稿。
8. 保存→关闭→重开→导出→实际 SDK 检查。v5 `process-record/check_native.py` 与 `check_ink.py` 已准备，**尚未对 v5 执行成功**。几何脚本预计230组姿态；线稿脚本还需扩展至大马尾与身体组合。捕获预览时缩小显示范围以看见完整发尖，不可修改几何数据来通过检查。

## 后续修复顺序与验收

先检查 v5 材料，再绑定，发现露底就回到材料修补：后发已去掉外侧重复马尾轮廓、填补孔洞，但**内部仍含旧刘海纹路，补洞部分较软**，并非画干净的后发。按真正后发范围清理；在头发移开、身体侧摆及仰头时检查，不只看中性图。

然后处理43实例审计中剩下的耳朵完整性、眼白旧虹膜痕、眼睑折点、虹膜/嘴唇浅边、花饰及脖子衣服混色。右发与右衣服补底已由 v4 修过，勿按历史表重复覆盖。

最后改善真实头部上下与左右透视、身体左右侧摆和前后仰，以及头发分层滞后。保持发根锚定、发尾连续，颜色与黑线同步。近远眼宽、眼距、瞳孔、鼻口、下颌和脖子必须协同，不靠拉伸整脸、拉长脖子实现转头。每阶段复位至中性，抽查端点、中间及反向组合，保留回退工程。

模型修好后再进行 Windows 桌宠、Ollama、语音服务和实时嘴型联调。`desktop/README.md`、`desktop/CHAT.md` 含已有安装及服务步骤；先安装桌宠依赖，再选择 v4 runtime 验证基础加载。Windows安装、显卡透明渲染、麦克风、Ollama、用户音色整链路**尚未验收**。不要将按次录音实现描述为完整双工实时对话。

## 必须保留的用户要求

- 外形参照 [原视频](https://www.youtube.com/watch?v=ltAEA_Lq5Js)。主要结构是头顶、刘海、一对小双马尾、一对大双马尾。
- 按发流补成完整发片，每层有对应独立黑线；眉毛独立。旧侧面脸、头顶、刘海不复用到当前正面。
- LibTV已无预算，不自行发起付费生成。已同意工具无关材料检查替代必须使用 Photoshop 的要求，不重复询问。
- 此次授权上传当前成果用于 Windows AI 接手；后续日常修复不应每做完一步自动发布新 Release。
- 不用第三方模型或网页贴图动画冒充本角色真实 Live2D。素材许可和项目原有署名继续保留，不将本包标成新原创角色授权。

## 验证脚本提示

材料QA依赖 Pillow、numpy、opencv-python、scipy、psd-tools；运行QA还需 PyQt5、live2d-py。使用独立 Python 环境，不改用户训练环境。脚本从解压根目录运行；`check_native.py` 接收对应版本目录，其他脚本按其参数列表执行。可重跑 v5 `process-record/finish_material_qa.py`；不要无故重跑 `prepare.py` 覆盖PSD。脚本只作辅助，视觉检查与原生保存回读不可省略。

建议接手指令：先校验文件并打开 v4 工程与 v5 PSD，阅读本说明和逐层审计；从“四马尾导入与配对网格”继续，给出实际模型预览后再处理后发、头部透视和身体动作。
