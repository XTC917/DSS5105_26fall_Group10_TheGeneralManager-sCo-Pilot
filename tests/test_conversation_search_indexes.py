"""Database contract for indexed persisted-conversation search."""

from backend.services.pg_database import connect


EXPECTED_INDEXES = {
    "idx_copilot_conversations_title_trgm",
    "idx_copilot_chat_turns_question_trgm",
    "idx_copilot_chat_turns_answer_trgm",
}


def test_conversation_search_indexes_are_installed_without_long_term_memory():
    with connect(admin=True) as connection:
        extension = connection.execute(
            "SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'"
        ).fetchone()
        indexes = connection.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'copilot'
              AND indexname = ANY(%s)
            """,
            (list(EXPECTED_INDEXES),),
        ).fetchall()
        removed_table = connection.execute(
            "SELECT to_regclass('copilot.user_memories') AS table_name"
        ).fetchone()

    assert extension is not None
    assert {row["indexname"] for row in indexes} == EXPECTED_INDEXES
    assert all("USING gin" in row["indexdef"] for row in indexes)
    assert removed_table["table_name"] is None
