# VersionAI Ingestion Service

Production-ready FastAPI microservice for ingesting files (video, audio, text, PDF) into the VersionAI pipeline.

## Architecture

```
Client ──► FastAPI Upload ──► Validation ──► S3 Storage ──► SQS Queue ──► Workers
```

**Pipeline:** Upload endpoint receives files, validates type/size/integrity, stores in S3, publishes a processing message to SQS with resolved downstream pipelines (Whisper, FFmpeg, embeddings, OCR).

## Quick Start

### 1. Local development with Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

This starts the ingestion service on `http://localhost:8000` with LocalStack providing S3 and SQS.

### 2. Local development without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

### 3. Run tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/upload/` | Upload a single file |
| `POST` | `/api/v1/upload/batch` | Upload multiple files |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Swagger UI |
| `GET` | `/redoc` | ReDoc |

### Upload a file

```bash
curl -X POST http://localhost:8000/api/v1/upload/ \
  -F "file=@video.mp4"
```

### Upload with API key

```bash
curl -X POST http://localhost:8000/api/v1/upload/ \
  -H "X-API-Key: your-secret-key" \
  -F "file=@document.pdf"
```

## Configuration

All settings are controlled via environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | `development` / `staging` / `production` |
| `MAX_UPLOAD_SIZE_BYTES` | `524288000` | Max file size (500 MB) |
| `S3_BUCKET_NAME` | `versionai-ingestion` | Target S3 bucket |
| `S3_ENDPOINT_URL` | — | Custom endpoint (MinIO/LocalStack) |
| `SQS_QUEUE_URL` | — | SQS queue URL for processing messages |
| `API_KEY` | — | Optional API key for request authentication |

## File Validation

- **Extension blocking:** Dangerous extensions (`.exe`, `.sh`, `.bat`, etc.) are rejected.
- **Magic-byte detection:** MIME type is detected from file contents, not the `Content-Type` header.
- **Size limits:** Configurable max upload size (default 500 MB).
- **Integrity:** SHA-256 checksum computed and stored with S3 metadata.

## Supported File Types

| Category | MIME Types |
|----------|------------|
| Video | `video/mp4`, `video/quicktime`, `video/webm`, `video/x-matroska`, `video/x-msvideo` |
| Audio | `audio/mpeg`, `audio/wav`, `audio/ogg`, `audio/flac`, `audio/mp4` |
| Text | `text/plain`, `text/csv`, `text/markdown` |
| PDF | `application/pdf` |
| Document | DOCX |

## Processing Pipelines

Files are automatically routed to downstream AI pipelines based on category:

| Category | Pipelines |
|----------|-----------|
| Video | Transcription (Whisper), Frame Extraction (FFmpeg) |
| Audio | Transcription (Whisper) |
| Text | Embedding |
| PDF | OCR, Embedding |
| Document | OCR, Embedding |

## Project Structure

```
ingestion-service/
├── app/
│   ├── main.py              # FastAPI app & lifespan
│   ├── config.py             # Pydantic settings
│   ├── dependencies.py       # DI providers
│   ├── api/
│   │   ├── router.py         # v1 API router
│   │   └── v1/upload.py      # Upload endpoints
│   ├── models/
│   │   ├── enums.py          # FileCategory, ProcessingPipeline
│   │   └── schemas.py        # Request/response models
│   ├── services/
│   │   ├── validation.py     # File validation (magic bytes, size, type)
│   │   ├── storage.py        # Async S3 storage
│   │   ├── queue.py          # SQS publisher
│   │   └── metadata.py       # Metadata extraction & pipeline routing
│   ├── middleware/
│   │   └── logging.py        # Request logging middleware
│   └── utils/
│       └── exceptions.py     # Custom exception hierarchy
├── tests/
│   ├── conftest.py
│   ├── test_upload.py
│   └── test_validation.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```
