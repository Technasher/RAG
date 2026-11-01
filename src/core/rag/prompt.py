from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.core.config import settings


SYSTEM_PROMPT = """Ты — официальный помощник университета.
Отвечай ТОЛЬКО на основе предоставленного контекста.
Если в контексте нет ответа — честно скажи: «Я не нашёл этой информации в базе знаний».
Не выдумывай факты, даты, имена и номера.
Отвечай кратко, по-русски, без воды.
Если уместно — ссылайся на источники в формате [1], [2]."""


_DAYS_RU = ["понедельник", "вторник", "среда", "четверг",
            "пятница", "суббота", "воскресенье"]
_MONTHS_RU = ["января", "февраля", "марта", "апреля", "мая", "июня",
              "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def _compute_week(now: datetime) -> dict:
    """
    Возвращает:
      {"week_number": int, "week_type": "числитель"|"знаменатель"|"",
       "status": "active"|"before"|"override"}
    """
    # 1. Ручной override — для тестов
    override = (settings.week_type_override or "").strip().lower()
    if override in {"числитель", "знаменатель"}:
        return {
            "week_number": 0,
            "week_type": override,
            "status": "override",
        }

    # 2. Автоматический расчёт от начала семестра
    try:
        semester_start = date.fromisoformat(settings.semester_start_date)
    except ValueError:
        return {"week_number": 0, "week_type": "", "status": "before"}

    days_diff = (now.date() - semester_start).days
    if days_diff < 0:
        return {"week_number": 0, "week_type": "", "status": "before"}

    week_number = days_diff // 7 + 1
    is_odd = week_number % 2 == 1
    is_numerator = is_odd if settings.first_week_is_numerator else not is_odd

    return {
        "week_number": week_number,
        "week_type": "числитель" if is_numerator else "знаменатель",
        "status": "active",
    }


def format_now(tz: str | None = None) -> str:
    """Строка вида: 'Сейчас: среда, 29 октября 2026 г., 14:32 (Europe/Moscow).
    Текущая учебная неделя: 9-я, числитель.'"""
    tz = tz or settings.default_timezone
    now = datetime.now(ZoneInfo(tz))

    date_part = (
        f"Сейчас: {_DAYS_RU[now.weekday()]}, "
        f"{now.day} {_MONTHS_RU[now.month - 1]} {now.year} г., "
        f"{now.strftime('%H:%M')} ({tz})."
    )

    week = _compute_week(now)

    if week["status"] == "before":
        return date_part + " Учебный семестр ещё не начался."

    if week["status"] == "override":
        return date_part + f" Текущая учебная неделя: {week['week_type']} (задано вручную)."

    if week["status"] == "active":
        return date_part + (
            f" Текущая учебная неделя: {week['week_number']}-я, "
            f"{week['week_type']}."
        )

    return date_part


def build_system_prompt(tz: str | None = None) -> str:
    """System prompt + время + тип недели. Вызывается на каждый запрос."""
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"{format_now(tz)}\n"
        "Используй эти данные, если пользователь спрашивает про «сегодня», "
        "«завтра», «сейчас», «на этой неделе» или актуальность расписания.\n"
        "ВАЖНО: расписание может отличаться для недель «числитель» и "
        "«знаменатель». Если пользователь спрашивает про «эту неделю» — "
        "отвечай для текущего типа недели. Если спрашивает про «следующую» — "
        "переключай тип (числитель ↔ знаменатель)."
    )


def build_context(hits, max_chars: int = 6000) -> str:
    parts: list[str] = []
    total = 0
    for i, hit in enumerate(hits, start=1):
        block = f"[{i}] {hit.title}\n{hit.content}"
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)
    return "\n\n".join(parts)


def build_messages(
    question: str,
    hits,
    history: list[dict] | None = None,
    tz: str | None = None,
) -> list[dict]:
    context = build_context(hits)
    user_content = f"Контекст:\n{context}\n\nВопрос пользователя: {question}"

    messages: list[dict] = [{"role": "system", "content": build_system_prompt(tz)}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_content})
    return messages
