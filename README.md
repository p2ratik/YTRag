# YouTube RAG Chat

A full-stack YouTube transcript RAG (retrieval-augmented generation) app. Users sign up, log in, create conversations, attach a YouTube video, and ask questions. The backend retrieves relevant transcript chunks from a Postgres + pgvector store and streams answers from an LLM.

## System Architecture

### Architecture diagram
```mermaid
flowchart LR
  subgraph Client[Frontend (Vite)]
    UI[Login + Chat UI]
    LS[localStorage: access_token]
  end

  subgraph API[FastAPI Backend]
    AUTH[Auth API\n/signup, /login, /logout]
    CHAT[Chat API\n/conversations, /message]
    WS[WebSocket\n/api/chat/ws]
    YT[YouTube Ingestion\n/upload-url]
    RAG[RAG Pipeline\nretrieval + rerank]
    LLM[LLM Adapter\nGroq streaming]
    EMB[Embeddings\nOpenAI text-embedding-3-small]
  end

  subgraph DB[Postgres + pgvector]
    USERS[(users)]
    CONVS[(conversations)]
    MSGS[(messages)]
    VEC[(vector_store)]
  end

  subgraph EXT[External Services]
    YTA[YouTube Transcript API]
    GROQ[Groq LLM]
    OAI[OpenAI Embeddings]
  end

  UI --> AUTH
  UI --> CHAT
  UI --> WS
  AUTH --> USERS
  CHAT --> CONVS
  CHAT --> MSGS
  YT --> YTA
  YT --> EMB
  EMB --> OAI
  EMB --> VEC
  RAG --> VEC
  RAG --> LLM
  LLM --> GROQ

  LS -. Bearer token .-> CHAT
  LS -. Bearer token .-> WS
```

### High-level flow
1. **Frontend (Vite)** authenticates users and stores the short-lived access token in `localStorage`.
2. **FastAPI backend** validates the access token on every protected request and resolves the current user.
3. **YouTube ingestion** downloads transcripts, creates parent/child chunks, embeds them, and stores them in `vector_store`.
4. **RAG pipeline** retrieves and reranks relevant chunks, builds context, and streams LLM responses.

### Components
- **Frontend**: Vite app in [frontend/](frontend/)
- **Backend API**: FastAPI in [backend/](backend/)
- **Auth**: JWT access token + HttpOnly refresh cookie
- **Database**: Postgres with pgvector (schema in [backend/schema.sql](backend/schema.sql))
- **Embeddings**: OpenAI `text-embedding-3-small`
- **LLM**: Groq chat completions
- **Transcript source**: YouTube Transcript API

## Authentication & Session Model

```mermaid
sequenceDiagram
  participant UI as Frontend
  participant API as FastAPI
  participant DB as Postgres

  UI->>API: POST /api/login (FormData)
  API->>DB: validate user + password hash
  DB-->>API: user record
  API-->>UI: access_token (JSON) + refresh_token (HttpOnly cookie)

  UI->>API: GET /api/chat/conversations
  Note right of UI: Authorization: Bearer <access_token>
  API->>API: decode JWT, resolve user
  API->>DB: SELECT conversations
  DB-->>API: rows
  API-->>UI: conversations list
```

- **Login**: `POST /api/login` (FormData)
  - Validates credentials, issues access token and refresh token.
  - **Access token** is returned in JSON and stored in `localStorage` by the frontend.
  - **Refresh token** is stored as an HttpOnly cookie.
- **Authenticated calls**: Frontend sends `Authorization: Bearer <access_token>`.
- **JWT validation**: Dependencies decode the token, fetch the user, and inject `current_user` into handlers.

> Note: A refresh endpoint is not currently implemented. The refresh token cookie is issued for future expansion.

## RAG Pipeline (YouTube → Vectors → Answer)

1. **Upload URL**: `POST /api/upload-url` with `conversation_id` and `url` (FormData)
2. **Transcript chunking**: 30s child chunks with overlap; 3-minute parent chunks are derived
3. **Embedding**: OpenAI embeddings (768 dims)
4. **Vector store**: pgvector `vector(768)` in `vector_store`
5. **Retrieval**: cosine distance + cross-encoder rerank
6. **Context build**: top-ranked parent chunks with timestamps
7. **LLM response**: Groq streaming completion

## API Surface (Core)

- **Auth**
  - `POST /api/signup` (FormData: email, username, password)
  - `POST /api/login` (FormData: username, password)
  - `POST /api/logout`
- **Chat**
  - `POST /api/chat/conversations` (JSON: { title })
  - `GET /api/chat/conversations`
  - `GET /api/chat/conversations/{id}/messages`
  - `POST /api/chat/message` (JSON: { conversation_id, message, video_id? })
  - `WS /api/chat/ws` (JWT required)
- **YouTube ingestion**
  - `POST /api/upload-url` (FormData: conversation_id, url)

## WebSocket Protocol

The WebSocket streams assistant responses as JSON events:

- `ready`
- `assistant_start`
- `assistant_chunk` `{ delta }`
- `assistant_end`
- `error` `{ message }`

## Project Setup

### Prerequisites
- **Python** 3.11+
- **Node.js** 18+
- **PostgreSQL** 14+ with **pgvector** extension

### Environment Variables
Set these in a `.env` file at the repo root (loaded by backend):

```
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/DBNAME
OPENAI_API_KEY=...
GROQ_API_KEY=...
JWT_SECRET_KEY=...
JWT_REFRESH_SECRET_KEY=...
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
ALGORITHM=HS256
```

### Database Setup
1. Create a Postgres database.
2. Enable pgvector:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. Apply the schema in [backend/schema.sql](backend/schema.sql).

### Backend Setup
1. Create and activate a virtual environment.
2. Install dependencies:
   - `fastapi`, `uvicorn`, `sqlalchemy`, `asyncpg`, `python-dotenv`, `pgvector`, `sentence-transformers`, `openai`, `groq`, `youtube-transcript-api`, `bcrypt`, `pyjwt`
3. Run the API:
   ```bash
   uvicorn backend.main:app --reload
   ```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

The frontend expects the backend at `http://localhost:8000` and WebSocket at `ws://localhost:8000`.

## Key Data Models

- **User**: `users`
- **Conversation**: `conversations`
- **Message**: `messages`
- **VectorStore**: `vector_store` (pgvector embeddings + chunk metadata)

## Security Notes

- Access tokens are short-lived and stored in `localStorage`.
- Refresh tokens are HttpOnly cookies (set to `secure=false` for local dev).
- For production, enable HTTPS and set `secure=true` for cookies.

## Repo Layout

- [backend/](backend/): FastAPI app, services, models, and DB access
- [frontend/](frontend/): Vite UI and assets
- [backend/schema.sql](backend/schema.sql): Database schema
- [workflow.md](workflow.md): Request/response flow reference
