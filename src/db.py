"""
EQD-AI SQLite persistence layer.

Single file: schema creation + repository classes.
Raw sqlite3 + Pydantic — no ORM (per best practices guide).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, List, Optional

from src.models import (
    Category,
    CategoryTheme,
    DecisionLog,
    Document,
    InitialCode,
    ICStatus,
    QualityMetric,
    Segment,
    Theme,
    ThemeIC,
    VerbatimQuote,
)

# ── Schema ────────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS documents (
    id              TEXT PRIMARY KEY,
    source_file     TEXT,
    raw_text        TEXT NOT NULL,
    metadata        TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS segments (
    id                  TEXT PRIMARY KEY,
    document_id         TEXT NOT NULL,
    canonical_text      TEXT NOT NULL,
    original_text       TEXT NOT NULL,
    char_count          INTEGER NOT NULL,
    segment_index       INTEGER NOT NULL DEFAULT 0,
    normalization_rules TEXT NOT NULL DEFAULT '[]',
    content_hash        TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

CREATE TABLE IF NOT EXISTS initial_codes (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    definition      TEXT NOT NULL,
    embedding_json  TEXT,
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS verbatim_quotes (
    id                      TEXT PRIMARY KEY,
    ic_id                   TEXT NOT NULL,
    segment_id              TEXT NOT NULL,
    quote_text              TEXT NOT NULL,
    span_start              INTEGER NOT NULL,
    span_end                INTEGER NOT NULL,
    is_verified             INTEGER NOT NULL DEFAULT 0,
    quote_embedding_json    TEXT,
    FOREIGN KEY (ic_id) REFERENCES initial_codes(id),
    FOREIGN KEY (segment_id) REFERENCES segments(id)
);

CREATE TABLE IF NOT EXISTS themes (
    id                TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    definition        TEXT NOT NULL,
    rationale         TEXT NOT NULL DEFAULT '',
    round_finalised   INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS theme_ics (
    theme_id    TEXT NOT NULL,
    ic_id       TEXT NOT NULL,
    assigned_at TEXT NOT NULL,
    PRIMARY KEY (theme_id, ic_id),
    FOREIGN KEY (theme_id) REFERENCES themes(id),
    FOREIGN KEY (ic_id) REFERENCES initial_codes(id)
);

CREATE TABLE IF NOT EXISTS decision_logs (
    id                  TEXT PRIMARY KEY,
    decision_type       TEXT NOT NULL,
    ic_id               TEXT,
    llm_recommendation  TEXT,
    human_action        TEXT,
    similarity_score    REAL,
    timestamp           TEXT NOT NULL,
    notes               TEXT,
    context             TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS quality_metrics (
    id          TEXT PRIMARY KEY,
    metric_type TEXT NOT NULL,
    entity_id   TEXT,
    entity_type TEXT,
    value       REAL NOT NULL,
    computed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    definition      TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS category_themes (
    category_id TEXT NOT NULL,
    theme_id    TEXT NOT NULL,
    assigned_at TEXT NOT NULL,
    PRIMARY KEY (category_id, theme_id),
    FOREIGN KEY (category_id) REFERENCES categories(id),
    FOREIGN KEY (theme_id) REFERENCES themes(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_segments_document       ON segments(document_id);
CREATE INDEX IF NOT EXISTS idx_quotes_ic               ON verbatim_quotes(ic_id);
CREATE INDEX IF NOT EXISTS idx_quotes_segment          ON verbatim_quotes(segment_id);
CREATE INDEX IF NOT EXISTS idx_theme_ics_theme         ON theme_ics(theme_id);
CREATE INDEX IF NOT EXISTS idx_theme_ics_ic            ON theme_ics(ic_id);
CREATE INDEX IF NOT EXISTS idx_decisions_timestamp     ON decision_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_metrics_type            ON quality_metrics(metric_type);
CREATE INDEX IF NOT EXISTS idx_category_themes_cat     ON category_themes(category_id);
CREATE INDEX IF NOT EXISTS idx_category_themes_theme   ON category_themes(theme_id);
"""


# ── Database connection ───────────────────────────────────────────────────────

class Database:
    """SQLite connection manager.

    For file-based databases: opens/closes a connection per operation.
    For :memory: databases: keeps a single persistent connection
    (each sqlite3.connect(":memory:") creates a separate database).
    """

    def __init__(self, db_path: str | Path = "eqa_ai.db"):
        self.db_path = str(db_path)
        self._is_memory = self.db_path == ":memory:"
        self._persistent_conn: Optional[sqlite3.Connection] = None

    def init_schema(self) -> None:
        """Create all tables. Safe to call multiple times (IF NOT EXISTS)."""
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        if self._is_memory:
            # Reuse a single connection for in-memory databases
            if self._persistent_conn is None:
                self._persistent_conn = sqlite3.connect(":memory:", timeout=30)
                self._persistent_conn.row_factory = sqlite3.Row
                self._persistent_conn.execute("PRAGMA foreign_keys = ON")
            try:
                yield self._persistent_conn
                self._persistent_conn.commit()
            except Exception:
                self._persistent_conn.rollback()
                raise
        else:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def close(self) -> None:
        """Close the persistent connection (for in-memory databases)."""
        if self._persistent_conn is not None:
            self._persistent_conn.close()
            self._persistent_conn = None


# ── Repositories ──────────────────────────────────────────────────────────────

class DocumentRepo:
    def __init__(self, db: Database):
        self.db = db

    def insert(self, doc: Document) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO documents (id, source_file, raw_text, metadata, created_at) VALUES (?,?,?,?,?)",
                (doc.id, doc.source_file, doc.raw_text,
                 json.dumps(doc.metadata), doc.created_at.isoformat()),
            )

    def get_by_id(self, doc_id: str) -> Optional[Document]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not row:
            return None
        return Document(
            id=row["id"], source_file=row["source_file"], raw_text=row["raw_text"],
            metadata=json.loads(row["metadata"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def get_all(self) -> List[Document]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM documents ORDER BY created_at").fetchall()
        return [
            Document(id=r["id"], source_file=r["source_file"], raw_text=r["raw_text"],
                     metadata=json.loads(r["metadata"]),
                     created_at=datetime.fromisoformat(r["created_at"]))
            for r in rows
        ]


class SegmentRepo:
    def __init__(self, db: Database):
        self.db = db

    def insert(self, seg: Segment) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO segments
                   (id, document_id, canonical_text, original_text, char_count,
                    segment_index, normalization_rules, content_hash, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (seg.id, seg.document_id, seg.canonical_text, seg.original_text,
                 seg.char_count, seg.segment_index,
                 json.dumps(seg.normalization_rules), seg.content_hash,
                 seg.created_at.isoformat()),
            )

    def get_by_id(self, seg_id: str) -> Optional[Segment]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM segments WHERE id=?", (seg_id,)).fetchone()
        if not row:
            return None
        return self._row_to_segment(row)

    def get_all_for_document(self, document_id: str) -> List[Segment]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM segments WHERE document_id=? ORDER BY segment_index",
                (document_id,),
            ).fetchall()
        return [self._row_to_segment(r) for r in rows]

    def get_canonical_text(self, segment_id: str) -> Optional[str]:
        """Fast lookup for grounding verification."""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT canonical_text FROM segments WHERE id=?", (segment_id,)
            ).fetchone()
        return row["canonical_text"] if row else None

    @staticmethod
    def _row_to_segment(row: sqlite3.Row) -> Segment:
        return Segment(
            id=row["id"], document_id=row["document_id"],
            canonical_text=row["canonical_text"], original_text=row["original_text"],
            char_count=row["char_count"], segment_index=row["segment_index"],
            normalization_rules=json.loads(row["normalization_rules"]),
            content_hash=row["content_hash"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class InitialCodeRepo:
    def __init__(self, db: Database):
        self.db = db

    def insert(self, ic: InitialCode) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO initial_codes
                   (id, name, definition, embedding_json, status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (ic.id, ic.name, ic.definition,
                 json.dumps(ic.embedding_json) if ic.embedding_json else None,
                 ic.status.value, ic.created_at.isoformat(), ic.updated_at.isoformat()),
            )

    def update(self, ic: InitialCode) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """UPDATE initial_codes
                   SET name=?, definition=?, embedding_json=?, status=?, updated_at=?
                   WHERE id=?""",
                (ic.name, ic.definition,
                 json.dumps(ic.embedding_json) if ic.embedding_json else None,
                 ic.status.value, datetime.utcnow().isoformat(), ic.id),
            )

    def get_by_id(self, ic_id: str) -> Optional[InitialCode]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM initial_codes WHERE id=?", (ic_id,)).fetchone()
        if not row:
            return None
        return self._row_to_ic(row)

    def get_all_active(self) -> List[InitialCode]:
        """Return the current codebook (active codes only)."""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM initial_codes WHERE status='active' ORDER BY created_at"
            ).fetchall()
        return [self._row_to_ic(r) for r in rows]

    def get_by_name(self, name: str) -> Optional[InitialCode]:
        """Look up an active IC by its exact name."""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM initial_codes WHERE name=? AND status='active'",
                (name,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_ic(row)

    def count_active(self) -> int:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM initial_codes WHERE status='active'"
            ).fetchone()
        return row["cnt"]

    @staticmethod
    def _row_to_ic(row: sqlite3.Row) -> InitialCode:
        emb = json.loads(row["embedding_json"]) if row["embedding_json"] else None
        return InitialCode(
            id=row["id"], name=row["name"], definition=row["definition"],
            embedding_json=emb, status=ICStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


class VerbatimQuoteRepo:
    def __init__(self, db: Database):
        self.db = db

    def insert(self, vq: VerbatimQuote) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO verbatim_quotes
                   (id, ic_id, segment_id, quote_text, span_start, span_end,
                    is_verified, quote_embedding_json)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (vq.id, vq.ic_id, vq.segment_id, vq.quote_text,
                 vq.span_start, vq.span_end, int(vq.is_verified),
                 json.dumps(vq.quote_embedding_json) if vq.quote_embedding_json else None),
            )

    def get_all_for_ic(self, ic_id: str) -> List[VerbatimQuote]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM verbatim_quotes WHERE ic_id=?", (ic_id,)
            ).fetchall()
        return [self._row_to_vq(r) for r in rows]

    def get_all_for_segment(self, segment_id: str) -> List[VerbatimQuote]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM verbatim_quotes WHERE segment_id=?", (segment_id,)
            ).fetchall()
        return [self._row_to_vq(r) for r in rows]

    def update_embedding(self, vq: VerbatimQuote) -> None:
        """Update only the embedding for an already-inserted quote (deferred embed)."""
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE verbatim_quotes SET quote_embedding_json=? WHERE id=?",
                (json.dumps(vq.quote_embedding_json) if vq.quote_embedding_json else None,
                 vq.id),
            )

    @staticmethod
    def _row_to_vq(row: sqlite3.Row) -> VerbatimQuote:
        emb = json.loads(row["quote_embedding_json"]) if row["quote_embedding_json"] else None
        return VerbatimQuote(
            id=row["id"], ic_id=row["ic_id"], segment_id=row["segment_id"],
            quote_text=row["quote_text"], span_start=row["span_start"],
            span_end=row["span_end"], is_verified=bool(row["is_verified"]),
            quote_embedding_json=emb,
        )


class ThemeRepo:
    def __init__(self, db: Database):
        self.db = db

    def insert(self, theme: Theme) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO themes (id, name, definition, rationale, round_finalised, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (theme.id, theme.name, theme.definition, theme.rationale,
                 theme.round_finalised, theme.created_at.isoformat()),
            )

    def assign_ic(self, tic: ThemeIC) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO theme_ics (theme_id, ic_id, assigned_at) VALUES (?,?,?)",
                (tic.theme_id, tic.ic_id, tic.assigned_at.isoformat()),
            )

    def get_latest_round(self) -> tuple[List[Theme], int]:
        """Return all themes from the latest synthesis round, plus the round number.

        Returns: (themes, round_number).  If no themes exist, returns ([], 0).
        """
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT MAX(round_finalised) AS mr FROM themes"
            ).fetchone()
            max_round = row["mr"] if row and row["mr"] is not None else 0

            if max_round == 0:
                rows = conn.execute(
                    "SELECT * FROM themes ORDER BY created_at"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM themes WHERE round_finalised = ? ORDER BY created_at",
                    (max_round,),
                ).fetchall()

        themes = [
            Theme(
                id=r["id"],
                name=r["name"],
                definition=r["definition"],
                rationale=r["rationale"],
                round_finalised=r["round_finalised"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]
        return themes, max_round

    def get_ics_for_theme(self, theme_id: str) -> List[str]:
        """Return list of IC IDs assigned to a theme."""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT ic_id FROM theme_ics WHERE theme_id=?", (theme_id,)
            ).fetchall()
        return [r["ic_id"] for r in rows]

    def dissolve_theme(self, theme_id: str) -> int:
        """Remove all IC-theme assignments. Theme record stays, ICs remain active."""
        with self.db.connect() as conn:
            cursor = conn.execute(
                "DELETE FROM theme_ics WHERE theme_id=?", (theme_id,)
            )
            return cursor.rowcount


class DecisionLogRepo:
    def __init__(self, db: Database):
        self.db = db

    def insert(self, log: DecisionLog) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO decision_logs
                   (id, decision_type, ic_id, llm_recommendation, human_action,
                    similarity_score, timestamp, notes, context)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (log.id, log.decision_type.value, log.ic_id,
                 log.llm_recommendation, log.human_action,
                 log.similarity_score, log.timestamp.isoformat(),
                 log.notes, json.dumps(log.context)),
            )

    def get_all(self) -> List[DecisionLog]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM decision_logs ORDER BY timestamp"
            ).fetchall()
        return [
            DecisionLog(
                id=r["id"], decision_type=r["decision_type"], ic_id=r["ic_id"],
                llm_recommendation=r["llm_recommendation"],
                human_action=r["human_action"],
                similarity_score=r["similarity_score"],
                timestamp=datetime.fromisoformat(r["timestamp"]),
                notes=r["notes"], context=json.loads(r["context"]),
            )
            for r in rows
        ]


class QualityMetricRepo:
    def __init__(self, db: Database):
        self.db = db

    def insert(self, qm: QualityMetric) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO quality_metrics
                   (id, metric_type, entity_id, entity_type, value, computed_at)
                   VALUES (?,?,?,?,?,?)""",
                (qm.id, qm.metric_type.value, qm.entity_id, qm.entity_type,
                 qm.value, qm.computed_at.isoformat()),
            )

    def get_by_type(self, metric_type: str) -> List[QualityMetric]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM quality_metrics WHERE metric_type=? ORDER BY computed_at",
                (metric_type,),
            ).fetchall()
        return [
            QualityMetric(
                id=r["id"], metric_type=r["metric_type"],
                entity_id=r["entity_id"], entity_type=r["entity_type"],
                value=r["value"],
                computed_at=datetime.fromisoformat(r["computed_at"]),
            )
            for r in rows
        ]


class CategoryRepo:
    """Repository for categories and category-theme assignments."""

    def __init__(self, db: Database):
        self.db = db

    def insert(self, category: Category) -> None:
        """Insert a new category."""
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO categories (id, name, definition, created_at)
                   VALUES (?,?,?,?)""",
                (category.id, category.name, category.definition,
                 category.created_at.isoformat()),
            )

    def assign_theme(self, ct: CategoryTheme) -> None:
        """Assign a theme to a category (junction table)."""
        with self.db.connect() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO category_themes
                   (category_id, theme_id, assigned_at)
                   VALUES (?,?,?)""",
                (ct.category_id, ct.theme_id, ct.assigned_at.isoformat()),
            )

    def get_all(self) -> List[Category]:
        """Return all categories ordered by creation time."""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM categories ORDER BY created_at"
            ).fetchall()
        return [
            Category(
                id=r["id"],
                name=r["name"],
                definition=r["definition"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]

    def get_themes_for_category(self, category_id: str) -> List[str]:
        """Return list of theme IDs assigned to a category."""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT theme_id FROM category_themes WHERE category_id=?",
                (category_id,),
            ).fetchall()
        return [r["theme_id"] for r in rows]

    def get_category_for_theme(self, theme_id: str) -> Optional[str]:
        """Return category_id for a theme, or None if unassigned."""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT category_id FROM category_themes WHERE theme_id=?",
                (theme_id,),
            ).fetchone()
        return row["category_id"] if row else None
