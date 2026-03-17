from pydantic import BaseModel


class EmailDraftGenerateRequest(BaseModel):
    student_id: str
    professor_id: str


class EmailDraftResponse(BaseModel):
    subject: str
    body: str
