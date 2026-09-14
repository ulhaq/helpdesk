from typing import Annotated

from pydantic import BaseModel, Field


class AssistantStatusOut(BaseModel):
    enabled: bool


class AiSourceOut(BaseModel):
    title: str
    slug: str
    # The passage of the article the text relies on.
    cited_text: str


class ReplySuggestionOut(BaseModel):
    text: str
    sources: list[AiSourceOut]


class WidgetQuestionIn(BaseModel):
    question: Annotated[str, Field(min_length=1, max_length=1000)]


class WidgetAnswerOut(BaseModel):
    # False when the help center couldn't ground an answer (or the assistant is
    # unavailable) - the widget then offers article results and a human.
    answered: bool
    text: str | None
    sources: list[AiSourceOut]
