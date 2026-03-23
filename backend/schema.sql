CREATE TABLE IF NOT EXISTS vector_store (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    video_id    TEXT NOT NULL,
    content     TEXT NOT NULL,
    start_time  NUMERIC(10, 3),
  end_time    NUMERIC(10, 3),
  chunk_level TEXT NOT NULL DEFAULT 'child' CHECK (chunk_level IN ('child', 'parent')),
  parent_chunk_id UUID REFERENCES vector_store(id) ON DELETE SET NULL,
  chunk_index INTEGER,
  parent_rank INTEGER,
    embedding   vector(768) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_vector_store_scope_level
ON vector_store (conversation_id, video_id, chunk_level);

CREATE INDEX IF NOT EXISTS idx_vector_store_scope_chunk_index
ON vector_store (conversation_id, video_id, chunk_index);

CREATE INDEX IF NOT EXISTS idx_vector_store_parent_chunk_id
ON vector_store (parent_chunk_id);

create table if not exists users(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_id text unique not null,
    user_name text unique not null,
    password text not null,
    created_at timestamp default now(),
    updated_at timestamp default now()
);

-- Conversations (one per chat session)
CREATE TABLE conversations (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES users(id),
  title       TEXT,             -- auto-generated from first message
  created_at  TIMESTAMPTZ DEFAULT now(),
  updated_at  TIMESTAMPTZ DEFAULT now()
);

-- Messages (every turn)
CREATE TABLE messages (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
  role            TEXT CHECK (role IN ('user', 'assistant', 'system')),
  content         TEXT NOT NULL,
  created_at      TIMESTAMPTZ DEFAULT now()
);


-- select * from messages inner join conversations on messages.conversation_id = conversations.id where conversations.user_id = '12345678-1234-1234-1234-123456789012';