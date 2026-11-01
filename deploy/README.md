# Deployment files (Phase 4A)

These files are templates only. No cloud resource was created.

- `../Dockerfile` — FastAPI container image for Render or any Docker host.
- `../render.yaml` — Render Blueprint for the backend, free plan.
- `../frontend/vercel.json` — Vercel static build + `/api` rewrite + SPA fallback + headers.
- `env.cloud.example` — backend environment variable template.

Before deploying:

1. Replace `REPLACE-WITH-RENDER-SERVICE.onrender.com` in `frontend/vercel.json`.
2. Fill `env.cloud.example` values in Render's dashboard, never in Git.
3. Set `CORS_ORIGINS` to the real Vercel domain(s), comma-separated.
4. Run Alembic only against the new cloud database.
5. Verify `/api/health`, login, approval, and SSE on all three device classes.
