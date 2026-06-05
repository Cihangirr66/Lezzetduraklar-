# -*- coding: utf-8 -*-
MOJIBAKE_CHARS = ("þ", "ð", "ý", "Ý", "Þ", "Ð", "Ã", "Ä", "Å", "�")


def looks_like_turkish_mojibake(value):
    text = value or ""
    return any(char in text for char in MOJIBAKE_CHARS)


def repair_turkish_text(value):
    text = value or ""
    if not text or not looks_like_turkish_mojibake(text):
        return text

    for source_encoding in ("latin-1", "cp1252"):
        for target_encoding in ("cp1254", "iso8859-9"):
            try:
                candidate = text.encode(source_encoding).decode(target_encoding)
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            if candidate != text and not looks_like_turkish_mojibake(candidate):
                return candidate
    return text
