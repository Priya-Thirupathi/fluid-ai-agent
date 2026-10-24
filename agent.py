from docx_builder import build_docx
from executor import execute
from models import AgentState
from planner import plan
from reviewer import reflect

MAX_REVISIONS = 1


def needs_revision(state: AgentState) -> bool:
    return (
        state.review is not None
        and not state.review.approved
        and bool(state.review.fix_tasks)
        and state.revision_count < MAX_REVISIONS
    )


async def run_agent(request: str) -> AgentState:
    state = AgentState(request=request)
    state = await plan(state)
    state = await execute(state, state.tasks)
    state = await reflect(state)

    while needs_revision(state):
        fix_tasks = state.review.fix_tasks
        state.tasks.extend(fix_tasks)
        state = await execute(state, fix_tasks)
        state.revision_count += 1
        state = await reflect(state)

    return build_docx(state)
