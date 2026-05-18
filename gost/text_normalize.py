from __future__ import annotations

import re

_SOFT_HYPHEN = "\u00ad"
_DASHES = "—–‐‑"

_GOST_IN_TEXT = re.compile(
    r"ГОСТ\s+(?:Р\s+)?\d+(?:\.\d+)*(?:\s*[-—–]\s*\d+)?",
    re.IGNORECASE,
)


def normalize_line(line: str) -> str:
    text = line.replace(_SOFT_HYPHEN, "").replace("\ufeff", "").strip()
    if not text:
        return ""

    text = text.replace("\u00a0", " ")
    for dash in _DASHES:
        text = text.replace(dash, "—")

    text = re.sub(r"(\w)-\s*$", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_block(text: str) -> str:
    if not text:
        return ""

    lines = [normalize_line(ln) for ln in text.splitlines()]
    merged = merge_lines(lines)
    text = "\n".join(merged)
    text = _repair_split_words(text)
    text = re.sub(r"\bТОСТ\b", "ГОСТ", text)
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_INCOMPLETE_ENDINGS = (
    "че",
    "ски",
    "ссы",
    "техниче",
    "проектныхтехн",
)


def _repair_split_words(text: str) -> str:
    def merge_match(match: re.Match[str]) -> str:
        left, right = match.group(1), match.group(2)
        if left.endswith((".", ",", ";", ":")):
            return match.group(0)
        if len(right) > 5:
            return match.group(0)
        if not any(left.lower().endswith(ending) for ending in _INCOMPLETE_ENDINGS):
            return match.group(0)
        if right[0].islower():
            return left + right
        return match.group(0)

    text = re.sub(
        r"\b([а-яё]{4,})\s+([а-яё]{2,6})\b",
        merge_match,
        text,
        flags=re.IGNORECASE,
    )
    replacements = {
        r"\bтеченио\b": "течение",
        r"\bссы\s+лки\b": "ссылки",
        r"\bпо\s+сле\b": "после",
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def merge_lines(lines: list[str]) -> list[str]:
    if not lines:
        return []

    paragraphs: list[str] = []
    buffer = ""

    for line in lines:
        if not line:
            if buffer:
                paragraphs.append(buffer)
                buffer = ""
            continue

        if not buffer:
            buffer = line
            continue

        if _should_join_lines(buffer, line):
            if buffer.endswith("-"):
                buffer = buffer[:-1] + line
            else:
                buffer = f"{buffer} {line}"
        else:
            paragraphs.append(buffer)
            buffer = line

    if buffer:
        paragraphs.append(buffer)
    return paragraphs


def _should_join_lines(previous: str, current: str) -> bool:
    if previous.endswith("-"):
        return True
    if previous[-1] in ",;:" and current[0].islower():
        return True
    if previous[-1] not in ".!?»\"" and current[0].islower():
        return True
    if len(previous) < 60 and not previous.endswith((".", "!", "?")):
        if current[0].islower() or current[0] in "иавсоку":
            return True
    return False


def normalize_title(title: str) -> str:
    text = normalize_block(title)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def repair_known_title(number: str, title: str, toc_title: str | None) -> str:
    if toc_title:
        return normalize_title(toc_title)
    cleaned = normalize_title(title)
    fixes = {
        "1": "Область применения",
        "2": "Нормативные ссылки",
    }
    if number in fixes and len(cleaned) < 12:
        return fixes[number]
    return cleaned


def strip_heading_prefix(body: str, number: str, title: str) -> str:
    if not body:
        return ""

    lines = body.splitlines()
    if not lines:
        return body

    first = normalize_line(lines[0])
    prefix = f"{number} {title}".strip()
    if first.startswith(f"{number} "):
        lines = lines[1:]
    elif first == number:
        lines = lines[1:]

    return normalize_block("\n".join(lines))
