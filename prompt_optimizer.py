"""
Prompt optimizer — clean and lightly structure raw prompts.

Implements the workflow described in the project spec: greet, recommend
format, then run heuristic cleaning steps.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Final

# Spelled-out numbers -> digits (longer tokens first to avoid partial matches)
_NUMBER_WORDS: Final[tuple[tuple[str, str], ...]] = (
    # compounds and teens (match before simpler words)
    ("twenty-eight", "28"),
    ("twenty-seven", "27"),
    ("twenty-six", "26"),
    ("twenty-five", "25"),
    ("twenty-four", "24"),
    ("twenty-three", "23"),
    ("twenty-two", "22"),
    ("twenty-one", "21"),
    ("twenty", "20"),
    ("nineteen", "19"),
    ("eighteen", "18"),
    ("seventeen", "17"),
    ("sixteen", "16"),
    ("fifteen", "15"),
    ("fourteen", "14"),
    ("thirteen", "13"),
    ("twelve", "12"),
    ("eleven", "11"),
    ("ten", "10"),
    ("nine", "9"),
    ("eight", "8"),
    ("seven", "7"),
    ("six", "6"),
    ("five", "5"),
    ("four", "4"),
    ("three", "3"),
    ("two", "2"),
    ("one", "1"),
    ("zero", "0"),
    ("thirty", "30"),
    ("forty", "40"),
    ("fifty", "50"),
    ("sixty", "60"),
    ("seventy", "70"),
    ("eighty", "80"),
    ("ninety", "90"),
    ("hundred", "100"),
)

_FILLER_PHRASES: Final[tuple[str, ...]] = (
    "please",
    "thank you",
    "thanks",
    "hello",
    "hi",
    "it is",
    "this is",
    "start by",
    "begin by",
    "i need you to",
    "i want you to",
    "i want to",
    "claude",
    "gemini",
    "chatgpt",
    "what's",
    "what is the",
    "what",
    "of these",
    "are",
    "when you conduct your analysis, include",
    "as well as",
)
# Each entry is stripped only when it appears as a whole word or run of whole
# words (never as a substring inside a larger token). Matching is
# case-insensitive (e.g. Please, THANK YOU, i NeEd YoU tO). Multi-word
# phrases tolerate any stretch of whitespace between the words.


def _filler_regex_for_phrase(phrase: str) -> re.Pattern[str]:
    """Case-insensitive whole-word(s) match; internal gaps allow any whitespace."""
    words = phrase.split()
    if not words:
        return re.compile("(?!.)")
    core = r"\s+".join(re.escape(w) for w in words)
    return re.compile(rf"(?i)(?<!\w){core}(?!\w)")


_FILLER_COMPILED: Final[tuple[re.Pattern[str], ...]] = tuple(
    _filler_regex_for_phrase(p) for p in sorted(_FILLER_PHRASES, key=len, reverse=True)
)


def _strip_whitespace(prompt: str) -> str:
    return prompt.strip()


def _break_long_sentences(text: str, max_words: int = 20) -> str:
    """
    Between sentence boundaries (. ! ?): if word count > max_words,
    replace ' and ', ' or ', ' but ' with newlines (spec).
    """
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    rebuilt: list[str] = []
    for sent in sentences:
        if not sent.strip():
            continue
        words = sent.split()
        if len(words) <= max_words:
            rebuilt.append(sent)
            continue
        s = sent
        for conj in (" and ", " or ", " but ", "however","as well as"):
            s = re.sub(re.escape(conj), "\n", s, flags=re.IGNORECASE)
        rebuilt.append(s)
    return " ".join(rebuilt)


def _dash_prefix_lines(text: str) -> str:
    """After each newline, ensure lines start with '- ' (markdown-style)."""
    lines = text.split("\n")
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append("")
            continue
        if stripped.startswith("-") or stripped.startswith("*"):
            result.append(stripped)
        else:
            result.append(f"- {stripped}")
    return "\n".join(result)


def _spell_numbers_to_digits(text: str) -> str:
    out = text
    for word, digit in _NUMBER_WORDS:
        pattern = rf"\b{re.escape(word)}\b"
        out = re.sub(pattern, digit, out, flags=re.IGNORECASE)
    return out


def _remove_filler(text: str) -> str:
    out = text
    for pat in _FILLER_COMPILED:
        out = pat.sub("", out)
    return re.sub(r"\s{2,}", " ", out).strip()


def _collapse_adjacent_dots(text: str) -> str:
    """
    Remove a redundant ``.`` when it follows another ``.`` directly (``..``)
    or only separated by whitespace (``. .``), using ``list.pop()`` on the
    latter dot.
    """
    chars = list(text)
    i = 0
    while i < len(chars):
        if chars[i] != ".":
            i += 1
            continue
        nxt = i + 1
        if nxt < len(chars) and chars[nxt] == ".":
            chars.pop(nxt)
            continue
        j = nxt
        while j < len(chars) and chars[j].isspace():
            j += 1
        if j < len(chars) and chars[j] == ".":
            chars.pop(j)
            continue
        i += 1
    return "".join(chars)


def token_counter(x: str) -> float:
    """
    Rough token estimate for English-ish LLM context (not tokenizer-exact).

    Heuristics combined:
    - ~1 token per 4 characters
    - ~1 token per ¾ word (i.e. tokens ≈ words / 0.75; 100 tokens ≈ 75 words)
    - Order-of-magnitude checks: ~30 tokens for 1–2 sentences, ~100 per paragraph,
      ~2048 tokens for ~1,500 words (used to sanity-check the blend)

    Uses the mean of the character-based and word-based estimates.
    """
    if not x:
        return 0.0
    char_est = len(x) / 4.0
    word_est = len(x.split()) / 0.75
    return (char_est + word_est) / 2.0


def clean_prompt(prompt: str) -> str:
    """
    1. Strip outer whitespace.
    2. Long sentences (>20 words between sentence boundaries): split on and/or/but -> newlines.
    3. Prefix non-empty lines with '- ' where missing.
    4. Replace common spelled-out number words with digits.
    5. Remove light filler phrases.
    6. Remove a later ``.`` when it immediately follows ``.`` or ``.`` + whitespace.
    7. Return cleaned prompt.
    """
    s = _strip_whitespace(prompt)
    s = _break_long_sentences(s)
    s = _dash_prefix_lines(s)
    s = _spell_numbers_to_digits(s)
    s = _remove_filler(s)
    s = _collapse_adjacent_dots(s)
    return s.strip()


def main() -> None:
    print("Hello user, we recommend you follow the format:")
    print("Role -> Context -> Task -> Constraints -> Output format")

    if len(sys.argv) > 1:
        raw = Path(sys.argv[1]).read_text(encoding="utf-8")
    else:
        print("\nPaste your prompt (end with Ctrl+Z then Enter on Windows, or Ctrl+D on Unix):", flush=True)
        raw = sys.stdin.read()

    cleaned = clean_prompt(raw)
    print(f"Raw token count: {token_counter(raw)}")
    print(f"Cleaned token count: {token_counter(cleaned)}")
    print(f"Cleaned prompt: {cleaned}")


if __name__ == "__main__":
    main()
