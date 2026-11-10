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
| `EMAIL_TEST_RECIPIENT` | Read by `_delivery_config()` but **not currently enforced**. See the safety note below. | No (read only) |
| `RESEND_API_KEY` | Resend API key (`re_...`). | Yes |

There is **no** SMTP host/port/user/password, no sender-name variable and no
TLS/SSL toggle — delivery is HTTP to `https://api.resend.com/emails`.

`_delivery_config()` enables delivery only when `EMAIL_DELIVERY_ENABLED=true`
**and** `EMAIL_FROM` **and** `RESEND_API_KEY` are set. `EMAIL_TEST_RECIPIENT`
is **not** required and is **not** used as an allow-list.

> **Safety note (current main behaviour).** The recipient is whatever single
> valid email address the manager enters on the draft card (commit “Send drafts
> to the address entered on the card”). `EMAIL_TEST_RECIPIENT` is read but not
> compared against the draft. Before enabling real delivery, confirm every
> person using the app understands that enabling the switch lets the app email
> **any address typed into the draft**, not only a test inbox. If you need a
> hard allow-list, that is a code change (not currently implemented).

## 4. Local `.env` template (copy, fill placeholders, never commit)

```dotenv
# Off by default. Turn on only when testing to your own inbox.
EMAIL_DELIVERY_ENABLED=false
# Verified Resend sender. onboarding@resend.dev is Resend's test sender.
EMAIL_FROM=onboarding@resend.dev
# Informational only; NOT an allow-list today. Use your own inbox while testing.
EMAIL_TEST_RECIPIENT=you@example.com
# Resend API key. Never put this in the frontend or commit it.
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxx
```

Run migrations first (`alembic upgrade head`) so `008_email_tables` is applied,
then restart the backend.

## 5. Render configuration

`render.yaml` intentionally does **not** declare any email variables, so they
must be added by hand and are never committed.

In **Render → your service → Environment**, add:

```
EMAIL_DELIVERY_ENABLED   = false            # keep false until verified
EMAIL_FROM               = onboarding@resend.dev
EMAIL_TEST_RECIPIENT     = you@example.com  # informational only (not enforced)
RESEND_API_KEY           = re_...           # Secret / sync:false
```

Mark `RESEND_API_KEY` as a secret. Changing environment variables **requires a
redeploy** of the backend service for the process to load them.

### Where to verify without sending

- `GET /openapi.json` (via the Vercel rewrite or the Render host) must list
  `POST /api/email/drafts/{draft_id}/send` and `GET/PUT
  /api/email/turns/{turn_id}/drafts/{index}`.
- `GET /api/email/turns/{turn_id}/drafts/{index}` on an owned turn returns
  `can_send: false` while delivery is disabled (or when `EMAIL_FROM` does not
  match the saved `from_address`). No provider call happens on a GET.
- Do **not** press “Confirm and send” to test; with the switch off it returns
  `503 Email delivery is not configured.` and must not be used as a probe in
  production.

### Enable real delivery only after

1. `RESEND_API_KEY` is a real key owned by the team, stored as a Render secret.
2. `EMAIL_FROM` is a Resend-verified sender (or the Resend test sender
   `onboarding@resend.dev`, which can only deliver to the account owner).
3. Everyone understands the recipient is the address typed on the draft.
4. The `email_drafts` / `email_send_attempts` migration (`008_email_tables`)
   is applied to the target database.
5. Someone is available to watch the first send and confirm the Resend log.

## 6. Safe testing (no real user is emailed)

- Keep `EMAIL_DELIVERY_ENABLED=false` until you are ready — the send endpoint
  returns `503 Email delivery is not configured.` and the UI shows
  "Sending requires an enabled email service and one recipient address."
- When enabled, the draft can be sent to its saved recipient as long as it is
  one valid address (`MAILBOX.fullmatch`). There is **no** allow-list today.
- Use `onboarding@resend.dev` as `EMAIL_FROM` and your **own** Resend account
  email as the recipient while testing. Resend restricts the test sender to
  your own account address.
- Verify config without sending: hit `GET /api/email/turns/{id}/drafts/{index}`
  and confirm `can_send: true` only appears for the configured recipient.
- Never log `RESEND_API_KEY` or authorization codes; the code does not print the
  key. Do not enable production sending automatically.
