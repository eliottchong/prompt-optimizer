#!/usr/bin/env python3

from __future__ import annotations

import math
import sys
from pathlib import Path


MODEL = "gemini-2.5-flash"


class OptimizeError(RuntimeError):
    pass


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / 4) if text else 0


def build_request(prompt: str) -> str:
    return (
        "Optimize the prompt below for lower token count.\n"
        "Rules:\n"
        "- Preserve every requirement, fact, number, code block, URL, name, and requested output format.\n"
        "- Remove only redundancy, filler, and awkward wording.\n"
        "- Remove greetings and direct address like \"hey chat\", \"hi there\", or \"hello chat\".\n"
        "- Prefer key semantic words when safe, e.g. \"what will the weather be next week\" -> \"weather next week\".\n"
        "- Do not answer the prompt.\n"
        "- Return only the optimized prompt text.\n\n"
        "Prompt:\n"
        "<<<PROMPT\n"
        f"{prompt}\n"
        "PROMPT>>>"
    )


def choose_candidate(original: str, candidate: str) -> str:
    if estimate_tokens(candidate) < estimate_tokens(original):
        return candidate
    return original


def optimize_with_gemini(prompt: str) -> str:
    try:
        from google import genai
    except ImportError as exc:
        raise OptimizeError("Missing dependency: install google-genai.") from exc

    try:
        client = genai.Client()
        response = client.models.generate_content(
            model=MODEL,
            contents=build_request(prompt),
        )
    except Exception as exc:
        raise OptimizeError(f"Gemini request failed: {exc}") from exc

    candidate = (getattr(response, "text", "") or "").strip()
    if not candidate:
        raise OptimizeError("Gemini returned empty text.")

    return choose_candidate(prompt, candidate)


def read_prompt(args: list[str]) -> str:
    if len(args) > 1:
        raise OptimizeError("Usage: python3 prompt-optimizerv2.py [prompt-file]")

    if args:
        return Path(args[0]).read_text(encoding="utf-8")

    return sys.stdin.read()


def print_result(original: str, optimized: str) -> None:
    original_tokens = estimate_tokens(original)
    optimized_tokens = estimate_tokens(optimized)

    print(f"Original estimated tokens: {original_tokens}")
    print(f"Optimized estimated tokens: {optimized_tokens}")
    print(f"Estimated savings: {original_tokens - optimized_tokens}")
    print()
    print(optimized)


def self_test() -> int:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2
    assert choose_candidate("abcdefgh", "abcd") == "abcd"
    assert choose_candidate("abcd", "abcdefgh") == "abcd"
    request = build_request("hello")
    assert "Remove greetings and direct address" in request
    assert "weather next week" in request
    assert "Do not answer the prompt" in request
    print("self-test passed")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if args == ["--self-test"]:
        return self_test()

    try:
        prompt = read_prompt(args).strip()
        if not prompt:
            raise OptimizeError("No prompt provided. Pipe text in or pass a prompt file.")

        optimized = optimize_with_gemini(prompt)
    except OptimizeError as exc:
        print(exc, file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Could not read prompt file: {exc}", file=sys.stderr)
        return 2

    print_result(prompt, optimized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
