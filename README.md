# Agentic Lab Assistant

A containerized, local first agentic workflow system that processes lab requests asynchronously using a planner executor architecture.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  FastAPI    │────▶│   Redis     │
│             │     │    API      │     │   Queue     │
└─────────────┘     └─────────────┘     └──────┬──────┘
                           │                   │
                           ▼                   ▼
                    ┌─────────────┐     ┌─────────────┐
                    │  Postgres   │◀────│   Worker    │
                    │     DB      │     │   (Agent)   │
                    └─────────────┘     └─────────────┘
```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Make (optional, for convenience)

### Run Everything

```bash
# One command to rule them all
docker compose up

# Or with make
make up
```

### Demo Workflow

1. **Submit a request:**
```bash
curl -X POST http://localhost:8000/requests \
  -H "Content-Type: application/json" \
  -d '{"text": "How do I handle a database connection timeout?", "priority": "high"}'
```

Response:
```json
{"request_id": "abc123...", "status": "queued"}
```

2. **Check status:**
```bash
curl http://localhost:8000/requests/{request_id}
```

Response (when done):
```json
{
  "request_id": "abc123...",
  "status": "done",
  "result": {
    "summary": "To handle database connection timeouts...",
    "steps": ["Check connection pool", "Verify network", "Review logs"],
    "sources": ["database_troubleshooting.md", "INC-001"]
  },
  "error": null
}
```

3. **Health check:**
```bash
curl http://localhost:8000/health
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/requests` | Submit a new lab request |
| GET | `/requests/{id}` | Get request status and result |
| GET | `/health` | Health check |

### Request Body (POST /requests)
```json
{
  "text": "Your question or request",
  "priority": "normal|high"
}
```

### Response Schema
```json
{
  "request_id": "uuid",
  "status": "queued|running|done|failed",
  "result": {
    "summary": "string",
    "steps": ["string"],
    "sources": ["string"]
  },
  "error": "string|null"
}
```

## Agent Workflow

The agent follows a two-step process:

### Step A: Planner
- Analyzes the input request
- Produces a structured JSON plan with steps and required tools
- Tools available: `search_docs`, `query_incidents`

### Step B: Executor
- Executes the plan step by step
- Calls tools based on the plan
- Aggregates results and produces final answer

### Tools

1. **search_docs(query)**: Keyword search over markdown runbooks in `data/runbooks/`
2. **query_incidents(query)**: SQL search against the `incidents` table

## Development

### Make Targets

```bash
make up       # Start all services
make down     # Stop all services
make demo     # Run demo requests
make test     # Run pytest
make eval     # Run evaluation harness
make lint     # Run ruff linter
make logs     # Tail service logs
make shell    # Shell into API container
make clean    # Remove volumes and images
```

### Running Tests

```bash
# With Docker
make test

# Locally (requires running services)
pytest tests/ -v
```

### Running Evaluation

```bash
# With Docker
make eval

# Locally
python eval/run_eval.py
```

## Configuration

Environment variables (see `docker-compose.yml`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://...` | Postgres connection string |
| `REDIS_URL` | `redis://redis:6379` | Redis connection string |
| `USE_REAL_LLM` | `false` | Enable real LLM (requires `LLM_API_KEY`) |
| `LLM_API_KEY` | - | API key for LLM provider |
| `LLM_MODEL` | `gpt-4.1` | LLM model to use |

## Project Structure

```
├── api/                 # FastAPI application
│   ├── main.py         # App entrypoint
│   ├── routes.py       # API endpoints
│   ├── models.py       # SQLAlchemy models
│   ├── schemas.py      # Pydantic schemas
│   └── database.py     # DB connection
├── worker/             # Background worker
│   ├── tasks.py        # RQ task definitions
│   └── agent/          # Agent implementation
│       ├── planner.py  # Planning logic
│       ├── executor.py # Execution logic
│       └── tools.py    # Tool implementations
├── data/runbooks/      # Markdown knowledge base
├── eval/               # Evaluation harness
│   ├── prompts.jsonl   # Test prompts
│   ├── schema.json     # Output validation schema
│   └── run_eval.py     # Eval runner
├── tests/              # Pytest tests
└── .github/workflows/  # CI pipeline
```

## Updates:
Currently working on a frontend user friendly UI using React.