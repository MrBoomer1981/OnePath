"""The user's settings of the radar: defaults here, changes in news.sqlite (the settings table), every value checked.

The app's «Настройки» change them through the API. A wrong value is refused with a message that says what is
expected; a stored value that no longer passes falls back to its default. The keys keep DEEper's `opps_` names (its
news part had a news lane too), so a database brought over from DEEper keeps its values.

The profile, against which each opportunity's fit is scored, is the user's own text: the default here is
deliberately neutral, since the repository is public, and the user writes theirs in «Настройки». Contacts never
reach the prompt (clean_profile()). A new profile has the open opportunities read again (opps._waiting()).
"""

import json
import logging
import re
import time
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from my_browser.news import db

logger = logging.getLogger(__name__)

TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
OPP_TYPES = {
    "hackathon": "хакатоны", "competition": "соревнования и олимпиады", "school": "школы и интенсивы",
    "internship": "стажировки", "fellowship": "исследовательские программы", "education": "программы с поступлением",
    "conference": "конференции, форумы и call for papers", "grant": "гранты и стипендии", "talk": "выступления",
    "exam": "экзамены и сертификаты", "other": "другое",
}
WEEKDAYS = {"mon": "понедельник", "tue": "вторник", "wed": "среда", "thu": "четверг", "fri": "пятница",
            "sat": "суббота", "sun": "воскресенье"}
DAILY = "daily"  # opps_digest_day: the app's list updated every day (a weekly digest of stage O3 left new ones waiting)
DEFAULT_PROFILE = (
    "Студент технического вуза в России, гражданин РФ. Интересы: искусственный интеллект, машинное обучение, анализ "
    "данных, программирование. Подходит: хакатоны и соревнования по ИИ и ML, школы, стажировки, исследовательские "
    "программы, конференции с подачей студенческих работ, гранты для студентов. Не подходит: акселераторы, "
    "стартап-студии, мероприятия без технической части.")
PROFILE_CHARS = (20, 3000)

# How each setting reads to the user in an error message.
LABELS = {
    "timezone": "часовой пояс", "opps_enabled": "возможности", "opps_digest_day": "день обновления списка",
    "opps_digest_time": "время обновления списка", "opps_window_days": "окно, дней",
    "opps_major_window_days": "окно крупных возможностей, дней", "opps_search": "поиск по вебу",
    "opps_types": "типы возможностей", "opps_budget_month_rub": "бюджет на LLM в месяц, ₽", "opps_profile": "профиль",
}


class SettingsError(ValueError):
    """A refused change; the message is for the user, in Russian."""


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timezone: str = "Europe/Moscow"
    opps_enabled: bool = True
    # The app's list of opportunities is updated once: every day, or one day a week (WEEKDAYS), at this time. The
    # names are those of DEEper's Telegram digest, which the morning update replaced on 26.10.2026.
    opps_digest_day: str = DAILY
    opps_digest_time: str = "08:00"
    opps_window_days: int = Field(92, ge=7, le=366)  # the app shows what is due at most this far ahead…
    opps_major_window_days: int = Field(183, ge=7, le=366)  # …an especially big opportunity this far
    opps_search: bool = True  # once a week the web is searched for what the sources missed (discover.py)
    opps_types: list[str] = list(OPP_TYPES)  # shown in the app; every type is collected and read
    opps_budget_month_rub: float = Field(30, ge=0, le=300)
    opps_profile: str = DEFAULT_PROFILE

    @field_validator("timezone")
    @classmethod
    def _timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ValueError, KeyError):  # ZoneInfoNotFoundError is a KeyError
            raise ValueError(f"«{value}» не найден, нужен вида Europe/Moscow") from None
        return value

    @field_validator("opps_digest_day")
    @classmethod
    def _weekday(cls, value: str) -> str:
        if value != DAILY and value not in WEEKDAYS:
            raise ValueError(f"«{value}» — нужен {DAILY} (каждый день) или день недели: {', '.join(WEEKDAYS)}")
        return value

    @field_validator("opps_digest_time")
    @classmethod
    def _opps_time(cls, value: str) -> str:
        return _check_time(value)

    @field_validator("opps_types")
    @classmethod
    def _types(cls, values: list[str]) -> list[str]:
        unknown = [v for v in values if v not in OPP_TYPES]
        if unknown:
            raise ValueError(f"нет типа «{unknown[0]}», есть: {', '.join(OPP_TYPES)}")
        return [t for t in OPP_TYPES if t in values]

    @field_validator("opps_profile")
    @classmethod
    def _profile(cls, value: str) -> str:
        value = value.strip()
        if not PROFILE_CHARS[0] <= len(value) <= PROFILE_CHARS[1]:
            raise ValueError(f"нужно от {PROFILE_CHARS[0]} до {PROFILE_CHARS[1]} знаков, сейчас {len(value)}")
        return value

    @property
    def opps_daily_budget_rub(self) -> float:
        """A tenth of the month: a backlog (the first runs after a deploy, a new profile) is read over a few days, a
        runaway loop stops the same day."""
        return self.opps_budget_month_rub / 10


CONTACTS = [
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),  # email
    re.compile(r"(?:https?://)?(?:t\.me|telegram\.me)/\S+|https?://\S+"),  # Telegram and other links
    re.compile(r"(?<!\w)@[A-Za-z][\w]{3,}"),  # a Telegram or other handle
]
PHONE = re.compile(r"\+?\d[\d\s()-]{8,}\d")


def clean_profile(text: str) -> str:
    """The profile as it goes into a prompt: without emails, links, handles and phone numbers."""
    for pattern in CONTACTS:
        text = pattern.sub("", text)
    text = PHONE.sub(lambda m: "" if sum(c.isdigit() for c in m.group(0)) >= 10 else m.group(0), text)
    text = re.sub(r"\s+([,.;:])", r"\1", " ".join(text.split()))  # what a removed contact left: «пишите , ,»
    return re.sub(r"([,;:])(?:\s*[,;:])+", r"\1", text)


def _check_time(value: str) -> str:
    if not TIME.match(value):
        raise ValueError(f"«{value}» — нужно время ЧЧ:ММ, например 09:00")
    return value


def explain(error: ValidationError) -> str:
    """One line per refused setting, in Russian: what is wrong and what is expected."""
    lines = []
    for problem in error.errors():
        field = str(problem["loc"][0]) if problem["loc"] else ""
        label = LABELS.get(field, field)
        kind, ctx = problem["type"], problem.get("ctx") or {}
        if kind == "extra_forbidden":
            text = f"нет такой настройки «{field}»"
            label = ""
        elif kind == "value_error":
            text = str(ctx.get("error") or problem["msg"])
        elif kind == "greater_than_equal":
            text = f"не меньше {ctx['ge']:g}"
        elif kind == "greater_than":
            text = f"больше {ctx['gt']:g}"
        elif kind == "less_than_equal":
            text = f"не больше {ctx['le']:g}"
        elif kind == "less_than":
            text = f"меньше {ctx['lt']:g}"
        elif kind.startswith("int_"):
            text = "нужно целое число"
        elif kind.startswith("float_"):
            text = "нужно число"
        elif kind.startswith("bool_"):
            text = "нужно да или нет"
        elif kind.startswith("list_"):
            text = "нужен список"
        elif kind.startswith("string_"):
            text = "нужен текст"
        else:
            text = problem["msg"]
        lines.append(f"{label}: {text}" if label else text)
    return "\n".join(lines)


def _stored() -> dict:
    with db.connect() as conn:
        return {row["key"]: json.loads(row["value"]) for row in conn.execute("SELECT key, value FROM settings")}


def is_set(key: str) -> bool:
    """The user has set this setting (it is stored), rather than living with its default."""
    return key in _stored()


def load() -> Settings:
    """Current settings; stored values that no longer pass are deleted, so their defaults apply."""
    stored = _stored()
    try:
        return Settings(**stored)
    except ValidationError as e:
        bad = {str(p["loc"][0]) for p in e.errors() if p["loc"]}
        logger.error("Settings: dropping stored %s (%s)", sorted(bad), explain(e).replace("\n", "; "))
        with db.transaction() as conn:
            conn.executemany("DELETE FROM settings WHERE key = ?", [(key,) for key in bad])
        return Settings(**{k: v for k, v in stored.items() if k not in bad})


def update(changes: dict) -> Settings:
    """Apply changes, or raise SettingsError saying what is wrong; nothing is stored then. A new profile is noted
    (`state.opps_profile_at`): the open opportunities are read again against it, within the budget."""
    current = load()
    try:
        merged = Settings(**{**current.model_dump(), **changes})
    except ValidationError as e:
        raise SettingsError(explain(e)) from None
    values = merged.model_dump()
    with db.transaction() as conn:
        for key in changes:
            conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                         (key, json.dumps(values[key], ensure_ascii=False)))
    if merged.opps_profile != current.opps_profile:  # after the transaction: set_state takes the same write lock
        db.set_state("opps_profile_at", time.time())
    return merged
