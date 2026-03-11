# Muraho Deployment (Easy Mode)

This is the fastest reliable way to run CMS + DB + seed data.

## 1) One-command Docker startup

From `infra/docker`:

```bash
docker compose up -d --build postgres redis minio minio-init payload payload-seed
```

What this now does automatically:

- starts PostgreSQL, Redis, MinIO
- starts CMS (`payload`) in bootstrap mode (`npm run dev`) so schema is created
- runs one-shot `payload-seed` after CMS becomes healthy

## 2) Verify

```bash
docker compose ps
curl http://localhost:3000/admin
curl http://localhost:3000/api/health
```

Admin URL:

- `http://localhost:3000/admin`

Default admin seed credentials (override via env if needed):

- email: `admin@muraho.rw`
- password: `MurahoAdmin2026!`

## 3) Re-run seed (optional)

```bash
docker compose run --rm payload-seed
```

## 4) Local CMS + Docker infra (alternative)

If you prefer CMS outside Docker:

```bash
cd infra/docker
docker compose up -d postgres redis minio minio-init

cd ../../cms
npm install
npm run dev
npm run seed
```

## Notes

- `payload-seed` is idempotent for existing admin users.
- `/api/health` may show `degraded`/`unhealthy` if AI/Ollama are down; CMS + DB can still be functional.
- To change seed credentials, set:
  - `SEED_ADMIN_EMAIL`
  - `SEED_ADMIN_PASSWORD`
