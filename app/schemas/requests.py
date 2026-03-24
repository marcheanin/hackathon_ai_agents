from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    user_request: str = Field(
        ...,
        description="Описание агента или системы, архитектуру которой нужно спроектировать",
        min_length=10,
        max_length=4000,
        examples=["Нужен агент для автоматической обработки email и создания тикетов в Jira"],
    )
    context: dict | None = Field(
        None,
        description="Дополнительный контекст (технологические ограничения, размер команды и т.д.)",
    )
