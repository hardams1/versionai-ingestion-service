# VersionAI Processing & Embedding Service

A Python-based microservice that consumes messages from SQS (published by the Ingestion Service), processes files into structured knowledge, and stores embeddings in a vector database for downstream AI retrieval.

## Architecture

```
┌─────────────────┐     ┌──────────────────────────────────────────────────┐     ┌──────────────┐
│                  │     │         Processing & Embedding Service           │     │              │
│  Ingestion       │     │                                                  │     │  Vector DB   │
│  Service         │────▶│  SQS Consumer ──▶ Pipeline Orchestrator          │────▶│  (FAISS /    │
│                  │ SQS │                   │                              │     │   Pinecone)  │
└─────────────────┘     │                   ├─▶ S3 Download                │     └──────────────┘
                         │                   ├─▶ Text Extraction            │
                         │                   ├─▶ Text Cleaning              │
                         │                   ├─▶ Chunking (token-aware)     │
                         │                   ├─▶ Embedding Generation       │
                         │                   └─▶ Vector Store               │
                         │                                                  │
                         │  Health API (FastAPI) ◀── /health, /api/v1/...   │
                         └──────────────────────────────────────────────────┘
```

## Processing Pipeline

| Step | Description | Module |
|------|-------------|--------|
| 1. Consume | Long-poll SQS for messages from Ingestion Service | `services/queue_consumer.py` |
| 2. Download | Fetch file from S3 to local temp storage | `services/storage.py` |
| 3. Extract | Convert file to raw text (PDF, DOCX, audio, video, text) | `services/text_extractor.py` |
| 4. Clean | Normalize Unicode, fix encoding, collapse whitespace | `services/text_cleaner.py` |
| 5. Chunk | Token-aware recursive splitting with overlap | `services/chunker.py` |
| 6. Embed | Generate vectors via OpenAI or sentence-transformers | `services/embedder.py` |
| 7. Store | Persist to FAISS (dev) or Pinecone (prod) | `services/vector_store.py` |
| 8. Track | SQLite-backed status and idempotency tracking | `utils/idempotency.py` |

## Input Message Format

### From Ingestion Service (primary)
```json
{
  "ingestion_id": "uuid",
  "filename": "report.pdf",
  "s3_bucket": "versionai-ingestion",
  "s3_key": "uploads/uuid/report.pdf",
  "file_category": "pdf",
  "mime_type": "application/pdf",
  "size_bytes": 245000,
  "checksum_sha256": "abc123...",
  "pipelines": ["ocr", "embedding"],
  "metadata": {"user_id": "user-123"},
  "created_at": "2026-03-30T00:00:00Z"
}
```

### Simplified format (alternative)
```json
{
  "file_id": "uuid",
  "user_id": "user-123",
  "file_type": "pdf",
  "s3_url": "s3://bucket/key",
  "processing_steps": ["parse", "embed", "store"]
}
```

## Quick Start

### 1. Prerequisites
- Python 3.12+
- Docker & Docker Compose
- ffmpeg (for audio/video processing)

### 2. Environment Setup
```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Run with Docker Compose
```bash
docker compose up --build
```

### 4. Run Locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health + worker status |
| `GET` | `/api/v1/status` | List all processing records |
| `GET` | `/api/v1/status/{ingestion_id}` | Get status for a specific file |
| `GET` | `/api/v1/metrics` | Worker metrics and status counts |
| `GET` | `/docs` | OpenAPI / Swagger UI |
| `GET` | `/redoc` | ReDoc documentation |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_PROVIDER` | `openai` | `openai` or `sentence-transformers` |
| `OPENAI_API_KEY` | — | Required for OpenAI embeddings |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI model name |
| `VECTOR_STORE_PROVIDER` | `faiss` | `faiss` or `pinecone` |
| `CHUNK_SIZE` | `512` | Target tokens per chunk |
| `CHUNK_OVERLAP` | `64` | Token overlap between chunks |
| `WORKER_CONCURRENCY` | `3` | Max parallel message processing |
| `SQS_VISIBILITY_TIMEOUT` | `300` | Seconds before failed message reappears |

## Design Principles

- **Idempotent**: Safe to retry — already-processed messages are skipped via SQLite state tracking
- **Fault-tolerant**: Failed messages return to SQS after visibility timeout for retry
- **Modular**: Each pipeline step is an independent, testable service class
- **Scalable**: Bounded concurrency with async semaphore; horizontal scaling via multiple instances

## Project Structure

```
processing-embedding-service/
├── app/
│   ├── main.py                 # FastAPI app + worker lifecycle
│   ├── config.py               # pydantic-settings configuration
│   ├── dependencies.py         # DI factories
│   ├── worker.py               # SQS polling loop with graceful shutdown
│   ├── models/
│   │   ├── enums.py            # FileCategory, ProcessingStatus, etc.
│   │   └── schemas.py          # Pydantic models for messages and records
│   ├── services/
│   │   ├── queue_consumer.py   # SQS long-polling consumer
│   │   ├── storage.py          # S3 file downloader
│   │   ├── text_extractor.py   # Multi-format text extraction
│   │   ├── text_cleaner.py     # Unicode normalization, whitespace cleanup
│   │   ├── chunker.py          # Token-aware recursive text splitting
│   │   ├── embedder.py         # OpenAI / sentence-transformers
│   │   ├── vector_store.py     # FAISS / Pinecone storage
│   │   └── processor.py        # Pipeline orchestrator
│   ├── middleware/
│   │   └── logging.py          # Request logging middleware
│   └── utils/
│       ├── exceptions.py       # Error hierarchy
│       └── idempotency.py      # SQLite state store
├── tests/
│   ├── conftest.py
│   ├── test_text_cleaner.py
│   ├── test_chunker.py
│   └── test_processor.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```
