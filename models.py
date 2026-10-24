from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Task(BaseModel):
    title: str
    tool: str
    details: str
    source: str = "plan"


class Section(BaseModel):
    heading: str
    text: str | None = None
    table: list[list[str]] | None = None


class Review(BaseModel):
    approved: bool
    gaps: list[str] = Field(default_factory=list)
    fix_tasks: list[Task] = Field(default_factory=list)


class AgentState(BaseModel):
    request: str
    title: str | None = None
    doc_type: str | None = None
    tasks: list[Task] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    sections: list[Section] = Field(default_factory=list)
    revision_count: int = 0
    document_id: str | None = None
    review: Review | None = None


class AgentRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    request: str = Field(min_length=10, max_length=2000)


class AgentResponse(BaseModel):
    title: str
    doc_type: str
    tasks: list[Task]
    assumptions: list[str]
    review: Review | None
    revision_count: int
    summary: str
    document_id: str
    download_url: str
