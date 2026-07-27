# Style-Bert-VITS2 日文语音模型

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
