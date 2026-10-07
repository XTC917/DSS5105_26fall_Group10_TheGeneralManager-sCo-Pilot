# KAN-35: Manager conversation history

This change reuses the conversation-history work in LIU ZHENZE's
`feat/postgres-chat-memory` (`c504777`) without merging that branch's unrelated
factory calculations, routing rules or dataset edits. Coordinate with that
branch's author before merging either implementation. The shared migration
`004_conversation_history` and its table layout are preserved.

## Storage and ownership

`copilot.conversations` stores `id` (UUID), `user_id` (FK to `auth.users`),
`title`, `created_at`, and `updated_at`. An ownership/recency index supports
listing only the authenticated user's most recently updated conversations.

`copilot.chat_turns` stores `id`, `conversation_id` (cascading FK),
`turn_number`, `question`, `answer`, `response_json` (JSONB), and `created_at`.
The question and answer are the user and assistant messages of one successful
turn, stored atomically. Their roles are exposed explicitly by the messages
endpoint. A second `conversation_messages` table is intentionally not created:
it would duplicate the teammate's existing store. `(conversation_id,
turn_number)` is unique; a conversation row lock serializes turn numbering.

The backend derives ownership from the existing bearer-token authentication
and checks it before agent execution, history reads, turn writes, and action
decisions. Missing and foreign-owned IDs both return 404. Client `user_id`
values cannot select an owner. SQL values are bound parameters. Factory
reader/agent database roles cannot read conversations or checkpoints; these
are accessed through the trusted backend identity, not agent SQL tools.

Metadata includes tools, evidence, limitations, routing intent, proposals,
clarification cards, charts and tables. Confirmation/dismissal decisions are
stored so restored actions retain their existing decisions. Restored proposals
carry their persisted turn ID and are checked against that turn's owner.

## Migrations and startup

Install `requirements.txt`, configure the existing PostgreSQL/admin settings,
and run from the repository root:

```sh
alembic upgrade head
uvicorn backend.main:app --reload --port 8000
```

`004_conversation_history` follows `002_auth_deactivation` and installs the two
history tables, indexes, foreign keys and grants. `005_checkpoint_memory`
installs the pinned LangGraph PostgreSQL saver 3.1.2 schema/version ledger and
restricts its permissions. The four checkpoint tables are `checkpoints`,
`checkpoint_blobs`, `checkpoint_writes` and `checkpoint_migrations` in `copilot`.
Startup checks the schema and opens a checkpoint pool; it never calls `setup()`
or changes tables. Changing the saver version requires reviewing its schema
and adding a migration.

To roll back the feature in a disposable/development database:

```sh
alembic downgrade 002_auth_deactivation
```

This removes conversation/checkpoint data and tables, while preserving the
baseline schemas and users. Production migration/rollback deployment remains
a team responsibility; this task only migrates isolated local test databases.

## HTTP contracts

All history routes and `/api/chat` require authentication.

| Endpoint | Behavior |
| --- | --- |
| `POST /api/conversations` | Create a UUID conversation owned by the current user; 201 |
| `GET /api/conversations?limit=50` | List up to 50 owned conversations, newest first |
| `GET /api/conversations/{id}?limit=50&before_turn_id=...` | Owned chronological turn window and next cursor |
| `GET /api/conversations/{id}/messages?limit=50&before_turn_id=...` | Same owned window, flattened to `user`/`assistant` messages and assistant metadata |
| `POST /api/chat` | Run the existing agent, validate its response, save both messages and metadata, return the existing ChatResponse fields |

`conversation_id` is now a required server-created UUID, matching the teammate's
implementation. The old anonymous `default` and frontend `gm-{timestamp}` IDs
are no longer accepted. This change is necessary to require an owned,
persisted conversation before accessing agent memory. Existing API clients
must authenticate and create/select a conversation first. The returned ID is
stable across follow-up messages and restoration.

LangGraph thread IDs include both the authenticated user and conversation UUID
(`user:{id}:conversation:{uuid}`). PostgreSQL checkpoints preserve its original
tool/context messages across process restarts, and restored first follow-ups
read the existing checkpoint even before the cached agent is initialized.
An agent failure or invalid response is not saved as a successful turn.
Database failures return a generic 503 without exposing SQL/credentials.
Agent execution/checkpoints and the final history transaction are separate;
a history-write failure can leave an advanced checkpoint, even though no
successful UI/history turn is returned. Exactly-once retry across these stores
is outside this feature.

## Frontend restoration

The Manager page waits for authentication, lists owned conversations, selects
the most recent, and follows every history cursor before rendering. It reuses
the existing API/token/error helpers. With no history it creates an owned
conversation and shows the same empty chat UI. A failed fetch shows an error
and Retry; it does not silently create another conversation. Sending and
switching are blocked during restoration/current chat requests. The sidebar
can create or select conversations; it shows the latest 50 conversations.

History and live replies share the same message mapper and MessageBubble.
Switching away from the Manager view preserves the current messages. Changing
users remounts the Manager page, and canceled initial fetches cannot overwrite
the new user's view. Session expiration uses the existing logout event.

## Validation and manual acceptance

Backend integration tests require the existing PostgreSQL baseline, seed data,
and the existing test identities (ADMIN id 1, EMPLOYEE id 2). Use a dedicated
test database; existing fixtures clean test state and must not run on production.

```sh
pytest tests/test_conversation_history.py tests/test_api.py tests/test_auth.py
pytest
cd frontend
npm ci
npm test
npm run build
```

Manual acceptance with normal configured AI credentials:

1. Log in as User A and send `How is ORD-120 doing?`.
2. Check both messages, tools and evidence. Refresh and confirm they restore.
3. Close/reopen the page, log out/in as A, and check the same conversation.
4. Send a follow-up and check it appends to the same conversation UUID.
5. Switch to another view and back; the latest messages should remain visible.
6. Log out and log in as B. A's messages and conversations must be absent.
7. Authenticate as B and request A's history/messages ID or send to it: expect
   404 with no data and no agent execution. Without authentication expect 401.
8. For histories longer than 50 turns, confirm the oldest messages also restore.

Local browser acceptance uses real authentication, PostgreSQL and tools with a
clearly labeled deterministic AI test reply. It verifies persistence/UI flows,
not a live model's response quality. No real AI credentials are required or
created by these tests.
