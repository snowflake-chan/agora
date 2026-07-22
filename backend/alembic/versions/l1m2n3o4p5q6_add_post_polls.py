"""add native post polls

Revision ID: l1m2n3o4p5q6
Revises: k0l1m2n3o4p5
Create Date: 2026-07-21 10:30:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "l1m2n3o4p5q6"
down_revision: Union[str, Sequence[str], None] = "k0l1m2n3o4p5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create retry-safe storage for one poll per top-level post."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS post_poll (
            id UUID PRIMARY KEY,
            post_id UUID NOT NULL,
            question VARCHAR(160) NOT NULL,
            closes_at TIMESTAMP WITH TIME ZONE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            CONSTRAINT uq_post_poll_post UNIQUE (post_id),
            CONSTRAINT post_poll_post_id_fkey
                FOREIGN KEY (post_id) REFERENCES content(id) ON DELETE CASCADE,
            CONSTRAINT ck_post_poll_question_length
                CHECK (char_length(btrim(question)) BETWEEN 5 AND 160),
            CONSTRAINT ck_post_poll_closes_after_creation
                CHECK (closes_at > created_at)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS post_poll_option (
            id UUID PRIMARY KEY,
            poll_id UUID NOT NULL,
            text VARCHAR(80) NOT NULL,
            normalized_digest VARCHAR(64) NOT NULL,
            position SMALLINT NOT NULL,
            CONSTRAINT post_poll_option_poll_id_fkey
                FOREIGN KEY (poll_id) REFERENCES post_poll(id) ON DELETE CASCADE,
            CONSTRAINT uq_post_poll_option_digest
                UNIQUE (poll_id, normalized_digest),
            CONSTRAINT uq_post_poll_option_poll_id_id UNIQUE (poll_id, id),
            CONSTRAINT uq_post_poll_option_position UNIQUE (poll_id, position),
            CONSTRAINT ck_post_poll_option_text_length
                CHECK (char_length(btrim(text)) BETWEEN 1 AND 80),
            CONSTRAINT ck_post_poll_option_position CHECK (position BETWEEN 0 AND 5)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS post_poll_vote (
            id UUID PRIMARY KEY,
            poll_id UUID NOT NULL,
            option_id UUID NOT NULL,
            user_id UUID NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
            CONSTRAINT post_poll_vote_poll_id_fkey
                FOREIGN KEY (poll_id) REFERENCES post_poll(id) ON DELETE CASCADE,
            CONSTRAINT post_poll_vote_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES "user"(id) ON DELETE CASCADE,
            CONSTRAINT fk_post_poll_vote_option
                FOREIGN KEY (poll_id, option_id)
                REFERENCES post_poll_option(poll_id, id) ON DELETE CASCADE,
            CONSTRAINT uq_post_poll_vote_poll_user UNIQUE (poll_id, user_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_post_poll_post_id ON post_poll (post_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_post_poll_option_poll_id "
        "ON post_poll_option (poll_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_post_poll_vote_poll_id "
        "ON post_poll_vote (poll_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_post_poll_vote_option_id "
        "ON post_poll_vote (option_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_post_poll_vote_user_id "
        "ON post_poll_vote (user_id)"
    )

    # A poll is only valid on a root post; a normal FK cannot express this.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION ensure_post_poll_target()
        RETURNS trigger AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM content
                WHERE id = NEW.post_id
                  AND type = 'post'
                  AND parent_id IS NULL
            ) THEN
                RAISE EXCEPTION 'post polls require a top-level post'
                    USING ERRCODE = 'foreign_key_violation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_ensure_post_poll_target ON post_poll")
    op.execute(
        """
        CREATE TRIGGER trg_ensure_post_poll_target
        BEFORE INSERT OR UPDATE OF post_id ON post_poll
        FOR EACH ROW EXECUTE FUNCTION ensure_post_poll_target()
        """
    )

    # Keep the database invariant at two through six choices even for direct SQL.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_post_poll_option_count()
        RETURNS trigger AS $$
        DECLARE target_poll_id UUID;
        DECLARE option_count INTEGER;
        BEGIN
            IF TG_TABLE_NAME = 'post_poll' THEN
                target_poll_id := NEW.id;
            ELSIF TG_OP = 'DELETE' THEN
                target_poll_id := OLD.poll_id;
            ELSIF TG_OP = 'UPDATE' AND OLD.poll_id IS DISTINCT FROM NEW.poll_id THEN
                IF EXISTS (SELECT 1 FROM post_poll WHERE id = OLD.poll_id) THEN
                    SELECT count(*) INTO option_count
                    FROM post_poll_option
                    WHERE poll_id = OLD.poll_id;
                    IF option_count < 2 OR option_count > 6 THEN
                        RAISE EXCEPTION 'post polls require two to six options'
                            USING ERRCODE = 'check_violation';
                    END IF;
                END IF;
                target_poll_id := NEW.poll_id;
            ELSE
                target_poll_id := NEW.poll_id;
            END IF;

            IF NOT EXISTS (SELECT 1 FROM post_poll WHERE id = target_poll_id) THEN
                RETURN NULL;
            END IF;

            SELECT count(*) INTO option_count
            FROM post_poll_option
            WHERE poll_id = target_poll_id;

            IF option_count < 2 OR option_count > 6 THEN
                RAISE EXCEPTION 'post polls require two to six options'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS ck_post_poll_option_count_poll ON post_poll"
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER ck_post_poll_option_count_poll
        AFTER INSERT OR UPDATE ON post_poll
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION validate_post_poll_option_count()
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS ck_post_poll_option_count_option "
        "ON post_poll_option"
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER ck_post_poll_option_count_option
        AFTER INSERT OR UPDATE OR DELETE ON post_poll_option
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION validate_post_poll_option_count()
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS post_poll_vote")
    op.execute("DROP TABLE IF EXISTS post_poll_option")
    op.execute("DROP TABLE IF EXISTS post_poll")
    op.execute("DROP FUNCTION IF EXISTS validate_post_poll_option_count()")
    op.execute("DROP FUNCTION IF EXISTS ensure_post_poll_target()")
