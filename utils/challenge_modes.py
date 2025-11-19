from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Sequence, Tuple


PLAYER_AGE_INDEX = 5
PLAYER_PRICE_INDEX = 6


def _safe_int(value) -> int | None:
    try:
        return int(value)
    except Exception:
        try:
            return int(float(str(value)))
        except Exception:
            return None


def _age_upto_23(player_row: Sequence) -> bool:
    age_value = _safe_int(player_row[PLAYER_AGE_INDEX])
    return age_value is not None and age_value <= 23


def _price_equals_10(player_row: Sequence) -> bool:
    price_value = _safe_int(player_row[PLAYER_PRICE_INDEX])
    return price_value == 10


@dataclass(frozen=True)
class ChallengeMode:
    code: str
    button_title: str
    prompt_line: str
    summary_label: str
    info_label: str
    restriction_hint: str
    no_player_hint: str
    player_filter: Callable[[Sequence], bool]
    aliases: Tuple[str, ...] = ()

    def is_player_allowed(self, player_row: Sequence) -> bool:
        try:
            return bool(self.player_filter(player_row))
        except Exception:
            return False

    def matches_text(self, text: str) -> bool:
        normalized = (text or "").strip().lower()
        if not normalized:
            return False
        return normalized == self.code or normalized in self.aliases


_CHALLENGE_MODES: Tuple[ChallengeMode, ...] = (
    ChallengeMode(
        code="default",
        button_title="Обычный режим",
        prompt_line="обычный (все игроки)",
        summary_label="Режим: обычный",
        info_label="обычный",
        restriction_hint="",
        no_player_hint="",
        player_filter=lambda _: True,
        aliases=("обычный", "regular", "default", "standard", "standart"),
    ),
    ChallengeMode(
        code="under23",
        button_title="U23 режим",
        prompt_line="U23 (только игроки не старше 23 лет)",
        summary_label="Режим: только U23",
        info_label="U23",
        restriction_hint="Режим U23: доступны только игроки 23 лет и младше.",
        no_player_hint="Режим U23 допускает только игроков 23 лет и младше.",
        player_filter=_age_upto_23,
        aliases=("u23", "under23", "23"),
    ),
    ChallengeMode(
        code="price10",
        button_title="Стоимость 10",
        prompt_line="Стоимость 10 (игроки ценой ровно 10 HC)",
        summary_label="Режим: стоимость 10",
        info_label="стоимость 10",
        restriction_hint="Режим Стоимость 10: доступны только игроки с ценой ровно 10 HC.",
        no_player_hint="В этом режиме доступны только игроки со стоимостью ровно 10 HC.",
        player_filter=_price_equals_10,
        aliases=("price10", "стоимость 10", "цена 10", "10"),
    ),
)

_MODE_BY_CODE: Dict[str, ChallengeMode] = {mode.code: mode for mode in _CHALLENGE_MODES}


def iter_challenge_modes() -> Tuple[ChallengeMode, ...]:
    return _CHALLENGE_MODES


def available_mode_codes() -> Tuple[str, ...]:
    return tuple(_MODE_BY_CODE.keys())


def get_challenge_mode(code: str | None) -> ChallengeMode:
    normalized = (code or "default").strip().lower()
    return _MODE_BY_CODE.get(normalized, _MODE_BY_CODE["default"])


def normalize_challenge_mode(code: str | None) -> str:
    return get_challenge_mode(code).code


def find_mode_by_text(text: str | None) -> ChallengeMode | None:
    normalized = (text or "").strip().lower()
    if not normalized:
        return None
    for mode in _CHALLENGE_MODES:
        if mode.matches_text(normalized):
            return mode
    return None
