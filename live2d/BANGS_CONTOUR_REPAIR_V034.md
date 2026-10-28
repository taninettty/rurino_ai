# 刘海发尖轮廓修正

上一版仅增加独立黑线，刘海颜色层和透明轮廓保持不变，因此发尖断口、锯齿和旧黑线残片仍然存在。本轮直接修正当前左视图刘海的中间 / 右侧发尖轮廓，并同步替换眼前刘海副本。

主文件：`Rurino_Bangs_Contour_Repaired_v034.psd`，3456 × 2816，54 个像素层。

## 已修改

- 顺着现有发流重建不等长发尖的曲线，保持中间刘海连续，没有新增矩形切片。
- 清理旧轮廓附近的黑线残片，局部颜色从相邻头发推断补齐，再生成独立 `Ink_Crown` 线层。
- 对左上连接处的小缺口补回原画中的头发像素。
- 同步更新 `Left_Fringe_EyeOverlap_SOURCE`、`RightFringe_ForegroundTips_SOURCE` 及对应黑线；眼睛上方使用同一轮廓。
- 新增 `Fringe_Edge_Skin_Underlap_LOCAL` 局部肤色补底。原脸部按旧发边裁切，改发尖后需要窄幅补底；该层在眼睛层下方，不覆盖眼睛，也不重新绘制脸型。

6 个已有像素层修改，新增 1 个局部补底；其余 47 个图层的 RGBA、位置、混合、透明度、可见性与剪贴属性逐项保持一致，包含全部五官与独立眉毛。

## 检查与边界

- 保存回读的 7 个输出层与 PNG 一致，PSD 默认合成与预览一致。
- 刘海保持一个主要连通区域，无封闭针孔。
- 检查睁眼、半闭眼、闭眼三种静态合成；修边没有新增透明露底缝隙。
- 边缘颜色与肤色补底含局部推断，并非恢复不可见原画。原视频用于造型参考，本轮没有生成新角色图。
- 本轮完成的是下部刘海发尖与相关遮挡；上部共用发根仍保持原有归属，右侧发根补片的完整形状不宣称已重做。内部阴影线与发尖的衔接可继续精修。
- 这是当前左视图的静态 PSD 材料；尚未新增 Cubism 网格、转头、抬低头、身体侧摆或头发物理。运行模型仍为旧稿。

输入 SHA256：`c65494958a7b3059252d5d530547fb040e2c3d1a58fd69d6a73dc06c1253a65c`

输出 SHA256：`6122418d6a8495c0da38217de40b3ffa98eee6d58624f9a178fe9f1a0ef015c5`

## 使用与重建

直接打开主 PSD 即可编辑。默认显示 `02_Open`，其余眼型组仅单独开启其中之一。头发颜色层与 `Ink_` 线层仍可分别调整。

包内保留上一版 PSD、原画取色参考、重建脚本和所需预览。安装 `production/requirements-materials-v034.txt` 后，先运行 `python production/repair_bangs_contours_v34.py`，再运行 `python production/repair_bangs_contours_v34.py --build`。预览字体使用 Linux Noto CJK，其他系统可修改 `outline_hair_layers_v34.py` 内的 `FONT` 路径。

![发尖前后对比](preview/bangs-tips-detail-v0.3.4.jpg)

![整头前后对比](preview/bangs-head-comparison-v0.3.4.jpg)

![三种眼型](preview/bangs-eye-states-v0.3.4.jpg)
