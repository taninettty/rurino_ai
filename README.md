# Style-Bert-VITS2 日文语音模型

## 瑠璃乃 Live2D 制作

[当前制作目标与下一步](live2d/CURRENT_WORK.md)：按“先拆完、最后统一修”的顺序，新增[刘海、贴脸发和长马尾拆分初稿](live2d/REMAINING_HAIR_SPLIT_V034.md)，6 个原图层拆成 18 个可见部件，提供 72 层 PSD。三个表情状态拼回原图完全一致；补根、边缘和整体修形留待统一处理。

[人物素材与 Cubism 交接](live2d/README.md) · [桌宠模型接入程序](desktop/README.md)。已提供 [v0.3.3 可运行绑定测试稿](live2d/RIG_DRAFT.md)，支持眨眼、口型与小幅转头；头发边缘和变形仍在精修。

## 使用方法

### 1. 安装依赖
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 生成语音
```bash
python infer_final.py "こんにちは"
python infer_final.py "がじょうせん、かかでらしゃい" --noise 0.03
```

### 参数说明
| 参数 | 默认值 | 说明 |
|------|--------|------|
| --sdp_ratio | 0.3 | 时长随机性 |
| --noise | 0.05 | 噪声注入，减少机械音 |
| --noise_w | 0.05 | 噪声权重 |
| --length | 1.0 | 语速，<1=快，>1=慢 |
| --pitch_scale | 1.0 | 音高缩放 |
| --intonation_scale | 1.0 | 语调缩放 |

## 文件说明
- speaker_1_e24_s25000.safetensors - 模型权重
- config.json - 模型配置
- style_vectors.npy - 风格向量
- bert/deberta-v2-large-japanese-char-wwm/ - BERT模型
