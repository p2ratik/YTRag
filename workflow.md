Browser                          Backend
─────────────────────────────────────────────────────
  login form
      │  POST /api/login (FormData)
      │ ──────────────────────────────────────────→
      │                authenticate_user() + verify password
      │                issue_tokens() → JWT signed with secret
      │ ←─────────────────────────────────────────
  localStorage['access_token'] = JWT
  cookie: refresh_token (HttpOnly, browser holds it)

  fetchAuth('/chat/conversations')
  → Authorization: Bearer <JWT>
      │ ──────────────────────────────────────────→
      │                dependencies.py: decode JWT → user UUID
      │                DB: SELECT user WHERE id = UUID
      │                → current_user injected into handler
      │ ←─────────────────────────────────────────
  currentConvId = returned UUID    (in-memory only)

  POST /api/chat/message { conversation_id, message }
      │ ──────────────────────────────────────────→
      │  chat_service: store → history → RAG → LLM → store reply
      │ ←─────────────────────────────────────────
  { reply: "..." }
