import logging

from llm import ask_json
from models import AgentState, Review
from tools import describe_tools, ensure_known_tools

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a strict reviewer of business documents.
Compare the draft with the user's request.

Check that every explicit requirement in the request is covered by a section,
and that conflicting or unrealistic requirements are addressed in the assumptions or a
section.

If everything is covered, return approved true with no gaps and no fix tasks.
Otherwise, list each gap, and add one fix task per gap that writes the missing part.

Available tools:
{tools}

Return JSON:
{{"approved": true, "gaps": ["..."],
  "fix_tasks": [{{"title": "...", "tool": "<tool name>", "details": "what this part must
contain"}}]}}"""


def render_draft(state: AgentState) -> str:
    lines = [f"Request: {state.request}", "", "Assumptions:"]
    lines += [f"- {assumption}" for assumption in state.assumptions]
    for section in state.sections:
        lines += ["", f"## {section.heading}"]
        if section.text:
            lines.append(section.text)
        if section.table:
            lines += [" | ".join(row) for row in section.table]
    return "\n".join(lines)


async def reflect(state: AgentState) -> AgentState:
    review = await ask_json(
        system=SYSTEM_PROMPT.format(tools=describe_tools()),
        user=render_draft(state),
        schema=Review,
    )
    ensure_known_tools(review.fix_tasks)
    for task in review.fix_tasks:
        task.source = "review"
    logger.info("Review approved=%s, gaps=%s", review.approved, review.gaps)

    state.review = review
    return state
