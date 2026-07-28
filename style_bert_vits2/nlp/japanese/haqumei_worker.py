"""
haqumei G2P 后端包装器

haqumei 是基于 Rust 的现代日语 G2P 库，提供更准确的重音标注和韵律信息。
这个包装器将 haqumei 的 API 转换为与 pyopenjtalk 兼容的格式，
以便无缝集成到 Style-Bert-VITS2 框架中。
"""
from typing import Optional
from haqumei import Haqumei, PitchAccent

# 全局 haqumei 实例
_haqumei_instance: Optional[Haqumei] = None


def get_haqumei() -> Haqumei:
    """获取全局 haqumei 实例（懒加载）"""
    global _haqumei_instance
    if _haqumei_instance is None:
        _haqumei_instance = Haqumei()
    return _haqumei_instance


def g2p_prosody(text: str) -> list[str]:
    """
    从文本提取音素 + 韵律符号序列。
    返回格式与 pyopenjtalk_g2p_prosody 兼容：
    ['^', 'k', 'o', '[', 'N', 'n', 'i', 'ch', 'i', 'w', 'a', '$']
    
    使用 haqumei 的音高信息来生成韵律符号：
    - '[': 音高上升（Low -> High）
    - ']': 音高下降（High -> Low）
    - '#': 短语边界
    
    Args:
        text (str): 输入文本
        
    Returns:
        list[str]: 音素和韵律符号的列表
    """
    h = get_haqumei()
    
    # 使用 g2p_mapping_prosody 获取详细的韵律信息
    mapping = h.g2p_mapping_prosody(text)
    
    result = ['^']  # 开头标记
    
    previous_pitch = None
    
    for word_detail in mapping:
        if word_detail.is_ignored:
            continue
            
        phonemes = word_detail.phonemes
        
        for phoneme_obj in phonemes:
            phoneme = phoneme_obj.phoneme
            
            if phoneme is None:
                continue
                
            # 处理特殊音素
            if phoneme == 'pau':
                result.append('_')
                previous_pitch = None
                continue
            
            # 获取当前音素的音高
            current_pitch = phoneme_obj.pitch
            
            # 根据音高变化添加韵律符号
            if previous_pitch is not None and current_pitch is not None:
                # Low -> High: 添加上升符号
                if previous_pitch == PitchAccent.Low and current_pitch == PitchAccent.High:
                    result.append('[')
                # High -> Low: 添加下降符号
                elif previous_pitch == PitchAccent.High and current_pitch == PitchAccent.Low:
                    result.append(']')
            
            # 处理无声母音：将大写 AEIOU 转换为小写 aeious（与 pyopenjtalk 的 drop_unvoiced_vowels=True 行为一致）
            if phoneme in "AEIOU":
                phoneme = phoneme.lower()
            
            # 添加音素
            result.append(phoneme)
            
            # 更新前一个音高
            previous_pitch = current_pitch
            
        # 单词边界检查（如果下一个单词的音高与当前不同）
        # 简化处理：每个单词后可能需要边界符号
    
    # 添加结尾标记
    result.append('$')
    
    return result


def g2p(text: str) -> list[str]:
    """
    获取纯音素序列（不含韵律符号）
    
    Args:
        text (str): 输入文本
        
    Returns:
        list[str]: 音素列表
    """
    h = get_haqumei()
    return h.g2p(text)


def run_frontend(text: str) -> list[dict]:
    """
    模拟 pyopenjtalk.run_frontend 的输出格式
    
    Args:
        text (str): 输入文本
        
    Returns:
        list[dict]: 解析结果列表，每个元素包含 'string' 和 'pron' 字段
    """
    h = get_haqumei()
    mapping = h.g2p_mapping_prosody(text)
    
    result = []
    
    for word_detail in mapping:
        if word_detail.is_ignored:
            continue
            
        word = word_detail.word
        pron = word_detail.pron  # 使用 pron 字段（实际发音）
        
        # 处理助词「は」「を」「へ」的特殊发音
        if word == 'は':
            pron = 'ワ'
        elif word == 'を':
            pron = 'ヲ'
        elif word == 'へ':
            pron = 'エ'
            
        # 处理标点符号：返回「、」作为 pron，让 g2p.py 的逻辑处理
        # pyopenjtalk 对标点返回「、」，g2p.py 会将其转换为原始标点
        import re
        if re.match(r'^[！？。，、；：""''（）\-\—…]+$', word):
            pron = '、'
            
        result.append({
            'string': word,
            'pron': pron
        })
        
    return result


def make_label(labels: list[dict]) -> list[str]:
    """
    模拟 pyopenjtalk.make_label 的输出格式
    由于 haqumei 不使用 full-context labels，这里返回简化版
    
    Args:
        labels (list[dict]): run_frontend 的输出
        
    Returns:
        list[str]: 简化的标签列表
    """
    return [f"{label['string']}/{label['pron']}" for label in labels]


def main():
    """测试 haqumei 包装器"""
    test_texts = [
        "こんにちは、私はAIです。",
        "今日はいい天気ですね。",
        "がじょうせん、かかでらしゃい",
        "とても嬉しい",
    ]
    
    print("=" * 60)
    print("haqumei G2P 包装器测试")
    print("=" * 60)
    
    for text in test_texts:
        print(f"\n原文: {text}")
        print(f"g2p: {g2p(text)}")
        print(f"g2p_prosody: {g2p_prosody(text)}")
        print(f"run_frontend: {run_frontend(text)}")


if __name__ == "__main__":
    main()
