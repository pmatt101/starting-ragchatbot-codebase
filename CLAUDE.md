# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

All commands must be run from the **`backend/`** directory using `uv`. On Windows, use Git Bash.

```bash
# Install dependencies (from project root)
uv sync

# Add a new dependency
uv add <package>

# Remove a dependency
uv remove <package>

# Start the server (from backend/)
uv run uvicorn app:app --reload --port 8000

# Or use the convenience script from project root
./run.sh
```

The app serves at `http://localhost:8000`. The frontend is served as static files by FastAPI — there is no separate frontend build step.

Requires a `.env` file in the project root (copy from `.env.example`):
```
ANTHROPIC_API_KEY=your_key_here
```

There is no test suite in this codebase.

## Architecture

This is a RAG (Retrieval-Augmented Generation) chatbot. The backend is a single FastAPI process that serves both the API and the static frontend.

### Key design: Agentic tool-use loop

The core AI interaction uses Anthropic's tool-use API — Claude is given a `search_course_content` tool and decides autonomously whether to call it. This means there are always **two Claude API calls** for course-specific questions (one to decide+invoke the tool, one to synthesize results), and **one call** for general questions.

```
app.py → RAGSystem → AIGenerator → Claude API call #1
                                        │
                          [tool_use] → CourseSearchTool → VectorStore (ChromaDB)
                                        │
                                   Claude API call #2 (with search results)
```

### ChromaDB collections

Two separate collections in `./chroma_db` (relative to `backend/`):
- **`course_catalog`** — one document per course; used for fuzzy course name resolution via semantic search
- **`course_content`** — one document per text chunk (~800 chars with 100-char overlap); used for actual RAG retrieval

Course name resolution works by embedding the user-supplied name and finding the nearest course in `course_catalog`, so partial/fuzzy names work automatically.

### Document format

Course files in `docs/` must follow this structure for the parser (`document_processor.py`) to extract metadata and lessons:

```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 1: <lesson title>
Lesson Link: <url>
<lesson text...>

Lesson 2: ...
```

Documents are parsed and indexed once at startup; already-indexed courses are skipped by title comparison.

### Session management

Sessions are in-memory only (lost on server restart). `SessionManager` keeps a rolling window of the last `MAX_HISTORY=2` Q&A exchanges, passed as a string in the Claude system prompt on each request.

### Configuration

All tuneable parameters live in `backend/config.py` as a single `Config` dataclass:
- `ANTHROPIC_MODEL` — Claude model ID
- `CHUNK_SIZE` / `CHUNK_OVERLAP` — document chunking
- `MAX_RESULTS` — number of ChromaDB results returned per search
- `MAX_HISTORY` — conversation turns retained per session
- `CHROMA_PATH` — ChromaDB storage path (relative to `backend/`)
