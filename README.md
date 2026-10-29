# AI SaaS Starter Kit

A multi-tenant SaaS foundation with organization-scoped access, password authentication, signed bearer tokens, monthly AI usage metering, quota reservations, an AI text-summary feature, and a Next.js dashboard.

> **Scope:** this is an engineering starter, not a production-hardened SaaS. The default AI provider is deterministic mock mode so the project works without external credentials. Set `AI_PROVIDER=openai` and provide an API key to use live model responses.

## Features

- **Authentication:** registration, login, password hashing with `scrypt`, signed JWT access tokens, and current-user endpoint.
- **Multi-tenancy:** organizations and memberships with `owner` / `member` roles. Every organization-specific endpoint verifies membership before accessing data.
- **Usage metering:** a usage-event ledger records user, organization, provider/model, input/output/total tokens, estimated cost, and billing month.
- **Quota enforcement:** a monthly token limit with an atomic database reservation before an AI call. A failed provider call releases its reservation.
- **AI adapter:** mock provider for local development and CI; optional OpenAI provider with token usage capture.
- **Dashboard:** sign up/sign in, organization selector, usage meter, and AI summary playground.
- **Delivery:** tests, Dockerfiles, Docker Compose with PostgreSQL, GitHub Actions CI, environment example, and API docs.

## Architecture

```text
Next.js dashboard
    | bearer JWT
    v
FastAPI (/api)
    +-- Auth service ---- Users / Memberships
    +-- Tenant checks --- Organizations
    +-- AI adapter ------ Mock or optional OpenAI
    +-- Quota reserve --- Organization monthly counter
    +-- Usage ledger ---- Usage events + cost estimates
                 |
                 v
             PostgreSQL (Docker) / SQLite (local)
```

## Quick start: local Python

Python 3.11+ is recommended.

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

The API uses SQLite by default and creates `saas.db` in the current directory. Visit [http://localhost:8000/docs](http://localhost:8000/docs).

## Run the dashboard

In a separate terminal:

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The default API base URL is `http://localhost:8000/api`.

## Docker Compose

Docker Compose starts PostgreSQL, the API, and the dashboard:

```bash
cp .env.example .env
# Set a strong SECRET_KEY in .env before sharing/deploying.
docker compose up --build
```

- Dashboard: http://localhost:3000
- API docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432 (development port)

Compose defaults to the mock AI provider. To use OpenAI, set `AI_PROVIDER=openai` and `OPENAI_API_KEY` in `.env`. Configure model and prices to match your selected provider and actual current pricing; the included price defaults are example values, not a billing source of truth.

## API overview

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/auth/register` | Create user + first organization |
| `POST` | `/api/auth/login` | Authenticate and return a bearer token |
| `GET` | `/api/me` | Current user |
| `GET` | `/api/organizations` | Organizations for current user |
| `POST` | `/api/organizations` | Create an organization (creator becomes owner) |
| `GET` | `/api/organizations/{id}/usage` | Current-month usage for a membership |
| `POST` | `/api/ai/summarize` | Summarize text within an organization quota |
| `GET` | `/api/organizations/{id}/usage/events` | Recent usage ledger entries for that organization |
| `GET` | `/health` | Health check |

Registration body:

```json
{
  "email": "owner@example.com",
  "password": "use-a-long-password",
  "organization_name": "Example Workspace"
}
```

Summary request body:

```json
{
  "organization_id": "<organization-id-from-register>",
  "input_text": "Paste text to summarize here...",
  "max_output_tokens": 160
}
```

Pass the returned token as `Authorization: Bearer <access_token>`.

## Run tests

```bash
python -m pip install -e ".[dev]"
pytest -q
```

Tests use isolated SQLite databases and the mock AI provider; no API key or live provider call is required.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./saas.db` | SQLAlchemy database URL |
| `SECRET_KEY` | development-only placeholder | JWT signing secret; set a long random value outside local development |
| `ACCESS_TOKEN_MINUTES` | `60` | JWT access token lifetime |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed browser origins |
| `AI_PROVIDER` | `mock` | `mock` or `openai` |
| `OPENAI_API_KEY` | unset | Required for OpenAI provider |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model identifier for the optional adapter |
| `OPENAI_INPUT_PRICE_PER_1M_USD` | `0.15` | Editable cost estimate per million input tokens |
| `OPENAI_OUTPUT_PRICE_PER_1M_USD` | `0.60` | Editable cost estimate per million output tokens |
| `DEFAULT_MONTHLY_TOKEN_LIMIT` | `10000` | New organization monthly token allowance |

## Security and production checklist

Before production use, address these intentionally out-of-scope items:

- Replace the development secret and rotate it; use a managed secret store.
- Use HTTPS, refresh-token/session rotation, email verification, password reset, rate limiting, and account lockout protections.
- Prefer secure, `HttpOnly`, `SameSite` cookies over localStorage bearer tokens for browser sessions.
- Add verified email/SSO, invitations, organization member management, and explicit role/permission policies.
- Run Alembic migrations rather than relying on `create_all`; validate migrations and database backups.
- Add provider timeouts/retries, request idempotency, abuse protection, and concurrency tests across multiple API workers.
- Treat token quota as a usage guardrail, not a financial billing ledger. Reconcile provider usage and pricing before charging customers.
- Add subscription billing (e.g. Stripe), webhook signature validation, plan mapping, invoices, and dunning only when needed.
- Add observability, audit-log retention, data deletion/export policies, and tenant isolation tests against the production database.
- Review whether submitted text contains personal, confidential, or regulated data before sending it to an external provider.

## Roadmap

- [ ] Add Alembic migrations and staging/production deployment examples.
- [ ] Add Stripe subscription lifecycle and webhook processing.
- [ ] Add invitations, organization members, and configurable roles.
- [ ] Add secure cookie sessions and a full session lifecycle.
- [ ] Add a second AI capability and per-model pricing registry.
- [ ] Add audit exports and admin usage reports.

## License

MIT. See [LICENSE](LICENSE).
