"""Хранение колод, карточек и истории повторений в SQLite."""
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from . import scheduler

MAX_DECK_NAME = 60
MAX_CARD_TEXT = 500

SCHEMA = """
CREATE TABLE IF NOT EXISTS decks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    front TEXT NOT NULL,
    back TEXT NOT NULL,
    box INTEGER NOT NULL DEFAULT 1 CHECK (box BETWEEN 1 AND 5),
    due TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (deck_id, front)
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    reviewed_on TEXT NOT NULL,
    correct INTEGER NOT NULL CHECK (correct IN (0, 1)),
    box_before INTEGER NOT NULL,
    box_after INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cards_due ON cards (due);
CREATE INDEX IF NOT EXISTS idx_reviews_day ON reviews (reviewed_on);
"""


class ValidationError(ValueError):
    """Неверные данные, введённые пользователем."""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_text(value, field, limit):
    """Убирает пробелы по краям и проверяет, что текст не пустой и не длинный."""
    text = (value or "").strip()
    if not text:
        raise ValidationError(f"Поле «{field}» не может быть пустым")
    if len(text) > limit:
        raise ValidationError(f"Поле «{field}» длиннее {limit} символов")
    return text


class Storage:
    """Обёртка над файлом базы: все SQL-запросы приложения собраны здесь."""

    def __init__(self, path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)

    def close(self):
        self.conn.close()

    # ---------- колоды ----------

    def add_deck(self, name):
        name = clean_text(name, "Название колоды", MAX_DECK_NAME)
        try:
            with self.conn:
                cur = self.conn.execute(
                    "INSERT INTO decks (name, created_at) VALUES (?, ?)", (name, _now())
                )
        except sqlite3.IntegrityError:
            raise ValidationError(f"Колода «{name}» уже существует") from None
        return cur.lastrowid

    def rename_deck(self, deck_id, name):
        name = clean_text(name, "Название колоды", MAX_DECK_NAME)
        try:
            with self.conn:
                self.conn.execute("UPDATE decks SET name = ? WHERE id = ?", (name, deck_id))
        except sqlite3.IntegrityError:
            raise ValidationError(f"Колода «{name}» уже существует") from None

    def delete_deck(self, deck_id):
        # Карточки и история удаляются каскадно (ON DELETE CASCADE).
        with self.conn:
            self.conn.execute("DELETE FROM decks WHERE id = ?", (deck_id,))

    def list_decks(self, today):
        rows = self.conn.execute(
            """
            SELECT d.id, d.name,
                   COUNT(c.id) AS total,
                   COALESCE(SUM(c.due <= ?), 0) AS due,
                   COALESCE(SUM(c.box = ?), 0) AS learned
            FROM decks d LEFT JOIN cards c ON c.deck_id = d.id
            GROUP BY d.id
            """,
            (today.isoformat(), scheduler.MAX_BOX),
        ).fetchall()
        return sorted((dict(r) for r in rows), key=lambda d: d["name"].casefold())

    def get_deck_id(self, name):
        row = self.conn.execute("SELECT id FROM decks WHERE name = ?", (name,)).fetchone()
        return row["id"] if row else None

    # ---------- карточки ----------

    def add_card(self, deck_id, front, back, today):
        front = clean_text(front, "Вопрос", MAX_CARD_TEXT)
        back = clean_text(back, "Ответ", MAX_CARD_TEXT)
        try:
            with self.conn:
                cur = self.conn.execute(
                    "INSERT INTO cards (deck_id, front, back, box, due, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (deck_id, front, back, scheduler.MIN_BOX, today.isoformat(), _now()),
                )
        except sqlite3.IntegrityError as error:
            if "UNIQUE" in str(error):
                raise ValidationError("В колоде уже есть карточка с таким вопросом") from None
            raise ValidationError("Колода не найдена") from None
        return cur.lastrowid

    def update_card(self, card_id, front, back):
        front = clean_text(front, "Вопрос", MAX_CARD_TEXT)
        back = clean_text(back, "Ответ", MAX_CARD_TEXT)
        try:
            with self.conn:
                self.conn.execute(
                    "UPDATE cards SET front = ?, back = ? WHERE id = ?", (front, back, card_id)
                )
        except sqlite3.IntegrityError:
            raise ValidationError("В колоде уже есть карточка с таким вопросом") from None

    def delete_card(self, card_id):
        with self.conn:
            self.conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))

    def get_card(self, card_id):
        row = self.conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        return dict(row) if row else None

    def list_cards(self, deck_id, search=""):
        rows = self.conn.execute("SELECT * FROM cards WHERE deck_id = ? ORDER BY id", (deck_id,))
        cards = [dict(r) for r in rows]
        needle = search.strip().casefold()
        if needle:
            # Поиск в Python: LOWER() в SQLite не понимает кириллицу.
            cards = [c for c in cards if needle in c["front"].casefold() or needle in c["back"].casefold()]
        return cards

    def due_cards(self, today, deck_id=None):
        """Карточки, срок повторения которых наступил: сначала самые просроченные."""
        query = (
            "SELECT c.*, d.name AS deck_name FROM cards c JOIN decks d ON d.id = c.deck_id"
            " WHERE c.due <= ?"
        )
        params = [today.isoformat()]
        if deck_id is not None:
            query += " AND c.deck_id = ?"
            params.append(deck_id)
        query += " ORDER BY c.due, c.box, c.id"
        return [dict(r) for r in self.conn.execute(query, params)]

    # ---------- повторения ----------

    def record_review(self, card_id, correct, today):
        """Сохраняет ответ и переносит карточку в новую ячейку."""
        card = self.get_card(card_id)
        if card is None:
            raise ValidationError("Карточка не найдена")
        new_box, due = scheduler.next_state(card["box"], correct, today)
        with self.conn:
            self.conn.execute(
                "UPDATE cards SET box = ?, due = ? WHERE id = ?",
                (new_box, due.isoformat(), card_id),
            )
            self.conn.execute(
                "INSERT INTO reviews (card_id, reviewed_on, correct, box_before, box_after)"
                " VALUES (?, ?, ?, ?, ?)",
                (card_id, today.isoformat(), int(bool(correct)), card["box"], new_box),
            )
        return new_box, due

    def reviews_since(self, start):
        rows = self.conn.execute(
            "SELECT reviewed_on, correct FROM reviews WHERE reviewed_on >= ?",
            (start.isoformat(),),
        )
        return [(date.fromisoformat(r["reviewed_on"]), bool(r["correct"])) for r in rows]

    def review_days(self):
        rows = self.conn.execute("SELECT DISTINCT reviewed_on FROM reviews")
        return {date.fromisoformat(r["reviewed_on"]) for r in rows}

    def card_states(self):
        rows = self.conn.execute("SELECT box, due FROM cards")
        return [(r["box"], date.fromisoformat(r["due"])) for r in rows]
