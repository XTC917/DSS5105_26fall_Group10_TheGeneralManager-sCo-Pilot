# Email delivery — actual implementation & configuration (Phase 5B)

This document describes the **real** email code in the repo (not an assumed
SMTP design). Read it before enabling anything.

## 1. Two separate email paths

| Path | What it does | Sends real mail? |
| --- | --- | --- |
| Agent tool `send_email` (`backend/tools/actions.py`) | Proposes a **simulated** local send (`confirmed=false`) and records a local note. Prompt rules repeat "no SMTP". | **No** |
| Explicit delivery flow (`backend/routers/email.py`) | Draft → edit → confirm → send through the **Resend HTTP API**. | **Yes**, only to one configured test recipient |

The UI never auto-sends. The agent can only draft (`draft_chase_email`) or
propose a *simulated* send. Real delivery always requires a human clicking
**Save and preview → Confirm and send**.

## 2. How the flow works

1. **Draft** – the agent tool `draft_chase_email` returns bilingual drafts from
   `backend/services/email_templates.py`. No email address is inferred; the
   recipient is always `missing` until a human supplies it.
2. **Open / load** – `GET /api/email/turns/{turn_id}/drafts/{index}` returns the
   draft view (creates a row lazily on first save).
3. **Edit** – `PUT /api/email/turns/{turn_id}/drafts/{index}` saves
   recipient / subject / body with optimistic `version` locking and a
   `content_hash`. Editing **is** supported; if a `version` is stale the server
   replies `409` and the UI must reload.
4. **Confirm & send** – `POST /api/email/drafts/{draft_id}/send` requires
   `version` + `content_hash`. It writes an `email_send_attempts` row first
   (with an idempotency key), sets status `SENDING`, then calls Resend.
5. **Result** – the response carries `status` (`SUBMITTED` / `FAILED` /
   `UNKNOWN`), `can_send`, recipient, subject, body. Success is only shown when
   the provider returns a message id. Failures keep the draft for editing.

### Status values
`DRAFT → SENDING → SUBMITTED` (success) or `FAILED` (retryable by editing) or
`UNKNOWN` (timeout / ambiguous provider response). `SENDING` older than 2 min is
surfaced as `UNKNOWN` so a stuck attempt is never silently "sent".

### Duplicate-send protection
- `email_send_attempts` has `UNIQUE (draft_id, draft_version)` and a unique
  `idempotency_key` (passed to Resend as `Idempotency-Key`).
- A draft already in `SENDING / SUBMITTED / UNKNOWN / FAILED` returns the
  existing row instead of re-sending. To retry a `FAILED` draft the user edits
  and re-saves, which bumps `version` and resets status to `DRAFT`.

## 3. Environment variables (from the code)

Set in `backend/routers/email.py::_delivery_config`.

| Variable | Purpose | Required to enable real send |
| --- | --- | --- |
| `EMAIL_DELIVERY_ENABLED` | Master switch. Must be exactly `true`. Default off. | Yes |
| `EMAIL_FROM` | Verified Resend sender address (e.g. `onboarding@resend.dev`). | Yes |
| `EMAIL_TEST_RECIPIENT` | The **only** recipient permitted. Real sends are rejected unless the draft recipient matches this address. | Yes |
| `RESEND_API_KEY` | Resend API key (`re_...`). | Yes |

There is **no** SMTP host/port/user/password, no sender-name variable and no
TLS/SSL toggle — delivery is HTTP to `https://api.resend.com/emails`.

`_delivery_config()` enables delivery only when `EMAIL_DELIVERY_ENABLED=true`
**and** `EMAIL_FROM` **and** `RESEND_API_KEY` are set **and**
`EMAIL_TEST_RECIPIENT` is a single valid address.

## 4. Local `.env` template (copy, fill placeholders, never commit)

```dotenv
# Off by default. Turn on only when testing to your own inbox.
EMAIL_DELIVERY_ENABLED=false
# Verified Resend sender. onboarding@resend.dev is Resend's test sender.
EMAIL_FROM=onboarding@resend.dev
# The ONLY address real mail can go to. Use your own Resend account email.
EMAIL_TEST_RECIPIENT=you@example.com
# Resend API key. Never put this in the frontend or commit it.
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxx
```

Run migrations first (`alembic upgrade head`) so `008_email_tables` is applied,
then restart the backend.

## 5. Render configuration

In **Render → your service → Environment**, add:

```
EMAIL_DELIVERY_ENABLED   = false            # keep false until verified
EMAIL_FROM               = onboarding@resend.dev
EMAIL_TEST_RECIPIENT     = you@example.com
RESEND_API_KEY           = re_...           # Secret / sync:false
```

Mark `RESEND_API_KEY` as a secret. Changing environment variables **requires a
redeploy** of the backend service for the process to load them.

## 6. Safe testing (no real user is emailed)

- Keep `EMAIL_DELIVERY_ENABLED=false` until you are ready — the send endpoint
  returns `503 Email delivery is not configured.` and the UI shows
  "Sending requires an enabled email service and the configured test recipient."
- When enabled, **only** `EMAIL_TEST_RECIPIENT` can receive mail; every other
  address is rejected with `422 Use the configured test recipient.`
- Use `onboarding@resend.dev` as `EMAIL_FROM` and your **own** Resend account
  email as `EMAIL_TEST_RECIPIENT`. Resend restricts the test sender to your own
  account address.
- Verify config without sending: hit `GET /api/email/turns/{id}/drafts/{index}`
  and confirm `can_send: true` only appears for the configured recipient.
- Never log `RESEND_API_KEY` or authorization codes; the code does not print the
  key. Do not enable production sending automatically.
