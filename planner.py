import logging

from pydantic import BaseModel, Field

from llm import ask_json
from models import AgentState, Task
from tools import describe_tools, ensure_known_tools

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the planner of an autonomous agent that produces business documents.
Read the user's request and plan the document.

1. Decide the document type and a clear title.
2. Look for missing information and conflicting or unrealistic requirements. For each one, state the assumption you will make or the risk you see. Never pretend a conflicting requirement is fine.
3. Break the work into 4 to 7 tasks, in document order. Each task produces one part of the document. Start with a lookup_data task if company data(team, budget, dates) would help.

Available tools:
{tools}

Return JSON:
  {{"title": "...", "doc_type": "...", "assumptions": ["..."],
    "tasks": [{{"title": "...", "tool": "<tool name>", "details": "what this part must contain"}}]}}"""


class Plan(BaseModel):
    title: str
    doc_type: str
    assumptions: list[str] = Field(default_factory=list)
    tasks: list[Task] = Field(min_length=1)


async def plan(state: AgentState) -> AgentState:
    result = await ask_json(
        system=SYSTEM_PROMPT.format(tools=describe_tools()),
        user=state.request,
        schema=Plan,
    )
    ensure_known_tools(result.tasks)
    logger.info("Planned %d tasks for %r", len(result.tasks), result.title)
    state.title = result.title
    state.doc_type = result.doc_type
    state.assumptions = result.assumptions
    state.tasks = result.tasks
    return state
