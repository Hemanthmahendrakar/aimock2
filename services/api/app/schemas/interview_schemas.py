from pydantic import BaseModel, Field


class ExchangeAccessTokenRequest(BaseModel):
    token: str = Field(min_length=10)


class SubmitAnswerRequest(BaseModel):
    question_id: str
    transcript_text: str = Field(min_length=1, max_length=20000)
