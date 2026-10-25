# Document Agent

An autonomous AI agent that turns a plain-English request into a finished Word document.
It plans its own tasks, chooses a tool for each one, writes the document, reviews its own
draft against the request, fixes what it finds, and returns a `.docx`.

## How it works

```
POST /agent {"request": "..."}
    │  validated: 10 to 2000 characters, otherwise 422
    ▼
PLAN      LLM picks the document type and title, lists assumptions and risks,
          and breaks the work into 4 to 7 tasks, each with a tool
    ▼
EXECUTE   runs the tasks in order through the tool registry
    ▼
REFLECT   reviewer checks the draft against the request and rewrites
          broken sections (at most 1 revision round)
    ▼
BUILD     python-docx renders headings, bullets and tables into a .docx
    ▼
Response  plan, assumptions, review result, summary, download link
```

A single `AgentState` object flows through every step. Each step is a function that takes
the state and returns it updated, so the pipeline is easy to follow, test and extend.

### Tools

Tools are registered with a decorator. The planner receives the list of registered tools
and their descriptions automatically, so adding a tool means writing one function.

| Tool | What it does |
|---|---|
| `lookup_data` | Fetches company data (team, budget, start date). Mock data in this version |
| `write_section` | Writes a prose section with the LLM |
| `make_table` | Builds a table (timelines, action items, budgets) with the LLM |

Tools share data through the state: `lookup_data` fills `context`, and the writing tools
read it, so later sections can use names and figures fetched earlier.

## Engineering improvement: reflection

After the first draft, a reviewer step checks that:

- every explicit requirement in the request is covered
- unrealistic or conflicting requirements are called out as risks, not assumed away
- sections do not contradict each other or the assumptions

If it finds problems, it returns fix tasks. A fix task that uses an existing section heading
rewrites that section in place; a new heading adds a missing section. The loop is capped at
one revision round (`MAX_REVISIONS` in `agent.py`) to keep cost and latency bounded.

**Why reflection:** first drafts from an LLM often miss a requirement or contradict
themselves, especially when the request is vague or conflicting. A review step catches
this before the user sees the document.

## Project structure

| File | Responsibility |
|---|---|
| `main.py` | HTTP layer: endpoints, status codes, response shape |
| `agent.py` | Orchestrator: plan, execute, reflect, build |
| `planner.py` | Turns the request into a plan |
| `executor.py` | Runs tasks in order through the tool registry |
| `tools.py` | Tool registry and the three tools |
| `reviewer.py` | Reflection step |
| `docx_builder.py` | Renders the Word document |
| `llm.py` | The only module that calls the LLM: JSON mode, validation, fallback |
| `models.py` | Pydantic models for state, API request and response |

## Setup

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/). Get a free API key from
[Groq](https://console.groq.com).

```bash
uv sync
cp .env.example .env    # then add your key
uv run uvicorn main:app --reload
```

`.env`:

```
GROQ_API_KEY=your_key_here
GROQ_MODEL=openai/gpt-oss-120b
GROQ_FALLBACK_MODEL=openai/gpt-oss-20b
```

Open http://localhost:8000/docs for interactive API docs.

### Docker

```bash
docker build -t fluid-agent .
docker run --env-file .env -p 8000:8000 fluid-agent
```

The API key is passed in at runtime and is never copied into the image.

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/agent` | Run the agent. Body: `{"request": "..."}` |
| `GET` | `/documents/{document_id}` | Download the generated `.docx` |
| `GET` | `/health` | Health check |

```bash
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"request": "Write meeting minutes for a sprint planning meeting with 4 engineers. We discussed the new login feature, a payment bug in checkout, and agreed to release on Friday."}'
```

The response includes the task list (each task marked `plan` or `review`), assumptions,
the review result, a summary, and a `download_url`. A request takes roughly 30 to 140
seconds, depending on the number of tasks and whether a revision round runs.

| Status | When |
|---|---|
| `200` | Document created |
| `422` | Request too short or too long, or an invalid document ID |
| `404` | Document not found |
| `503` | The LLM failed on both models |

## Test requests

**Standard:**
> Write meeting minutes for a sprint planning meeting with 4 engineers. We discussed the
> new login feature, a payment bug in checkout, and agreed to release on Friday.

**Complex** (conflicting and missing information):
> Create a project plan to launch our new mobile app in 2 weeks. We only have one developer.
> It must include full QA testing, a marketing campaign, and support for both iOS and Android.

The complex request conflicts with the mock company data, which lists four engineers. The
agent is expected to follow the request, flag the timeline as a risk, and state how it
handles it.

The agent was also checked on unseen document types (an onboarding SOP, a technical design
document, and a cloud migration proposal) without changing any prompts, to make sure it
was not tuned only to the two test requests.

## Reliability

- **Validated LLM output:** every LLM answer is parsed into a Pydantic model. Wrong or
  missing fields count as a failure rather than reaching the document.
- **Fallback:** if the primary model errors or returns invalid JSON, the call is retried on
  the fallback model. If both fail, the API returns 503.
- **Rate limits:** the Groq SDK retries `429` responses automatically, and the fallback
  model has its own separate limit.
- **Unknown tools:** if the planner names a tool that does not exist, the task falls back
  to `write_section` and a warning is logged.
- **Formatting:** prompts ask for plain text, and the document builder also strips
  markdown and turns `- ` lines into real Word bullets, since prompts alone are not reliable.

## Design decisions

- **Fixed pipeline instead of a free-form agent loop.** The LLM decides the content, the
  tasks and the tools, while the overall shape (plan, execute, reflect) is fixed. This keeps
  the number of LLM calls bounded and the behaviour easy to debug. The trade-off is that the
  agent cannot re-plan halfway through.
# Document Agent

An autonomous AI agent that turns a plain-English request into a finished Word document.
It plans its own tasks, chooses a tool for each one, writes the document, reviews its own
draft against the request, fixes what it finds, and returns a `.docx`.

## How it works

```
POST /agent {"request": "..."}
    │  validated: 10 to 2000 characters, otherwise 422
    ▼
PLAN      LLM picks the document type and title, lists assumptions and risks,
          and breaks the work into 4 to 7 tasks, each with a tool
    ▼
EXECUTE   runs the tasks in order through the tool registry
    ▼
REFLECT   reviewer checks the draft against the request and rewrites
          broken sections (at most 1 revision round)
    ▼
BUILD     python-docx renders headings, bullets and tables into a .docx
    ▼
Response  plan, assumptions, review result, summary, download link
```

A single `AgentState` object flows through every step. Each step is a function that takes
the state and returns it updated, so the pipeline is easy to follow, test and extend.

### Tools

Tools are registered with a decorator. The planner receives the list of registered tools
and their descriptions automatically, so adding a tool means writing one function.

| Tool | What it does |
|---|---|
| `lookup_data` | Fetches company data (team, budget, start date). Mock data in this version |
| `write_section` | Writes a prose section with the LLM |
| `make_table` | Builds a table (timelines, action items, budgets) with the LLM |

Tools share data through the state: `lookup_data` fills `context`, and the writing tools
read it, so later sections can use names and figures fetched earlier.

## Engineering improvement: reflection

After the first draft, a reviewer step checks that:

- every explicit requirement in the request is covered
- unrealistic or conflicting requirements are called out as risks, not assumed away
- sections do not contradict each other or the assumptions

If it finds problems, it returns fix tasks. A fix task that uses an existing section heading
rewrites that section in place; a new heading adds a missing section. The loop is capped at
one revision round (`MAX_REVISIONS` in `agent.py`) to keep cost and latency bounded.

**Why reflection:** first drafts from an LLM often miss a requirement or contradict
themselves, especially when the request is vague or conflicting. A review step catches
this before the user sees the document.

## Project structure

| File | Responsibility |
|---|---|
| `main.py` | HTTP layer: endpoints, status codes, response shape |
| `agent.py` | Orchestrator: plan, execute, reflect, build |
| `planner.py` | Turns the request into a plan |
| `executor.py` | Runs tasks in order through the tool registry |
| `tools.py` | Tool registry and the three tools |
| `reviewer.py` | Reflection step |
| `docx_builder.py` | Renders the Word document |
| `llm.py` | The only module that calls the LLM: JSON mode, validation, fallback |
| `models.py` | Pydantic models for state, API request and response |

## Setup

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/). Get a free API key from
[Groq](https://console.groq.com).

```bash
uv sync
cp .env.example .env    # then add your key
uv run uvicorn main:app --reload
```

`.env`:

```
GROQ_API_KEY=your_key_here
GROQ_MODEL=openai/gpt-oss-120b
GROQ_FALLBACK_MODEL=openai/gpt-oss-20b
```

Open http://localhost:8000/docs for interactive API docs.

### Docker

```bash
docker build -t fluid-agent .
docker run --env-file .env -p 8000:8000 fluid-agent
```

The API key is passed in at runtime and is never copied into the image.

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/agent` | Run the agent. Body: `{"request": "..."}` |
| `GET` | `/documents/{document_id}` | Download the generated `.docx` |
| `GET` | `/health` | Health check |

```bash
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"request": "Write meeting minutes for a sprint planning meeting with 4 engineers. We discussed the new login feature, a payment bug in checkout, and agreed to release on Friday."}'
```

The response includes the task list (each task marked `plan` or `review`), assumptions,
the review result, a summary, and a `download_url`. A request takes roughly 30 to 140
seconds, depending on the number of tasks and whether a revision round runs.

| Status | When |
|---|---|
| `200` | Document created |
| `422` | Request too short or too long, or an invalid document ID |
| `404` | Document not found |
| `503` | The LLM failed on both models |

## Test requests

**Standard:**
> Write meeting minutes for a sprint planning meeting with 4 engineers. We discussed the
> new login feature, a payment bug in checkout, and agreed to release on Friday.

**Complex** (conflicting and missing information):
> Create a project plan to launch our new mobile app in 2 weeks. We only have one developer.
> It must include full QA testing, a marketing campaign, and support for both iOS and Android.

The complex request conflicts with the mock company data, which lists four engineers. The
agent is expected to follow the request, flag the timeline as a risk, and state how it
handles it.

The agent was also checked on unseen document types (an onboarding SOP, a technical design
document, and a cloud migration proposal) without changing any prompts, to make sure it
was not tuned only to the two test requests.

## Reliability

- **Validated LLM output:** every LLM answer is parsed into a Pydantic model. Wrong or
  missing fields count as a failure rather than reaching the document.
- **Fallback:** if the primary model errors or returns invalid JSON, the call is retried on
  the fallback model. If both fail, the API returns 503.
- **Rate limits:** the Groq SDK retries `429` responses automatically, and the fallback
  model has its own separate limit.
- **Unknown tools:** if the planner names a tool that does not exist, the task falls back
  to `write_section` and a warning is logged.
- **Formatting:** prompts ask for plain text, and the document builder also strips
  markdown and turns `- ` lines into real Word bullets, since prompts alone are not reliable.

## Design decisions

- **Fixed pipeline instead of a free-form agent loop.** The LLM decides the content, the
  tasks and the tools, while the overall shape (plan, execute, reflect) is fixed. This keeps
  the number of LLM calls bounded and the behaviour easy to debug. The trade-off is that the
  agent cannot re-plan halfway through.
- **Plain Python instead of LangGraph.** The pipeline is linear, so a graph runtime adds
  little. The step functions map directly onto LangGraph if branching is needed: each
  function becomes a node, and the revision check becomes a conditional edge.
- **Sequential execution.** Later tasks depend on earlier results (for example, team data
  fetched by `lookup_data`), so tasks run in order rather than in parallel.
- **Layout in code, content from the LLM.** The document layout is plain Python, which makes
  it predictable, fast and free.

## Known limitations

- Each section is written separately, so numbers and dates can drift between sections. The
  reviewer catches some of this, but not all.
- When the reviewer rewrites a section, it may change the tool, for example turning a table
  into prose.
- The request waits while the agent runs (30 to 140 seconds).
- Company data is mocked.
- Generated documents are kept on local disk and never cleaned up.

## Next steps

- A background job queue: `POST /agent` returns a job ID and the client polls for status,
  so long requests do not hold an HTTP connection open.
- A shared facts sheet (dates, budget, people) that every writer must use, to stop
  numbers drifting between sections.
- RAG over real company documents in place of mock data.
- An evaluation set of requests, used to score every prompt change.
- Automated tests with a fake LLM client.

