from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Intent:
    key: str
    label: str                    # текст на кнопке
    answer: str                   # заготовленный ответ
    document_external_id: str | None = None   # какой файл прикрепить
    attach_always: bool = False
    related: list[str] = field(default_factory=list)  # другие intent'ы для quick_replies


INTENTS: dict[str, Intent] = {
    "start": Intent(
            key="start",
            label="👋 Начать",
            answer="Здравствуйте! Чем могу помочь?",
            related=["show_schedule", "admission", "contacts"],
        ),
    "show_schedule": Intent(
        key="show_schedule",
        label="📅 Расписание",
        answer="Актуальное расписание занятий — во вложении.",
        document_external_id="Расписание занятий ПМиИ-251 ПМиИ-252 ПМиИА-251.pdf",
        attach_always=True,
        related=["admission", "contacts"],
    ),
    "admission": Intent(
        key="admission",
        label="🎓 Приёмная комиссия",
        answer=(
            "Приёмная комиссия работает с 9:00 до 18:00, обед 13:00–14:00.\n"
            "Телефон: +7 (999) 123-45-67. Адрес: ул. Университетская, 1."
        ),
        related=["show_schedule", "contacts"],
    ),
    "contacts": Intent(
        key="contacts",
        label="📞 Контакты",
        answer="Телефон приёмной: +7 (999) 123-45-67. Email: info@university.ru",
        related=["admission"],
    ),
}

# Стартовое меню (показывается при первом сообщении / команде /start)
STARTER_INTENTS = ["show_schedule", "admission", "contacts"]