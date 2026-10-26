import json
from collections.abc import Awaitable, Callable
from types import SimpleNamespace

# A responder gets (step, model, user prompt) and returns the model's reply:
# a dict (sent as JSON) or a raw string (to simulate broken output).
Responder = Callable[[str, str, str], Awaitable[dict | str]]

PLAN = {
    "title": "Sprint Planning Minutes",
    "doc_type": "Meeting Minutes",
    "assumptions": ["The meeting was held today"],
    "tasks": [
        {"title": "Attendees", "tool": "lookup_data", "details": "team"},
        {"title": "Decisions", "tool": "write_section", "details": "What was agreed"},
        {"title": "Action Items", "tool": "make_table", "details": "Owners and dates"},
    ],
}
SECTION = {"text": "Arun will fix the payment bug by Thursday."}
TABLE = {"rows": [["Action", "Owner", "Days"], ["Fix payment bug", "Arun", 2]]}
APPROVED = {"approved": True, "gaps": [], "fix_tasks": []}


def step_of(system: str) -> str:
    if system.startswith("You are the planner"):
        return "plan"
    if system.startswith("You are a strict reviewer"):
        return "review"
    if system.startswith("You create one table"):
        return "table"
    return "section"


async def happy_path(step: str, model: str, user: str) -> dict | str:
    return {"plan": PLAN, "section": SECTION, "table": TABLE, "review": APPROVED}[step]


class FakeGroq:
    """Stands in for AsyncGroq and records every call it receives."""

    def __init__(self, responder: Responder) -> None:
        self.responder = responder
        self.calls: list[tuple[str, str]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, model, messages, response_format):
        system, user = messages[0]["content"], messages[1]["content"]
        step = step_of(system)
        self.calls.append((step, model))
        reply = await self.responder(step, model, user)
        content = reply if isinstance(reply, str) else json.dumps(reply)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )
