"""Module 1 - text preprocessing (tokenizer). Works for any script, incl. Kannada."""
import unicodedata


def tokenize(text):
    """Lowercase and cut text into word tokens.
    Keeps letters (L*), combining marks (M*) and digits (N*) so Indic words are not
    broken. Zero-width joiners (U+200C/U+200D) occur *inside* Kannada words and are
    ignored; every other character (space, punctuation, U+200B ...) separates words."""
    tokens, cur = [], []
    for ch in text.lower():
        if ch in "\u200c\u200d":
            continue
        if unicodedata.category(ch)[0] in "LMN":
            cur.append(ch)
        elif cur:
            tokens.append("".join(cur))
            cur = []
    if cur:
        tokens.append("".join(cur))
    return tokens
