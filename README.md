# DataGenie

Self-service NL-to-SQL analytics SaaS. Business stakeholders ask questions in plain English and get back tables and charts — no SQL required.

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Fill in .env with your Supabase + LLM API credentials

# Generate secret keys
python -c "from app.core.security import generate_keys; import json; print(json.dumps(generate_keys(), indent=2))"

# Run migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend
npm install

cp .env.local.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000

npm run dev
```

App: http://localhost:3000

---

## Environment Variables (backend/.env)

| Variable | Description |
|---|---|
| `JWT_SECRET_KEY` | 32-byte hex secret for JWT signing |
| `FERNET_KEY` | Fernet key for encrypting data source credentials |
| `DATABASE_URL` | Supabase Postgres async URL (`postgresql+asyncpg://...`) |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service-role key (for Storage uploads) |
| `SUPABASE_STORAGE_BUCKET` | Storage bucket name for CSV uploads (default: `csv-uploads`) |
| `LLM_PROVIDER` | `openai` or `anthropic` |
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key (if using Anthropic) |

---

## Project Structure

```
backend/
  app/
    core/security.py        ← Fernet + JWT
    connectors/             ← CSV, Postgres, MySQL, Google Sheets
    services/
      nl_to_sql.py          ← Core 9-step pipeline
      llm.py                ← OpenAI / Anthropic wrapper
      schema_embeddings.py  ← pgvector schema indexing
    api/
      deps.py               ← Tenant-scoped auth + repository
      routes/               ← auth, query, data-sources, glossary
    models/                 ← SQLAlchemy models
  alembic/                  ← DB migrations

frontend/
  app/
    (auth)/login/           ← Login + signup
    dashboard/
      chat/                 ← Main chat interface
      sources/              ← Connect data sources
      settings/             ← Glossary + settings
  components/
    ChatInterface.tsx
    ResultsTable.tsx
    ResultsChart.tsx
  lib/
    api.ts                  ← API client
```

---

## Deployment (Railway + Vercel + Supabase)

1. Create a [Supabase](https://supabase.com) project — grab the Postgres URL, project URL, and service key
2. Create a `csv-uploads` Storage bucket in Supabase (set private)
3. Deploy backend to [Railway](https://railway.app) — connect GitHub repo, set env vars, add Redis addon
4. Deploy frontend to [Vercel](https://vercel.com) — set `NEXT_PUBLIC_API_URL` to your Railway backend URL
5. Run `alembic upgrade head` via Railway's shell

Estimated cost: ~$55–75/month for the first cohort of customers.
