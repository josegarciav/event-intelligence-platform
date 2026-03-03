# Admin Service — Pulsecity IAM

FastAPI service providing application-level identity and access management (IAM):
user accounts, role-based access control, and API key management.

## Roles

| Role | Permissions |
|------|-------------|
| `admin` | Full access: create/update/delete users, manage any API key |
| `editor` | Write event data, no user management |
| `viewer` | Read-only access |

## Endpoints

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Email + password → JWT |
| POST | `/auth/refresh` | Refresh JWT (requires valid token) |

### Users (admin only)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/users/` | List all users |
| POST | `/users/` | Create user |
| GET | `/users/{id}` | Get user by ID |
| PATCH | `/users/{id}` | Update role or active status |
| DELETE | `/users/{id}` | Delete user |

### API Keys
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api-keys/generate` | Generate API key for current user |
| DELETE | `/api-keys/{key}` | Revoke API key |

## Auth Flow

```bash
# 1. Login
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@pulsecity.com", "password": "your-password"}'
# → {"access_token": "eyJ...", "token_type": "bearer"}

# 2. Use token
curl http://localhost:8001/users/ \
  -H "Authorization: Bearer eyJ..."
```

## Local Development

```bash
cd services/admin

# Install dependencies
uv sync

# Set up environment
cp .env.example .env
# Edit .env with your DATABASE_URL

# Run (requires PostgreSQL running)
uv run uvicorn src.main:app --reload --port 8001

# Interactive docs
open http://localhost:8001/docs
```

## JWT Configuration

- Algorithm: HS256
- Default expiry: 24 hours (configurable via `ACCESS_TOKEN_EXPIRE_HOURS`)
- Secret: set `SECRET_KEY` env var (minimum 32 random chars for production)
