"""字幕处理器测试 - 重点验证分词分隔符正则表达式的正确性"""

import re

from backend.utils.subtitle_processor import SubtitleProcessor


def _split(text: str):
    """用处理器的分隔符正则切分文本，去掉空片段（与生产代码一致）"""
    sp = SubtitleProcessor()
    parts = re.split(sp.word_separators, text)
    return [p for p in parts if p.strip()]


def test_word_separators_is_single_clean_character_class():
    """分隔符应为单一、正确闭合的字符类，且包含全部预期的中文标点与空白。

    历史 bug：内嵌的 ASCII 单引号会把字面量提前截断并隐式拼接成两段字符串，
    导致单引号从字符类中丢失，并触发 `\\s` 的 SyntaxWarning。
    """
    separators = SubtitleProcessor().word_separators

    # 必须是一个完整的字符类 [....]+
    assert separators.startswith("[")
    assert separators.endswith("]+")

    # 全部预期分隔符都应在字符类内（含中文弯引号 “”‘’ 与空白 \s）
    for ch in "，。！？；：“”‘’（）【】、":
        assert ch in separators, f"分隔符缺少字符: {ch!r}"
    assert r"\s" in separators

    # 正则本身可被编译（无语法错误）
    assert re.compile(separators)


def test_splits_cjk_string_on_punctuation_and_whitespace():
    """对包含中文标点和空白的样本字符串，应按预期切分出干净的词片段。"""
    sample = "你好，世界！这是“测试”‘单引号’；（括号）【中括号】、还有 空格\t制表符。"
    assert _split(sample) == [
        "你好",
        "世界",
        "这是",
        "测试",
        "单引号",
        "括号",
        "中括号",
        "还有",
        "空格",
        "制表符",
    ]


def test_curly_quotes_act_as_separators():
    """回归测试：弯单/双引号必须作为分隔符生效（旧实现中单引号会丢失）。"""
    assert _split("前“引用”后") == ["前", "引用", "后"]
    assert _split("前‘引用’后") == ["前", "引用", "后"]
