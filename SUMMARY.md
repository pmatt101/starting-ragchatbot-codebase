# Course Materials RAG Chatbot — Codebase Summary

---

## Codebase Overview

A full-stack **Retrieval-Augmented Generation (RAG)** system for answering questions about course materials.

### Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI (Python) |
| AI model | Claude Sonnet (via Anthropic API) |
| Vector database | ChromaDB (persistent, local) |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers) |
| Package manager | uv |
| Frontend | Vanilla HTML/CSS/JS |

---

### Architecture

```
User Query
    ↓
Frontend (index.html + script.js)
    ↓  POST /api/query
FastAPI (app.py)
    ↓
RAGSystem (rag_system.py)  ← orchestrates everything
    ├── SessionManager     ← tracks conversation history per session
    ├── AIGenerator        ← calls Claude API with tool use
    │       ↓ tool_use
    │   ToolManager → CourseSearchTool
    │                       ↓
    └── VectorStore (ChromaDB)
            ├── course_catalog  (course titles/metadata)
            └── course_content  (chunked lesson text)
```

---

### Key Files

| File | Role |
|---|---|
| `backend/app.py` | FastAPI app — 2 endpoints: `POST /api/query`, `GET /api/courses` |
| `backend/rag_system.py` | Main orchestrator — ties all components together |
| `backend/ai_generator.py` | Claude API client — handles tool-use agentic loop |
| `backend/vector_store.py` | ChromaDB wrapper — semantic search, add/get courses |
| `backend/search_tools.py` | `CourseSearchTool` + `ToolManager` — Anthropic tool-calling interface |
| `backend/document_processor.py` | Parses `.txt`/`.pdf`/`.docx` course files, chunks text |
| `backend/session_manager.py` | In-memory conversation history (rolling window of 2 exchanges) |
| `backend/models.py` | Pydantic models: `Course`, `Lesson`, `CourseChunk` |
| `backend/config.py` | Central config dataclass (model name, chunk size, paths, etc.) |
| `docs/` | 4 course script `.txt` files (the knowledge base content) |
| `frontend/` | Static HTML/CSS/JS served directly by FastAPI |

---

### Data Flow

1. **Ingestion** (at startup): `.txt` files in `docs/` are parsed by `DocumentProcessor` — header lines extract course title/link/instructor, then content is split into ~800-char overlapping chunks → stored in ChromaDB.

2. **Query**: User sends a question → Claude decides whether to call `search_course_content` tool → tool does semantic search in ChromaDB (optionally filtered by course name or lesson number) → results fed back to Claude → final answer returned with source labels.

3. **Session**: Each browser session gets a `session_id`; the last 2 Q&A exchanges are prepended as context to subsequent queries.

---

### Document Format (expected by parser)

```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 1: <lesson title>
Lesson Link: <url>
<lesson content...>

Lesson 2: ...
```

---

## Document Processing Pipeline

### 1. File Reading (`document_processor.py: read_file`)
Reads `.txt`/`.pdf`/`.docx` files as UTF-8 text (falls back to ignoring bad chars on decode errors).

---

### 2. Metadata Extraction (`document_processor.py: process_course_document`)
Parses the first 3–4 lines for structured headers:
```
Line 1 → "Course Title: ..."      → course.title
Line 2 → "Course Link: ..."       → course.course_link
Line 3 → "Course Instructor: ..." → course.instructor
```
If a line doesn't match the expected pattern, the raw line content is used as a fallback.

---

### 3. Lesson Segmentation
After the header, the file is scanned line-by-line for lesson markers:
```
Lesson 1: Introduction
Lesson Link: https://...
<content lines...>

Lesson 2: ...
```
Each lesson boundary triggers a flush of the previous lesson's accumulated content into chunks.

---

### 4. Text Chunking (`document_processor.py: chunk_text`)
Each lesson's text is split into overlapping chunks:
- **Whitespace normalization** first (`\s+` → single space)
- **Sentence-aware splitting** using a regex that splits on `.`, `!`, `?` followed by a capital letter (handles common abbreviations)
- Sentences are greedily packed into chunks up to **800 chars** (`CHUNK_SIZE`)
- **100-char overlap** (`CHUNK_OVERLAP`) — the last N sentences of a chunk are repeated at the start of the next one to preserve context across boundaries

---

### 5. `CourseChunk` Creation
Each chunk becomes a `CourseChunk` object with context prepended:
```python
# First chunk of a lesson:
"Lesson 1 content: <text>"

# Last lesson uses a fuller prefix:
"Course <title> Lesson 2 content: <text>"
```
Chunks carry metadata: `course_title`, `lesson_number`, `chunk_index`.

---

### 6. Storage in ChromaDB
Back in `rag_system.py`, the output of processing is split into two collections:
- `course_catalog` — one entry per course (title, instructor, link, lessons list as JSON)
- `course_content` — one entry per chunk (embedded via `all-MiniLM-L6-v2` for semantic search)

---

## Query Lifecycle: Frontend → Backend

### 1. User Input (`script.js`)

User types a message and presses Enter or clicks Send:

```js
// script.js:45-96 — sendMessage()
chatInput.disabled = true;
addMessage(query, 'user');          // renders user bubble immediately
// shows animated loading dots in the chat
```

---

### 2. HTTP Request (`script.js:63-72`)

```js
fetch('/api/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        query: query,               // the user's text
        session_id: currentSessionId  // null on first message
    })
})
```

---

### 3. FastAPI Receives Request (`app.py:56-74`)

```python
@app.post("/api/query")
async def query_documents(request: QueryRequest):
    session_id = request.session_id or rag_system.session_manager.create_session()
    answer, sources = rag_system.query(request.query, session_id)
    return QueryResponse(answer=answer, sources=sources, session_id=session_id)
```

If no `session_id` was sent, a new one (`session_1`, `session_2`, …) is created.

---

### 4. RAG Orchestration (`rag_system.py:102-140`)

```python
def query(self, query, session_id):
    prompt = f"Answer this question about course materials: {query}"
    history = self.session_manager.get_conversation_history(session_id)  # last 2 exchanges

    response = self.ai_generator.generate_response(
        query=prompt,
        conversation_history=history,
        tools=self.tool_manager.get_tool_definitions(),
        tool_manager=self.tool_manager
    )

    sources = self.tool_manager.get_last_sources()
    self.tool_manager.reset_sources()
    self.session_manager.add_exchange(session_id, query, response)
    return response, sources
```

---

### 5. First Claude API Call (`ai_generator.py:80`)

Claude is sent:
- **System prompt** — instructions + conversation history (if any)
- **User message** — the query
- **Tool definition** — `search_course_content` (query, optional course_name, optional lesson_number)
- **tool_choice: auto** — Claude decides whether to search or answer directly

**Two possible paths:**

#### Path A — General knowledge question
Claude responds directly (`stop_reason = "end_turn"`). `response.content[0].text` is returned immediately.

#### Path B — Course-specific question (tool use)
Claude responds with `stop_reason = "tool_use"` and specifies arguments like:
```json
{ "query": "...", "course_name": "...", "lesson_number": 2 }
```

---

### 6. Tool Execution (`ai_generator.py:89-134` + `search_tools.py`)

```python
# For each tool_use block in the response:
tool_result = tool_manager.execute_tool("search_course_content", **content_block.input)
```

Inside `CourseSearchTool.execute()` (`search_tools.py:52`):
1. Calls `vector_store.search(query, course_name, lesson_number)`
2. **Course name resolution** — if a `course_name` was given, does a semantic search against `course_catalog` to find the closest real title
3. **Builds a ChromaDB filter** — `{"course_title": "..."}` and/or `{"lesson_number": N}`
4. **Queries `course_content`** — top-5 most semantically similar chunks returned
5. Formats results as `[CourseName - Lesson N]\n<chunk text>` blocks
6. Stores source labels in `self.last_sources` for the UI

---

### 7. Second Claude API Call (`ai_generator.py:127-135`)

The conversation is extended with the tool result and sent back to Claude **without tools** this time:
```
messages = [
  { role: "user",      content: original query },
  { role: "assistant", content: [tool_use block] },
  { role: "user",      content: [tool_result block] }
]
```
Claude synthesizes the retrieved chunks into a final answer.

---

### 8. Response Back to Frontend (`script.js:76-85`)

```json
{
  "answer": "...",
  "sources": ["Course Name - Lesson 2", "..."],
  "session_id": "session_1"
}
```

- `currentSessionId` is stored for subsequent messages
- Loading dots removed, answer rendered as **Markdown** (via `marked.parse()`)
- Sources shown in a collapsible `<details>` element below the answer

---

### Summary Flow Diagram

```
User types query
      │
      ▼
script.js sendMessage()
      │  POST /api/query  {query, session_id}
      ▼
app.py /api/query
      │
      ▼
rag_system.query()
      │  prepends conversation history
      ▼
ai_generator → Claude API call #1
      │
      ├─ [general question] → return text directly
      │
      └─ [tool_use] → CourseSearchTool.execute()
                             │
                             ▼
                       VectorStore.search()
                       ChromaDB semantic lookup
                             │
                             ▼
                   Claude API call #2 (with results)
                             │
                             ▼
                       final answer text
      │
      ▼
JSON response → script.js renders markdown + sources
```

---

## Detailed System Visualization

### Component Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          BROWSER (frontend/)                                │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  index.html                                                          │  │
│  │  ┌─────────────────────────┐   ┌──────────────────────────────────┐ │  │
│  │  │    Sidebar              │   │    Chat Panel                    │ │  │
│  │  │  - Course count         │   │  - Message bubbles (user/AI)     │ │  │
│  │  │  - Course title list    │   │  - Loading spinner (3 dots)      │ │  │
│  │  │  - Suggested questions  │   │  - Markdown rendered responses   │ │  │
│  │  └─────────────────────────┘   │  - Collapsible sources panel     │ │  │
│  │                                └──────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  script.js — State: { currentSessionId }                                   │
│  ┌────────────────────┐   ┌─────────────────────────────────────────────┐  │
│  │ On DOMContentLoad  │   │ sendMessage()                               │  │
│  │  createNewSession()│   │  1. read chatInput.value                   │  │
│  │  loadCourseStats() │   │  2. disable input + show loading bubble    │  │
│  │    GET /api/courses│   │  3. POST /api/query {query, session_id}    │  │
│  └────────────────────┘   │  4. await response                         │  │
│                           │  5. store session_id if first message      │  │
│                           │  6. remove loading, render answer+sources  │  │
│                           └─────────────────────────────────────────────┘  │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │  HTTP (JSON over localhost:8000)
                          │
          ┌───────────────┴──────────────────────────────────────────┐
          │  POST /api/query                   GET /api/courses       │
          │  Body: { query, session_id? }      Response: { total,    │
          │  Response: { answer, sources,                titles[] }  │
          │             session_id }                                  │
          └───────────────┬──────────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────────────────┐
│                        FASTAPI  (backend/app.py)                            │
│                                                                             │
│  Middleware: CORSMiddleware, TrustedHostMiddleware                          │
│  Static mount: GET /* → ../frontend/  (serves HTML/CSS/JS)                 │
│                                                                             │
│  @startup → rag_system.add_course_folder("../docs")                        │
│               skips already-indexed courses                                 │
│                                                                             │
│  POST /api/query                        GET /api/courses                    │
│  ┌─────────────────────────┐            ┌──────────────────────────┐       │
│  │ 1. get or create        │            │ rag_system               │       │
│  │    session_id           │            │  .get_course_analytics() │       │
│  │ 2. rag_system.query()   │            │ → { total, titles[] }    │       │
│  │ 3. return answer+sources│            └──────────────────────────┘       │
│  └────────────┬────────────┘                                               │
└───────────────┼─────────────────────────────────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────────────────────────────┐
│                      RAGSystem  (backend/rag_system.py)                     │
│                                                                             │
│  query(query, session_id)                                                   │
│  │                                                                          │
│  ├─ SessionManager.get_conversation_history(session_id)                     │
│  │    returns last N exchanges as formatted string, or None                 │
│  │                                                                          │
│  ├─ AIGenerator.generate_response(prompt, history, tools, tool_manager)     │
│  │    (see Claude API section below)                                        │
│  │                                                                          │
│  ├─ ToolManager.get_last_sources()   → sources list for UI                  │
│  ├─ ToolManager.reset_sources()                                             │
│  └─ SessionManager.add_exchange(session_id, query, response)                │
│         stores user + assistant messages, trims to MAX_HISTORY=2 exchanges  │
└───────────────┬─────────────────────────────────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────────────────────────────┐
│                    AIGenerator  (backend/ai_generator.py)                   │
│                                                                             │
│  generate_response()                                                        │
│  │                                                                          │
│  ├─ Build system prompt:                                                    │
│  │    SYSTEM_PROMPT + "\n\nPrevious conversation:\n" + history (if any)     │
│  │                                                                          │
│  ├─ API Call #1 ──────────────────────────────────────────────────────────┐ │
│  │   model:       claude-sonnet-4-20250514                                │ │
│  │   temperature: 0                                                       │ │
│  │   max_tokens:  800                                                     │ │
│  │   system:      prompt above                                            │ │
│  │   messages:    [{ role: user, content: query }]                       │ │
│  │   tools:       [search_course_content definition]                     │ │
│  │   tool_choice: auto                                                    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│  │                                                                          │
│  ├─── stop_reason = "end_turn" ──────────────────────────────────────────▶ │
│  │    (general knowledge question)          return response.content[0].text │
│  │                                                                          │
│  └─── stop_reason = "tool_use" ─────────────────────────────────────────┐  │
│       (course-specific question)                                         │  │
│                                                                          ▼  │
│  _handle_tool_execution()                                                   │
│  │                                                                          │
│  ├─ For each tool_use block:                                                │
│  │    ToolManager.execute_tool("search_course_content", **args)             │
│  │    (see Tool Execution section below)                                    │
│  │                                                                          │
│  ├─ API Call #2 ──────────────────────────────────────────────────────────┐ │
│  │   messages: [                                                          │ │
│  │     { role: user,      content: original query        },              │ │
│  │     { role: assistant, content: [tool_use block]      },              │ │
│  │     { role: user,      content: [tool_result block]   }               │ │
│  │   ]                                                                    │ │
│  │   (no tools passed — forces final answer generation)                  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│       return final_response.content[0].text                                 │
└───────────────┬─────────────────────────────────────────────────────────────┘
                │ tool call
┌───────────────▼─────────────────────────────────────────────────────────────┐
│               ToolManager + CourseSearchTool  (backend/search_tools.py)     │
│                                                                             │
│  ToolManager.execute_tool("search_course_content", query, course_name?,     │
│                                                          lesson_number?)    │
│  │                                                                          │
│  └─ CourseSearchTool.execute(query, course_name, lesson_number)             │
│       │                                                                     │
│       ├─ VectorStore.search(query, course_name, lesson_number)              │
│       │   (see VectorStore section below)                                   │
│       │                                                                     │
│       ├─ if results.error  → return error string                            │
│       ├─ if results.empty  → return "No relevant content found..."          │
│       │                                                                     │
│       └─ _format_results(results)                                           │
│             for each (doc, metadata):                                       │
│               builds: "[CourseName - Lesson N]\n<chunk text>"               │
│               appends: "CourseName - Lesson N" to self.last_sources         │
│             returns joined string of all formatted blocks                   │
└───────────────┬─────────────────────────────────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────────────────────────────┐
│                     VectorStore  (backend/vector_store.py)                  │
│                                                                             │
│  ChromaDB PersistentClient  (./chroma_db)                                   │
│  Embedding: SentenceTransformer("all-MiniLM-L6-v2")                         │
│                                                                             │
│  Collections:                                                               │
│  ┌──────────────────────────────┐  ┌──────────────────────────────────────┐ │
│  │  course_catalog              │  │  course_content                      │ │
│  │  1 doc per course            │  │  1 doc per chunk (~800 chars)        │ │
│  │  id = course title           │  │  id = title_chunkindex               │ │
│  │  metadata:                   │  │  metadata:                           │ │
│  │    title, instructor,        │  │    course_title,                     │ │
│  │    course_link,              │  │    lesson_number,                    │ │
│  │    lessons_json (JSON str),  │  │    chunk_index                       │ │
│  │    lesson_count              │  │                                      │ │
│  └──────────────────────────────┘  └──────────────────────────────────────┘ │
│                                                                             │
│  search(query, course_name?, lesson_number?)                                │
│  │                                                                          │
│  ├─ Step 1 — Course resolution (if course_name given):                      │
│  │    query course_catalog with course_name text                            │
│  │    returns closest matching course title (semantic match)                │
│  │    if none found → return SearchResults.empty(error)                     │
│  │                                                                          │
│  ├─ Step 2 — Build filter:                                                  │
│  │    both provided  → { "$and": [{course_title}, {lesson_number}] }        │
│  │    course only    → { "course_title": title }                            │
│  │    lesson only    → { "lesson_number": N }                               │
│  │    neither        → None  (search all content)                           │
│  │                                                                          │
│  └─ Step 3 — Query course_content:                                          │
│       n_results = MAX_RESULTS (5)                                           │
│       returns top-5 semantically similar chunks + metadata + distances      │
└─────────────────────────────────────────────────────────────────────────────┘


### Full Request/Response Timeline

```
Browser                    FastAPI              RAGSystem          Claude API        ChromaDB
  │                           │                     │                  │                │
  │── GET /api/courses ──────▶│                     │                  │                │
  │                           │── get_course_analytics() ────────────────────────────▶ │
  │                           │◀─ { total, titles[] } ─────────────────────────────── │
  │◀─ { total_courses, ───────│                     │                  │                │
  │    course_titles[] }      │                     │                  │                │
  │                           │                     │                  │                │
  │  [user types query]       │                     │                  │                │
  │                           │                     │                  │                │
  │── POST /api/query ───────▶│                     │                  │                │
  │   {query, session_id}     │                     │                  │                │
  │   [loading spinner shown] │── rag.query() ─────▶│                  │                │
  │                           │                     │── get_history() ─┤                │
  │                           │                     │                  │                │
  │                           │                     │── API Call #1 ──▶│                │
  │                           │                     │   {system,msgs,  │                │
  │                           │                     │    tools}        │                │
  │                           │                     │                  │                │
  │                           │      ┌──────────────┤◀─ stop:"end_turn"│                │
  │                           │      │  OR          │                  │                │
  │                           │      │              │◀─ stop:"tool_use"│                │
  │                           │      │              │   {tool,args}    │                │
  │                           │      │              │── search() ─────────────────────▶│
  │                           │      │              │                  │   catalog query │
  │                           │      │              │◀──────────────────────────────── │
  │                           │      │              │   course title   │                │
  │                           │      │              │── content query ─────────────────▶│
  │                           │      │              │◀──────────────────────────────── │
  │                           │      │              │   top-5 chunks   │                │
  │                           │      │              │── API Call #2 ──▶│                │
  │                           │      │              │   {msgs+results} │                │
  │                           │      │              │◀─ final answer ──│                │
  │                           │      └──────────────▶                  │                │
  │                           │◀─ (answer, sources) ─│                  │                │
  │◀─ {answer,sources, ───────│                     │                  │                │
  │    session_id}            │                     │                  │                │
  │  [render markdown]        │                     │                  │                │
  │  [show sources panel]     │                     │                  │                │
```


### Session State Across Multiple Turns

```
Turn 1                          Turn 2                          Turn 3
──────                          ──────                          ──────
session_id = null               session_id = "session_1"        session_id = "session_1"

FastAPI creates "session_1"     SessionManager returns:         SessionManager returns:
SessionManager: []              "User: <Q1>                     "User: <Q2>
                                 Assistant: <A1>"                Assistant: <A2>"
                                                                (Q1/A1 dropped — window=2)

System prompt =                 System prompt =                 System prompt =
  SYSTEM_PROMPT                   SYSTEM_PROMPT +                 SYSTEM_PROMPT +
                                  "\nPrevious conversation:       "\nPrevious conversation:
                                   User: Q1                        User: Q2
                                   Assistant: A1"                  Assistant: A2"
```


### Data Ingestion Pipeline (Startup)

```
docs/
├── course1_script.txt
├── course2_script.txt          Each file:
├── course3_script.txt          ┌──────────────────────────────────────────────┐
└── course4_script.txt          │ Course Title: <title>                        │
                                │ Course Link: <url>                           │
                                │ Course Instructor: <name>                    │
                                │                                              │
                                │ Lesson 1: <title>                            │
                                │ Lesson Link: <url>                           │
                                │ <lesson text...>                             │
                                │                                              │
                                │ Lesson 2: ...                                │
                                └──────────────────────────────────────────────┘
                                              │
                                              ▼
                                   DocumentProcessor
                                              │
                          ┌───────────────────┴────────────────────┐
                          ▼                                        ▼
                   Course object                          List[CourseChunk]
                   ┌─────────────┐                       ┌──────────────────┐
                   │ title       │                       │ content (≤800c)  │
                   │ course_link │                       │ course_title     │
                   │ instructor  │                       │ lesson_number    │
                   │ lessons[]   │                       │ chunk_index      │
                   └─────────────┘                       └──────────────────┘
                          │                                        │
                          ▼                                        ▼
                   course_catalog                          course_content
                   (1 row/course)                         (N rows/course)
                   ChromaDB                               ChromaDB
                   embedded by                            embedded by
                   MiniLM-L6-v2                           MiniLM-L6-v2
```

---

## Running the App

### Prerequisites

1. Install `uv` (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
2. Install dependencies:
   ```bash
   uv sync
   ```
3. Create a `.env` file in the project root:
   ```
   ANTHROPIC_API_KEY=your_key_here
   ```

### Option 1 — Shell script
```bash
chmod +x run.sh
./run.sh
```

### Option 2 — Manual
```bash
cd backend
uv run uvicorn app:app --reload --port 8000
```

### Then open
- **App**: http://localhost:8000
- **API docs**: http://localhost:8000/docs

> On Windows, run these commands in **Git Bash** (not cmd or PowerShell).

