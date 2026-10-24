import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from llm import ask_json
from models import AgentState, Section, Task

ToolFunc = Callable[[Task, AgentState], Awaitable[None]]


@dataclass
class Tool:
    name: str
    description: str
    func: ToolFunc


TOOLS: dict[str, Tool] = {}

logger = logging.getLogger(__name__)


def tool(name: str, description: str):
    def register(func: ToolFunc) -> ToolFunc:
        TOOLS[name] = Tool(name, description, func)
        return func

    return register


def describe_tools() -> str:
    return "\n".join(f"- {t.name}: {t.description}" for t in TOOLS.values())


def ensure_known_tools(tasks: list[Task]) -> None:
    for task in tasks:
        if task.tool not in TOOLS:
            logger.warning(
                "Unknown tool %r in task %r, using write_section", task.tool, task.title
            )
            task.tool = "write_section"


MOCK_DATA = {
    "company": "Acme Corp",
    "team": [
        {"name": "Arun", "role": "Backend Engineer"},
        {"name": "Divya", "role": "Frontend Engineer"},
        {"name": "Karthik", "role": "Mobile Engineer"},
        {"name": "Meena", "role": "QA Engineer"},
    ],
    "budget": "INR 2,00,000",
    "start_date": "3 November 2026",
}


class SectionText(BaseModel):
    text: str


class TableRows(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)
    rows: list[list[str]]


def section_prompt(task: Task, state: AgentState) -> str:
    return (
        f"Request: {state.request}\n"
        f"Section: {task.title}\n"
        f"Instructions: {task.details}\n"
        f"Company data: {json.dumps(state.context)}"
    )


@tool("lookup_data", "Fetch company data such as team members, budget and start date")
async def lookup_data(task: Task, state: AgentState) -> None:
    details = task.details.lower()
    found = {key: value for key, value in MOCK_DATA.items() if key in details}
    state.context.update(found or MOCK_DATA)


@tool("write_section", "Write a prose section of the document")
async def write_section(task: Task, state: AgentState) -> None:
    result = await ask_json(
        system=(
            f"You write one section of a {state.doc_type}. "
            "Use the company data where relevant. If it conflicts with the request, follow the request. "
            "Write plain paragraphs separated by blank lines, with no markdown."
            'Return JSON: {"text": "..."}'
        ),
        user=section_prompt(task, state),
        schema=SectionText,
    )
    state.sections.append(Section(heading=task.title, text=result.text))


@tool(
    "make_table",
    "Create a table for structured data such as timelines, action items or budgets",
)
async def make_table(task: Task, state: AgentState) -> None:
    result = await ask_json(
        system=(
            f"You create one table for a {state.doc_type}. "
            "Use the company data where relevant. If it conflicts with the request, follow the request. "
            'Return JSON: {"rows": [["Header 1", "Header 2"], ["cell", "cell"]]}. The first row is the header.'
        ),
        user=section_prompt(task, state),
        schema=TableRows,
    )
    state.sections.append(Section(heading=task.title, table=result.rows))
