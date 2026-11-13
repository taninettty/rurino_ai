# Style-Bert-VITS2 日文语音模型（瑠璃乃 / rurino_1）

基于 Style-Bert-VITS2 **2.7.0-JP-Extra** 的单说话人日语模型，声音来自《莲之空》系列中瑠璃乃的日语音声。

- 训练数据：1258 段 / 2.90 小时游戏原声（44.1 kHz 单声道，人工校对文本）
- 训练量：25 epoch / 14,583 step，JP-Extra base 初始化，fp32
- 验证：留出集说话人余弦 **0.799**（旧版 0.666），时长比 0.84
- 更新日期：2026-11-13

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

`infer_final.py` 默认从 `d:\taninety002\22\Style-Bert-VITS2` 加载框架代码；换机器时设置环境变量
`SBV2_ROOT` 指向你的 Style-Bert-VITS2 目录即可。

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
- `model_assets/speaker_1/rurino_1_e25_s14583.safetensors` - 模型权重（Git LFS）
- `model_assets/speaker_1/config.json` - 模型配置（含 spk2id / style2id）
- `model_assets/speaker_1/style_vectors.npy` - Neutral 风格向量（1×256）
- `samples/` - 样音（游戏文本 / 直播文本）
- `bert/deberta-v2-large-japanese-char-wwm/` - 日语 BERT 模型

## 版本对比

| 模型 | 游戏域余弦 | 说明 |
| --- | ---: | --- |
| **rurino_1（本仓库）** | **0.799** | 25 epoch，正式版本 |
| speaker_1_e24_s25000（旧） | 0.666 | 旧版，语速偏快约 30% |
| rurino_union | 0.749 | 并入 4.1 小时直播数据（实验） |
| rurino_final | 0.805 | 并集 + 干净收尾（实验，主观略逊） |

## 已知限制

- 语料仅 2.90 小时，专有名词、数字读法、生僻汉字可能读错。
- 输入含「大沢瑠璃乃」等姓名时 `clean_text` 可能报 `Cannot read: 乃`，建议改用假名（おおさわるりの）或在前端替换。
- 未做降噪/响度归一化，底噪水平与原声一致。
