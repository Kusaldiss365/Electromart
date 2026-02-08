from pydantic import BaseModel

class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    input_type: str = "text"


class ChatResponse(BaseModel):
    route: str
    response: str
