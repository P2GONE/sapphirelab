"""Syntactic text mutations (no LLM call required)."""
import random


def word_shuffle(text: str) -> str:
    words = text.split()
    if len(words) <= 2:
        return text
    middle = words[1:-1]
    random.shuffle(middle)
    return " ".join([words[0], *middle, words[-1]])


def spacing_mutation(text: str) -> str:
    out = []
    for ch in text:
        out.append(ch)
        if ch.isalpha() and random.random() < 0.25:
            out.append(" ")
    return "".join(out)


def punctuation_insert(text: str) -> str:
    out = []
    for ch in text:
        out.append(ch)
        if ch.isalpha() and random.random() < 0.08:
            out.append(random.choice([".", ",", "-", "'"]))
    return "".join(out)


def text_split_lines(text: str) -> str:
    words = text.split()
    if not words:
        return text
    chunk = max(1, len(words) // 4)
    return "\n".join(" ".join(words[i:i + chunk]) for i in range(0, len(words), chunk))


MUTATIONS = {
    "word_shuffle": word_shuffle,
    "spacing_mutation": spacing_mutation,
    "punctuation_insert": punctuation_insert,
    "text_split_lines": text_split_lines,
}


def apply_chain(text: str, chain) -> str:
    out = text
    for name in chain:
        fn = MUTATIONS.get(name)
        if fn:
            out = fn(out)
    return out
