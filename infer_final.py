"""
Rurino AI - 日文角色语音合成模型推理脚本
基于 Style-Bert-VITS2 JP-Extra 训练的日文角色语音合成模型

用法:
  python infer_final.py "こんにちは"
  python infer_final.py "がじょうせん、かかでらしゃい" --noise 0.03
  python infer_final.py "こんにちは" --output output.wav
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))
# 添加 Style-Bert-VITS2 框架路径
sys.path.insert(0, str(Path(__file__).parent / "Style-Bert-VITS2"))

import argparse
import soundfile as sf

from style_bert_vits2.constants import Languages
from style_bert_vits2.tts_model import TTSModel

# 路径配置（相对路径，便于在任何位置使用）
ROOT = Path(__file__).parent
ASSETS_DIR = ROOT / "model_assets" / "speaker_1"
OUTPUT_DIR = ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 最终模型
MODEL_PATH = ASSETS_DIR / "speaker_1_e24_s25000.safetensors"
CONFIG_PATH = ASSETS_DIR / "config.json"
STYLE_VEC_PATH = ASSETS_DIR / "style_vectors.npy"

def generate(text, sdp_ratio=0.3, noise=0.05, noise_w=0.05, length=1.0, 
             pitch_scale=1.0, intonation_scale=1.0, output_path=None):
    """生成语音"""
    # 加载模型（首次调用）
    if not hasattr(generate, 'model'):
        print(f"加载模型: {MODEL_PATH.name}")
        generate.model = TTSModel(
            model_path=MODEL_PATH,
            config_path=CONFIG_PATH,
            style_vec_path=STYLE_VEC_PATH,
            device="cuda",
        )
        print("模型加载完成！")
    
    print(f"生成: {text}")
    sr, audio = generate.model.infer(
        text=text,
        language=Languages.JP,
        speaker_id=0,
        reference_audio_path=None,
        style="Neutral",
        style_weight=1.0,
        sdp_ratio=sdp_ratio,
        noise=noise,
        noise_w=noise_w,
        length=length,
        line_split=True,
        split_interval=0.5,
        pitch_scale=pitch_scale,
        intonation_scale=intonation_scale,
    )
    
    # 确定输出路径
    if output_path:
        out_path = Path(output_path)
    else:
        import hashlib
        text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
        out_path = OUTPUT_DIR / f"output_{text_hash}.wav"
    
    # 确保输出目录存在
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    sf.write(str(out_path), audio, sr, subtype="PCM_16")
    dur = len(audio) / sr
    print(f"输出: {out_path} ({dur:.2f}s)")
    
    return out_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rurino AI - 日文语音生成（e24模型）")
    parser.add_argument("text", help="要生成的日文文本")
    parser.add_argument("--sdp_ratio", type=float, default=0.3, help="时长随机性 (0-1)")
    parser.add_argument("--noise", type=float, default=0.05, help="噪声注入强度")
    parser.add_argument("--noise_w", type=float, default=0.05, help="噪声权重")
    parser.add_argument("--length", type=float, default=1.0, help="语速 (>1=慢)")
    parser.add_argument("--pitch_scale", type=float, default=1.0, help="音高缩放")
    parser.add_argument("--intonation_scale", type=float, default=1.0, help="语调缩放")
    parser.add_argument("--output", type=str, default=None, help="输出文件路径")
    args = parser.parse_args()
    
    generate(
        args.text,
        sdp_ratio=args.sdp_ratio,
        noise=args.noise,
        noise_w=args.noise_w,
        length=args.length,
        pitch_scale=args.pitch_scale,
        intonation_scale=args.intonation_scale,
        output_path=args.output,
    )
