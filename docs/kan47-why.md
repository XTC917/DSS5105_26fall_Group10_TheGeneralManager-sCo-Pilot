# KAN-47: explanation and live progress

This branch is based directly on `main`. Its changes are limited to the Why panel, optional model summaries, and streaming execution progress. It does not include KAN-35's conversation-history routes, conversation list, database migrations or PostgreSQL checkpoint store. The original KAN-35 implementation remains on its own branch.

## Why

Answers include four steps: the question, returned source facts, tool calculations/comparisons, and the reason for the conclusion. Explanations use deterministic tool output without another model call or changes to business calculations. Source records expand into a readable table. Missing evidence, ambiguity and limitations are stated explicitly; raw debug JSON and code locations are not rendered.

An explicitly routed follow-up can reuse source evidence from an earlier tool result in the same in-memory session. The panel labels this reuse and does not claim a new lookup. It never copies old model summaries or action proposals; a failed latest lookup prevents falling back to stale evidence.

## Optional model summary

The existing OpenAI Responses client accepts `OPENAI_REASONING_SUMMARY=auto` on a supported model. Leave it empty by default. Only provider `summary_text` blocks from the final answer message are extracted; intermediate tool-call planning, raw reasoning, signatures and encrypted content are excluded. Gemini ignores this setting. The example uses the tested model identifier `gpt-5.6-sol`; verify access with your account.

A live fictional scheduling probe verified the API and existing client parser. A simple probe returned no summary, which is a valid outcome. Real tool-call summaries included chart/tool planning, so summaries remain optional and off by default. Evidence from the tools is the default explanation.

Official reference: https://developers.openai.com/api/docs/guides/reasoning

## HTTP and streaming

Both `POST /api/chat` and `POST /api/chat/stream` require the existing bearer authentication. They retain the main branch's string `conversation_id` contract; no server-created conversation or history table is required. In-memory agent sessions are namespaced by authenticated user, and the public response retains the client conversation ID.

The streaming route emits:

- `progress`: readable tool-execution stages, without arguments, prompts or raw output.
- `done`: the complete response after schema validation.
- `error`: a public error; a failed run or invalid response never emits success.

Idle streams send keep-alive comments. The client handles arbitrary SSE boundaries and split UTF-8 characters, and never retries tools automatically on disconnect. It streams progress rather than answer tokens. Existing action confirmation remains a separate UI step.

Session context uses main's `MemorySaver`. It is not persistent history: refreshing the page starts a new UI session, and a backend restart clears in-memory context. No KAN-35 migration, dependency or database table is needed. Existing KAN-35 database data is not deleted by this branch.

## Validation of the independent branch

A fresh local `kan47_only_test` database was migrated using only main's `001_initial_auth` and `002_auth_deactivation` migrations and seeded with the course dataset. Checks verified that no conversations, chat turns or LangGraph checkpoint tables exist, and `/api/conversations` returns 404.

- 29 focused backend checks pass: Why/summary extraction, agent parsing, both chat transports, authentication, per-user session isolation, progress ordering, single invocation, errors and response validation. Agent doubles are used for regression tests.
- All 3 frontend transport/metadata tests pass; the production frontend build succeeds.
- The broader backend run, excluding the existing semantic-test collection error, ran 183 checks: 181 passed and two existing template tests failed. These expect templates before the main branch's required chart/table step. The template-prompt function is unchanged. `test_semantic.py` still imports removed database constants. These unrelated baseline issues were left unchanged.

Standalone live verification with `gpt-5.6-sol` also passed: ORD-108 risk completed in 20.3 seconds (`trace_order`, `render_table`), followed by an explicit calculation question in 13.0 seconds with no new data-tool invocation and correctly labelled reused evidence. The test database had only migration `002_auth_deactivation` and no KAN-35 tables; the history endpoint returned 404. Results are recorded locally outside the repository in `work/kan47-only-live-results.json`.
