import logging
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path
from fastapi.responses import FileResponse

from agent import run_agent
from docx_builder import OUTPUT_DIR
from llm import LLMError
from models import AgentRequest, AgentResponse

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

app = FastAPI(title="Document Agent")

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/agent", response_model=AgentResponse)
async def agent(body: AgentRequest) -> AgentResponse:
    try:
        state = await run_agent(body.request)
    except LLMError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    summary = (
        f"Created '{state.title}' with {len(state.sections)} sections "
        f"from {len(state.tasks)} tasks. Flagged {len(state.assumptions)} assumptions. "
        f"Review {'approved' if state.review and state.review.approved else 'not fully approved'}"
        f"after {state.revision_count} revision(s)."
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
