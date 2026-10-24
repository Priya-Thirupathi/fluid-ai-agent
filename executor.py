import logging

from models import AgentState, Task
from tools import TOOLS

logger = logging.getLogger(__name__)


async def execute(state: AgentState, tasks: list[Task]) -> AgentState:
    for task in tasks:
        logger.info("Running %s: %s", task.tool, task.title)
        await TOOLS[task.tool].func(task, state)
    return state
