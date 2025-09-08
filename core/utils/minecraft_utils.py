import re

def strip_minecraft_formatting_codes(text: str) -> str:
    """
    Removes Minecraft formatting codes from a string.
    """
    # 正则表达式匹配 § 后面跟着一个十六进制字符 (0-9, a-f) 或 k, l, m, n, o, r
    pattern = re.compile(r'§[0-9a-fk-or]', re.IGNORECASE)
    return pattern.sub('', text)
