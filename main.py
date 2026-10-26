import asyncio
import logging
import os
from contextvars import ContextVar
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Path, Request
from fastapi.responses import FileResponse

from agent import run_agent
from docx_builder import OUTPUT_DIR
from llm import LLMError
from models import AgentRequest, AgentResponse

request_id: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id.get()
        return True


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s",
)
for handler in logging.getLogger().handlers:
    handler.addFilter(RequestIdFilter())

app = FastAPI(title="Document Agent")

AGENT_TIMEOUT_SECONDS = float(os.getenv("AGENT_TIMEOUT_SECONDS", "180"))
DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    current = uuid4().hex[:8]
    token = request_id.set(current)
    try:
        response = await call_next(request)
    finally:
        request_id.reset(token)
    response.headers["X-Request-ID"] = current
    return response


def plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/agent", response_model=AgentResponse)
async def agent(body: AgentRequest) -> AgentResponse:
    try:
        async with asyncio.timeout(AGENT_TIMEOUT_SECONDS):
            state = await run_agent(body.request)
    except LLMError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except TimeoutError as error:
        raise HTTPException(
            status_code=504,
            detail=f"Agent did not finish within {AGENT_TIMEOUT_SECONDS:g} seconds",
        ) from error

    summary = (
        f"Created '{state.title}' with {plural(len(state.sections), 'section')} "
        f"from {plural(len(state.tasks), 'task')}. "
        f"Flagged {plural(len(state.assumptions), 'assumption')}. "
        f"Review {'approved' if state.review and state.review.approved else 'not fully approved'} "
        f"after {plural(state.revision_count, 'revision')}."
    )
    return AgentResponse(
        title=state.title,
        doc_type=state.doc_type,
        tasks=state.tasks,
        assumptions=state.assumptions,
        review=state.review,
        revision_count=state.revision_count,
        summary=summary,
        document_id=state.document_id,
        download_url=f"/documents/{state.document_id}",
    )


@app.get("/documents/{document_id}")
async def download(document_id: Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]):
    path = OUTPUT_DIR / f"{document_id}.docx"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Document not found")
    return FileResponse(
        path, media_type=DOCX_MEDIA_TYPE, filename=f"{document_id}.docx"
    )
