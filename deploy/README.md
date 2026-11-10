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

## Phase 5D deploy check (Alert Finish)

`POST /api/watches/{watch_id}/finish` was added in commit `0d5da2f`. If the
deployed Render release predates it, the button returns `404 Not Found`. Confirm
in `https://<backend-host>/openapi.json` that the path is present. If it is
missing, redeploy the backend from the current `main` (Phase 5D verified
`0f0634a`). No code change is needed for the contract itself — the frontend and
backend already agree on method and path.

## Email on Render

`render.yaml` does not include email variables. Add `EMAIL_DELIVERY_ENABLED`,
`EMAIL_FROM`, `EMAIL_TEST_RECIPIENT` and `RESEND_API_KEY` by hand (secret), then
redeploy. Keep `EMAIL_DELIVERY_ENABLED=false` until the safety conditions in
`docs/email_delivery.md` are met.
