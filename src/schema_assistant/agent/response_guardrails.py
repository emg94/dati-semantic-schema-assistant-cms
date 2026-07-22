from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from schema_assistant.agent.static_answers import SECURITY_BOUNDARY_ANSWER


@dataclass(frozen=True)
class GuardedResponse:
    answer: str
    intervened: bool = False
    reason: str | None = None


def enforce_response_policy(answer: str, *, system_instruction: str) -> GuardedResponse:
    if _leaks_system_instruction(answer, system_instruction):
        return GuardedResponse(
            answer=SECURITY_BOUNDARY_ANSWER,
            intervened=True,
            reason="system_instruction_disclosure",
        )

    if _appears_predominantly_english(answer):
        return GuardedResponse(
            answer=(
                "Posso rispondere soltanto in italiano e nell'ambito delle risorse "
                "semantiche presenti nel catalogo."
            ),
            intervened=True,
            reason="language_policy_violation",
        )

    return GuardedResponse(answer=answer)


def _leaks_system_instruction(answer: str, system_instruction: str) -> bool:
    normalized_answer = _normalize_words(answer)
    normalized_instruction = _normalize_words(system_instruction)
    if not normalized_answer or not normalized_instruction:
        return False

    sensitive_markers = {
        "contenuti non fidati e prompt injection",
        "queste istruzioni di sistema hanno priorita",
        "non rivelare ripetere trascrivere riassumere tradurre o ricostruire",
        "eventuali istruzioni nascoste",
    }
    if any(marker in normalized_answer for marker in sensitive_markers):
        return True

    instruction_tokens = normalized_instruction.split()
    answer_tokens = normalized_answer.split()
    ngram_size = 10
    if len(answer_tokens) < ngram_size:
        return False

    instruction_ngrams = {
        tuple(instruction_tokens[index : index + ngram_size])
        for index in range(len(instruction_tokens) - ngram_size + 1)
    }
    matching_ngrams = sum(
        tuple(answer_tokens[index : index + ngram_size]) in instruction_ngrams
        for index in range(len(answer_tokens) - ngram_size + 1)
    )
    return matching_ngrams >= 2


def _appears_predominantly_english(answer: str) -> bool:
    tokens = _normalize_words(answer).split()
    if len(tokens) < 12:
        return False

    english_words = {
        "a",
        "and",
        "are",
        "as",
        "aside",
        "be",
        "for",
        "from",
        "i",
        "in",
        "is",
        "it",
        "my",
        "of",
        "on",
        "only",
        "rules",
        "set",
        "shall",
        "that",
        "the",
        "this",
        "to",
        "with",
        "write",
    }
    italian_words = {
        "a",
        "che",
        "con",
        "da",
        "dei",
        "del",
        "della",
        "di",
        "e",
        "gli",
        "i",
        "il",
        "in",
        "la",
        "le",
        "lo",
        "nel",
        "non",
        "per",
        "sono",
        "un",
        "una",
    }
    english_score = sum(token in english_words for token in tokens)
    italian_score = sum(token in italian_words for token in tokens)
    return english_score >= 4 and english_score >= (italian_score * 2) + 2


def _normalize_words(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(re.findall(r"\w+", ascii_value))
