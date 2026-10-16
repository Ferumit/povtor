"""Графический интерфейс на Tkinter: колоды, повторение и статистика."""
import sys
import tkinter as tk
from datetime import date, timedelta
from tkinter import filedialog, messagebox, ttk

from . import csv_io, scheduler, stats
from .db import ValidationError

COLORS = {
    "bg": "#F3F5F9",
    "surface": "#FFFFFF",
    "border": "#DCE1EA",
    "heading": "#EEF1F6",
    "text": "#1F2430",
    "muted": "#687082",
    "accent": "#3B6EF5",
    "accent_dark": "#2C57CC",
    "accent_soft": "#DDE6FD",
    "good": "#2E9D5B",
    "good_dark": "#237A46",
    "bad": "#D6493F",
    "bad_dark": "#B23A31",
    "grid": "#E6EAF2",
}
# Оттенки столбцов для ячеек 1–5: от светлого к насыщенному.
BOX_COLORS = ["#C9D7FC", "#A6BEFA", "#7FA1F8", "#5A86F6", "#3B6EF5"]
FONT = "Segoe UI"
ALL_DECKS = "Все колоды"


def enable_dpi_awareness():
    """Чёткий текст на экранах с масштабированием 125–200 % в Windows."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass


def fmt_date(day):
    return day.strftime("%d.%m.%Y")


def due_text(due, today):
    days = (due - today).days
    if days <= 0:
        return "сегодня"
    if days == 1:
        return "завтра"
    return fmt_date(due)


def plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def cards_word(n):
    return f"{n} {plural(n, 'карточка', 'карточки', 'карточек')}"


class App(tk.Tk):
    def __init__(self, storage, today=date.today):
        super().__init__()
        self.storage = storage
        self.today = today
        self.scale = self.winfo_fpixels("1i") / 96
        self.title("Повтор — тренажёр карточек")
        self.geometry(f"{self.px(1040)}x{self.px(680)}")
        self.minsize(self.px(860), self.px(580))
        self.configure(bg=COLORS["bg"])
        self._setup_style()
        self._build_header()

        self.notebook = ttk.Notebook(self)
        self.decks_tab = DecksTab(self.notebook, self)
        self.review_tab = ReviewTab(self.notebook, self)
        self.stats_tab = StatsTab(self.notebook, self)
        self.notebook.add(self.decks_tab, text="Колоды")
        self.notebook.add(self.review_tab, text="Повторение")
        self.notebook.add(self.stats_tab, text="Статистика")
        self.notebook.pack(fill="both", expand=True, padx=self.px(16), pady=(0, self.px(16)))
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.refresh())

        for key in ("<space>", "1", "2"):
            self.bind(key, self._on_key)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.refresh()

    def px(self, value):
        return int(round(value * self.scale))

    def _setup_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        c = COLORS
        base = (FONT, 10)
        style.configure(".", font=base, background=c["bg"], foreground=c["text"],
                        bordercolor=c["border"], focuscolor=c["accent"])
        style.configure("TFrame", background=c["bg"])
        style.configure("Surface.TFrame", background=c["surface"])
        style.configure("TLabel", background=c["bg"])
        style.configure("Surface.TLabel", background=c["surface"])
        style.configure("Muted.TLabel", background=c["surface"], foreground=c["muted"])
        style.configure("Title.TLabel", background=c["surface"], font=(FONT, 12, "bold"))
        style.configure("AppTitle.TLabel", font=(FONT, 18, "bold"))
        style.configure("AppSub.TLabel", foreground=c["muted"])

        pad = (self.px(10), self.px(6))
        style.configure("TButton", padding=pad, width=-8, background=c["surface"],
                        lightcolor=c["surface"], darkcolor=c["surface"], bordercolor=c["border"])
        style.map("TButton", background=[("active", c["heading"])],
                  foreground=[("disabled", "#A8AEBB")])
        for name, color, dark in (("Accent", "accent", "accent_dark"),
                                  ("Good", "good", "good_dark"),
                                  ("Bad", "bad", "bad_dark")):
            style.configure(f"{name}.TButton", background=c[color], foreground="white",
                            lightcolor=c[color], darkcolor=c[color], bordercolor=c[color],
                            font=(FONT, 10, "bold"), padding=pad)
            style.map(f"{name}.TButton", background=[("active", c[dark]), ("disabled", "#B9C3D6")],
                      lightcolor=[("active", c[dark])], darkcolor=[("active", c[dark])])

        style.configure("TNotebook", background=c["bg"], borderwidth=0, tabmargins=0)
        style.configure("TNotebook.Tab", padding=(self.px(18), self.px(7)), background=c["bg"],
                        lightcolor=c["bg"], bordercolor=c["border"], font=(FONT, 10))
        style.map("TNotebook.Tab", background=[("selected", c["surface"])],
                  lightcolor=[("selected", c["surface"])])

        style.configure("Treeview", rowheight=self.px(28), background=c["surface"],
                        fieldbackground=c["surface"], bordercolor=c["border"],
                        lightcolor=c["surface"], darkcolor=c["surface"])
        style.map("Treeview", background=[("selected", c["accent_soft"])],
                  foreground=[("selected", c["text"])])
        style.configure("Treeview.Heading", background=c["heading"], foreground=c["muted"],
                        font=(FONT, 9, "bold"), relief="flat", lightcolor=c["heading"],
                        darkcolor=c["heading"], bordercolor=c["border"],
                        padding=(self.px(6), self.px(4)))
        style.map("Treeview.Heading", background=[("active", c["heading"])])
        style.configure("TEntry", fieldbackground=c["surface"], lightcolor=c["surface"],
                        padding=self.px(5))
        style.configure("TCombobox", fieldbackground=c["surface"], lightcolor=c["surface"],
                        padding=self.px(4))
        style.map("TCombobox", fieldbackground=[("readonly", c["surface"])])

    def _build_header(self):
        header = ttk.Frame(self, padding=(self.px(18), self.px(12), self.px(18), self.px(10)))
        header.pack(fill="x")
        ttk.Label(header, text="Повтор", style="AppTitle.TLabel").pack(side="left")
        ttk.Label(header, text="интервальные повторения по системе Лейтнера",
                  style="AppSub.TLabel").pack(side="left", padx=(self.px(12), 0), pady=(self.px(6), 0))
        self.header_info = ttk.Label(header, style="AppSub.TLabel")
        self.header_info.pack(side="right", pady=(self.px(6), 0))

    def refresh(self):
        today = self.today()
        due = len(self.storage.due_cards(today))
        self.header_info.configure(text=f"Сегодня {fmt_date(today)} · к повторению: {cards_word(due)}")
        current = self.notebook.select()
        if current == str(self.decks_tab):
            self.decks_tab.refresh()
        elif current == str(self.review_tab):
            self.review_tab.refresh()
        else:
            self.stats_tab.refresh()

    def _on_key(self, event):
        # Горячие клавиши работают только на вкладке повторения и не мешают вводу текста.
        if self.notebook.select() != str(self.review_tab):
            return
        if isinstance(event.widget, (tk.Text, tk.Entry, ttk.Entry)):
            return
        self.review_tab.on_key(event.keysym)

    def _on_close(self):
        self.storage.close()
        self.destroy()


def panel(parent, app, **grid):
    """Белая панель с тонкой рамкой — основной «кирпичик» интерфейса."""
    frame = tk.Frame(parent, bg=COLORS["surface"], highlightthickness=1,
                     highlightbackground=COLORS["border"], highlightcolor=COLORS["border"])
    inner = ttk.Frame(frame, style="Surface.TFrame", padding=app.px(14))
    inner.pack(fill="both", expand=True)
    return frame, inner


class FormDialog(tk.Toplevel):
    """Окно с полями ввода. on_save получает значения и может бросить ValidationError."""

    def __init__(self, app, title, fields, on_save):
        super().__init__(app)
        self.app = app
        self.on_save = on_save
        self.title(title)
        self.transient(app)
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])
        body = ttk.Frame(self, padding=app.px(16))
        body.pack(fill="both", expand=True)
        self.widgets = []
        for label, value, multiline in fields:
            ttk.Label(body, text=label).pack(anchor="w", pady=(0, app.px(4)))
            if multiline:
                widget = tk.Text(body, width=46, height=4, wrap="word", font=(FONT, 11),
                                 relief="solid", borderwidth=1, padx=app.px(6), pady=app.px(4))
                widget.insert("1.0", value)
            else:
                widget = ttk.Entry(body, width=46, font=(FONT, 11))
                widget.insert(0, value)
            widget.pack(fill="x", pady=(0, app.px(12)))
            self.widgets.append(widget)
        buttons = ttk.Frame(body)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Сохранить", style="Accent.TButton", command=self._save).pack(side="right")
        ttk.Button(buttons, text="Отмена", command=self.destroy).pack(side="right", padx=(0, app.px(8)))
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Control-Return>", self._save)
        if len(fields) == 1 and not fields[0][2]:
            self.bind("<Return>", self._save)
        self.widgets[0].focus_set()
        self.update_idletasks()
        x = app.winfo_rootx() + (app.winfo_width() - self.winfo_width()) // 2
        y = app.winfo_rooty() + (app.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{x}+{y}")
        self.grab_set()

    def _values(self):
        return [w.get("1.0", "end").strip() if isinstance(w, tk.Text) else w.get().strip()
                for w in self.widgets]

    def _save(self, event=None):
        try:
            self.on_save(*self._values())
        except ValidationError as error:
            messagebox.showerror("Проверьте данные", str(error), parent=self)
            return "break"
        self.destroy()
        self.app.refresh()
        return "break"


class DecksTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=app.px(12))
        self.app = app
        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=3)
        self.rowconfigure(0, weight=1)

        left, inner = panel(self, app)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, app.px(12)))
        ttk.Label(inner, text="Колоды", style="Title.TLabel").pack(anchor="w", pady=(0, app.px(8)))
        self.decks = ttk.Treeview(inner, columns=("name", "total", "due", "learned"),
                                  show="headings", selectmode="browse")
        for col, title, width, anchor in (("name", "Колода", 170, "w"), ("total", "Всего", 54, "center"),
                                          ("due", "Сегодня", 64, "center"),
                                          ("learned", "Выучено", 68, "center")):
            self.decks.heading(col, text=title, anchor=anchor)
            self.decks.column(col, width=app.px(width), anchor=anchor, stretch=col == "name")
        self.decks.pack(fill="both", expand=True)
        self.decks.bind("<<TreeviewSelect>>", lambda e: self.refresh_cards())
        row = ttk.Frame(inner, style="Surface.TFrame")
        row.pack(fill="x", pady=(app.px(10), 0))
        ttk.Button(row, text="Новая колода", style="Accent.TButton", command=self.add_deck).pack(side="left")
        ttk.Button(row, text="Переименовать", command=self.rename_deck).pack(side="left", padx=app.px(6))
        ttk.Button(row, text="Удалить", command=self.delete_deck).pack(side="left")

        right, inner = panel(self, app)
        right.grid(row=0, column=1, sticky="nsew")
        top = ttk.Frame(inner, style="Surface.TFrame")
        top.pack(fill="x", pady=(0, app.px(8)))
        self.cards_title = ttk.Label(top, text="Карточки", style="Title.TLabel")
        self.cards_title.pack(side="left")
        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *a: self.refresh_cards())
        ttk.Entry(top, textvariable=self.search, width=22).pack(side="right")
        ttk.Label(top, text="Поиск:", style="Muted.TLabel").pack(side="right", padx=(0, app.px(6)))
        self.cards = ttk.Treeview(inner, columns=("front", "back", "box", "due"),
                                  show="headings", selectmode="browse")
        for col, title, width, anchor in (("front", "Вопрос", 170, "w"), ("back", "Ответ", 150, "w"),
                                          ("box", "Ячейка", 60, "center"),
                                          ("due", "Повторение", 96, "center")):
            self.cards.heading(col, text=title, anchor=anchor)
            self.cards.column(col, width=app.px(width), anchor=anchor, stretch=col in ("front", "back"))
        self.cards.pack(fill="both", expand=True)
        self.cards.bind("<Double-1>", lambda e: self.edit_card())
        row = ttk.Frame(inner, style="Surface.TFrame")
        row.pack(fill="x", pady=(app.px(10), 0))
        ttk.Button(row, text="Добавить", style="Accent.TButton", command=self.add_card).pack(side="left")
        ttk.Button(row, text="Изменить", command=self.edit_card).pack(side="left", padx=app.px(6))
        ttk.Button(row, text="Удалить", command=self.delete_card).pack(side="left")
        ttk.Button(row, text="Экспорт CSV", command=self.export_csv).pack(side="right")
        ttk.Button(row, text="Импорт CSV", command=self.import_csv).pack(side="right", padx=app.px(6))

    # ----- данные -----

    def selected_deck(self):
        selection = self.decks.selection()
        return int(selection[0]) if selection else None

    def selected_card(self):
        selection = self.cards.selection()
        return int(selection[0]) if selection else None

    def refresh(self):
        keep = self.selected_deck()
        self.decks.delete(*self.decks.get_children())
        decks = self.app.storage.list_decks(self.app.today())
        for deck in decks:
            self.decks.insert("", "end", iid=str(deck["id"]),
                              values=(deck["name"], deck["total"], deck["due"], deck["learned"]))
        ids = [d["id"] for d in decks]
        if ids:
            self.decks.selection_set(str(keep if keep in ids else ids[0]))
        self.refresh_cards()

    def refresh_cards(self):
        self.cards.delete(*self.cards.get_children())
        deck_id = self.selected_deck()
        if deck_id is None:
            self.cards_title.configure(text="Карточки")
            return
        name = self.decks.set(str(deck_id), "name")
        cards = self.app.storage.list_cards(deck_id, self.search.get())
        self.cards_title.configure(text=f"{name} · {cards_word(len(cards))}")
        today = self.app.today()
        for card in cards:
            due = date.fromisoformat(card["due"])
            self.cards.insert("", "end", iid=str(card["id"]),
                              values=(card["front"], card["back"], card["box"], due_text(due, today)))

    # ----- действия -----

    def add_deck(self):
        def save(name):
            deck_id = self.app.storage.add_deck(name)
            self.decks.selection_set(())
            self.after_idle(lambda: self.decks.selection_set(str(deck_id)))
        FormDialog(self.app, "Новая колода", [("Название", "", False)], save)

    def rename_deck(self):
        deck_id = self.selected_deck()
        if deck_id is None:
            return
        name = self.decks.set(str(deck_id), "name")
        FormDialog(self.app, "Переименовать колоду", [("Название", name, False)],
                   lambda new: self.app.storage.rename_deck(deck_id, new))

    def delete_deck(self):
        deck_id = self.selected_deck()
        if deck_id is None:
            return
        name = self.decks.set(str(deck_id), "name")
        total = self.decks.set(str(deck_id), "total")
        if messagebox.askyesno("Удалить колоду",
                               f"Удалить колоду «{name}» и все её карточки ({total})?\n"
                               "История повторений этих карточек тоже будет удалена.", parent=self):
            self.app.storage.delete_deck(deck_id)
            self.app.refresh()

    def add_card(self):
        deck_id = self.selected_deck()
        if deck_id is None:
            messagebox.showinfo("Нет колоды", "Сначала создайте колоду.", parent=self)
            return
        FormDialog(self.app, "Новая карточка", [("Вопрос", "", True), ("Ответ", "", True)],
                   lambda front, back: self.app.storage.add_card(deck_id, front, back, self.app.today()))

    def edit_card(self):
        card_id = self.selected_card()
        if card_id is None:
            return
        card = self.app.storage.get_card(card_id)
        FormDialog(self.app, "Изменить карточку",
                   [("Вопрос", card["front"], True), ("Ответ", card["back"], True)],
                   lambda front, back: self.app.storage.update_card(card_id, front, back))

    def delete_card(self):
        card_id = self.selected_card()
        if card_id is None:
            return
        if messagebox.askyesno("Удалить карточку", "Удалить выбранную карточку?", parent=self):
            self.app.storage.delete_card(card_id)
            self.app.refresh()

    def import_csv(self):
        deck_id = self.selected_deck()
        if deck_id is None:
            messagebox.showinfo("Нет колоды", "Выберите колоду, в которую добавить карточки.", parent=self)
            return
        path = filedialog.askopenfilename(parent=self, title="Импорт карточек",
                                          filetypes=[("Таблица CSV", "*.csv"), ("Все файлы", "*.*")])
        if not path:
            return
        try:
            added, skipped = csv_io.import_cards(self.app.storage, deck_id, path, self.app.today())
        except (OSError, UnicodeDecodeError) as error:
            messagebox.showerror("Не удалось прочитать файл", str(error), parent=self)
            return
        message = f"Добавлено: {cards_word(added)}."
        if skipped:
            message += f"\nПропущено строк: {skipped} (повторы, пустые или слишком длинные)."
        messagebox.showinfo("Импорт завершён", message, parent=self)
        self.app.refresh()

    def export_csv(self):
        deck_id = self.selected_deck()
        if deck_id is None:
            return
        name = self.decks.set(str(deck_id), "name")
        path = filedialog.asksaveasfilename(parent=self, title="Экспорт колоды", defaultextension=".csv",
                                            initialfile=f"{name}.csv", filetypes=[("Таблица CSV", "*.csv")])
        if not path:
            return
        try:
            count = csv_io.export_cards(self.app.storage, deck_id, path)
        except OSError as error:
            messagebox.showerror("Не удалось сохранить файл", str(error), parent=self)
            return
        messagebox.showinfo("Экспорт завершён", f"Сохранено: {cards_word(count)}.", parent=self)


class ReviewTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=app.px(12))
        self.app = app
        self.queue = []
        self.current = None
        self.revealed = False
        self.finished = False  # после сессии итог остаётся на экране до новой

        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, app.px(12)))
        ttk.Label(top, text="Колода:").pack(side="left")
        self.deck_choice = ttk.Combobox(top, state="readonly", width=28, font=(FONT, 10))
        self.deck_choice.pack(side="left", padx=app.px(8))
        self.deck_choice.bind("<<ComboboxSelected>>", lambda e: self._idle())
        ttk.Button(top, text="Начать повторение", style="Accent.TButton", takefocus=False,
                   command=self.start).pack(side="left")
        self.progress = ttk.Label(top, foreground=COLORS["muted"])
        self.progress.pack(side="right")

        frame, card = panel(self, app)
        frame.pack(fill="both", expand=True)
        card.configure(padding=(app.px(40), app.px(28)))
        self.deck_label = ttk.Label(card, style="Muted.TLabel", font=(FONT, 10))
        self.deck_label.pack(anchor="w")
        self.box_label = ttk.Label(card, style="Muted.TLabel", font=(FONT, 10))
        self.box_label.place(relx=1.0, y=0, anchor="ne")
        self.question = ttk.Label(card, style="Surface.TLabel", font=(FONT, 20, "bold"),
                                  justify="center", anchor="center", wraplength=app.px(640))
        self.question.pack(fill="x", expand=True, pady=(app.px(24), app.px(8)))
        self.answer_slot = ttk.Frame(card, style="Surface.TFrame", height=app.px(110))
        self.answer_slot.pack(fill="x", expand=True)
        self.answer_slot.pack_propagate(False)
        self.line = tk.Frame(self.answer_slot, height=1, bg=COLORS["border"])
        self.answer = ttk.Label(self.answer_slot, style="Surface.TLabel", font=(FONT, 15),
                                foreground=COLORS["accent_dark"], justify="center",
                                anchor="center", wraplength=app.px(640))
        self.hint = ttk.Label(card, style="Muted.TLabel", font=(FONT, 9))
        self.hint.pack(side="bottom", pady=(app.px(12), 0))

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", pady=(app.px(12), 0))
        self.show_btn = ttk.Button(buttons, text="Показать ответ", style="Accent.TButton",
                                   takefocus=False, command=self.reveal)
        self.bad_btn = ttk.Button(buttons, text="Не помню", style="Bad.TButton", takefocus=False,
                                  command=lambda: self.answer_card(False))
        self.good_btn = ttk.Button(buttons, text="Помню", style="Good.TButton", takefocus=False,
                                   command=lambda: self.answer_card(True))
        self.buttons = buttons
        self._idle()

    def refresh(self):
        names = [d["name"] for d in self.app.storage.list_decks(self.app.today())]
        self.deck_choice.configure(values=[ALL_DECKS] + names)
        if self.deck_choice.get() not in self.deck_choice["values"]:
            self.deck_choice.set(ALL_DECKS)
        if self.current is None and not self.finished:
            self._idle()

    def _deck_id(self):
        name = self.deck_choice.get()
        return None if name in ("", ALL_DECKS) else self.app.storage.get_deck_id(name)

    def _set_buttons(self, *visible):
        for btn in (self.show_btn, self.bad_btn, self.good_btn):
            btn.pack_forget()
        for btn in visible:
            btn.pack(side="left", expand=True, fill="x", padx=self.app.px(4), ipady=self.app.px(4))

    def _show_message(self, title, text):
        self.current = None
        self.deck_label.configure(text="")
        self.box_label.configure(text="")
        self.question.configure(text=title)
        self._show_answer(text, muted=True)
        self.hint.configure(text="")
        self._set_buttons()

    def _show_answer(self, text, muted=False):
        self.line.pack_forget()
        self.answer.pack_forget()
        if text:
            if not muted:
                self.line.pack(fill="x", padx=self.app.px(80), pady=(0, self.app.px(14)))
            self.answer.configure(text=text, foreground=COLORS["muted"] if muted else COLORS["accent_dark"],
                                  font=(FONT, 12 if muted else 15))
            self.answer.pack(fill="x")

    def _idle(self):
        self.finished = False
        due = len(self.app.storage.due_cards(self.app.today(), self._deck_id()))
        if due:
            text = f"Сегодня к повторению {cards_word(due)}. Нажмите «Начать повторение»."
        else:
            text = "На сегодня всё повторено. Новые карточки можно добавить на вкладке «Колоды»."
        self._show_message("Готовы к повторению?", text)
        self.progress.configure(text="")

    def start(self):
        today = self.app.today()
        self.queue = self.app.storage.due_cards(today, self._deck_id())
        if not self.queue:
            self._idle()
            return
        self.total = len(self.queue)
        self.answered = 0
        self.correct = 0
        self.retry = set()
        self.finished = False
        self.focus_set()  # чтобы пробел не попадал в список колод
        self._next()

    def _next(self):
        if not self.queue:
            self._finish()
            return
        self.current = self.queue.pop(0)
        self.revealed = False
        card = self.current
        is_retry = card["id"] in self.retry
        self.deck_label.configure(text=card["deck_name"])
        self.box_label.configure(text="повтор ошибки" if is_retry else f"ячейка {card['box']} из {scheduler.MAX_BOX}")
        self.question.configure(text=card["front"])
        self._show_answer("")
        self.hint.configure(text="Пробел — показать ответ")
        self._set_buttons(self.show_btn)
        done = min(self.answered + 1, self.total)
        self.progress.configure(text=f"Карточка {done} из {self.total} · верно {self.correct}")

    def reveal(self):
        if self.current is None or self.revealed:
            return
        self.revealed = True
        self._show_answer(self.current["back"])
        self.hint.configure(text="1 — не помню · 2 — помню")
        self._set_buttons(self.bad_btn, self.good_btn)

    def answer_card(self, remembered):
        if self.current is None or not self.revealed:
            return
        card = self.current
        if card["id"] in self.retry:
            # Повторный показ ошибки в той же сессии только закрепляет ответ:
            # расписание уже изменено первым ответом.
            pass
        else:
            self.app.storage.record_review(card["id"], remembered, self.app.today())
            self.answered += 1
            self.correct += int(remembered)
            if not remembered:
                self.retry.add(card["id"])
                self.queue.append(card)
        self._next()

    def _finish(self):
        self.current = None
        self.finished = True
        self.app.refresh()
        today = self.app.today()
        tomorrow = [c for c in self.app.storage.card_states() if c[1] == today + timedelta(days=1)]
        text = (f"Верных ответов: {self.correct} из {self.total}. "
                f"Завтра в повторении: {cards_word(len(tomorrow))}.")
        self._show_message("Сессия завершена", text)
        self.progress.configure(text="")

    def on_key(self, key):
        if key == "space":
            if self.current is None and not self.finished:
                self.start()
            else:
                self.reveal()
        elif key in ("1", "2") and self.revealed:
            self.answer_card(key == "2")


class StatsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=app.px(12))
        self.app = app
        self.days = []
        self.boxes = [0] * scheduler.MAX_BOX

        tiles = ttk.Frame(self)
        tiles.pack(fill="x", pady=(0, app.px(12)))
        self.tiles = {}
        for i, (key, caption) in enumerate((("total", "всего карточек"), ("due", "к повторению сегодня"),
                                            ("learned", "выучено (ячейка 5)"), ("accuracy", "верных за 14 дней"),
                                            ("streak", "дней подряд"))):
            tiles.columnconfigure(i, weight=1, uniform="tile")
            frame, inner = panel(tiles, app)
            frame.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else app.px(10), 0))
            value = ttk.Label(inner, style="Surface.TLabel", font=(FONT, 20, "bold"))
            value.pack(anchor="w")
            ttk.Label(inner, text=caption, style="Muted.TLabel").pack(anchor="w")
            self.tiles[key] = value

        charts = ttk.Frame(self)
        charts.pack(fill="both", expand=True)
        charts.columnconfigure(0, weight=3)
        charts.columnconfigure(1, weight=2)
        charts.rowconfigure(0, weight=1)
        self.daily_canvas = self._canvas(charts, 0)
        self.box_canvas = self._canvas(charts, 1)
        self.forecast = ttk.Label(self, foreground=COLORS["muted"])
        self.forecast.pack(anchor="w", pady=(app.px(10), 0))

    def _canvas(self, parent, column):
        frame = tk.Frame(parent, bg=COLORS["surface"], highlightthickness=1,
                         highlightbackground=COLORS["border"])
        frame.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else self.app.px(12), 0))
        canvas = tk.Canvas(frame, bg=COLORS["surface"], highlightthickness=0, height=self.app.px(300))
        canvas.pack(fill="both", expand=True, padx=self.app.px(6), pady=self.app.px(6))
        canvas.bind("<Configure>", lambda e: self.redraw())
        return canvas

    def refresh(self):
        storage, today = self.app.storage, self.app.today()
        states = storage.card_states()
        reviews = storage.reviews_since(today - timedelta(days=13))
        info = stats.summary(states, reviews, storage.review_days(), today)
        self.tiles["total"].configure(text=info["total"])
        self.tiles["due"].configure(text=info["due"])
        self.tiles["learned"].configure(text=info["learned"])
        self.tiles["accuracy"].configure(text="—" if info["accuracy"] is None else f"{info['accuracy']} %")
        self.tiles["streak"].configure(text=info["streak"])
        self.days = stats.daily_reviews(reviews, today)
        self.boxes = stats.box_distribution(states)
        load = stats.forecast(states, today)
        labels = ["сегодня", "завтра"] + [(today + timedelta(days=i)).strftime("%d.%m") for i in range(2, 7)]
        self.forecast.configure(text="Нагрузка на неделю:  " + "  ·  ".join(
            f"{label}: {count}" for label, count in zip(labels, load)))
        self.redraw()

    def redraw(self):
        self._draw_daily()
        self._draw_boxes()

    def _frame(self, canvas, title):
        canvas.delete("all")
        px = self.app.px
        canvas.create_text(px(10), px(8), text=title, anchor="nw", font=(FONT, 11, "bold"), fill=COLORS["text"])
        return canvas.winfo_width(), canvas.winfo_height()

    def _axis(self, canvas, left, top, right, bottom, top_value):
        px = self.app.px
        for value in (0, top_value // 2, top_value):
            y = bottom - (bottom - top) * value / top_value
            canvas.create_line(left, y, right, y, fill=COLORS["grid"])
            canvas.create_text(left - px(6), y, text=str(value), anchor="e", font=(FONT, 8), fill=COLORS["muted"])

    def _draw_daily(self):
        canvas, px = self.daily_canvas, self.app.px
        width, height = self._frame(canvas, "Ответы за 14 дней")
        for i, (color, label) in enumerate(((COLORS["good"], "верно"), (COLORS["bad"], "неверно"))):
            x = width - px(150) + i * px(70)
            canvas.create_rectangle(x, px(12), x + px(10), px(22), fill=color, outline="")
            canvas.create_text(x + px(14), px(17), text=label, anchor="w", font=(FONT, 9), fill=COLORS["muted"])
        if not any(d.total for d in self.days):
            canvas.create_text(width / 2, height / 2, text="Пока нет ответов", fill=COLORS["muted"], font=(FONT, 11))
            return
        left, top, right, bottom = px(40), px(48), width - px(12), height - px(30)
        top_value = max(5, -(-max(d.total for d in self.days) // 10) * 10)
        self._axis(canvas, left, top, right, bottom, top_value)
        slot = (right - left) / len(self.days)
        bar = slot * 0.62
        for i, day in enumerate(self.days):
            x0 = left + slot * i + (slot - bar) / 2
            y = bottom
            for count, color in ((day.correct, COLORS["good"]), (day.wrong, COLORS["bad"])):
                if count:
                    h = (bottom - top) * count / top_value
                    canvas.create_rectangle(x0, y - h, x0 + bar, y, fill=color, outline="")
                    y -= h
            if (len(self.days) - 1 - i) % 2 == 0:
                canvas.create_text(x0 + bar / 2, bottom + px(12), text=day.day.strftime("%d.%m"),
                                   font=(FONT, 8), fill=COLORS["muted"])

    def _draw_boxes(self):
        canvas, px = self.box_canvas, self.app.px
        width, height = self._frame(canvas, "Карточки по ячейкам")
        if not any(self.boxes):
            canvas.create_text(width / 2, height / 2, text="Карточек пока нет", fill=COLORS["muted"], font=(FONT, 11))
            return
        left, top, right, bottom = px(40), px(48), width - px(12), height - px(44)
        top_value = max(5, -(-max(self.boxes) // 10) * 10)
        self._axis(canvas, left, top, right, bottom, top_value)
        slot = (right - left) / len(self.boxes)
        bar = slot * 0.56
        for i, count in enumerate(self.boxes):
            x0 = left + slot * i + (slot - bar) / 2
            h = (bottom - top) * count / top_value
            canvas.create_rectangle(x0, bottom - h, x0 + bar, bottom, fill=BOX_COLORS[i], outline="")
            canvas.create_text(x0 + bar / 2, bottom - h - px(8), text=str(count), font=(FONT, 9, "bold"),
                               fill=COLORS["text"])
            canvas.create_text(x0 + bar / 2, bottom + px(12), text=str(i + 1), font=(FONT, 9, "bold"),
                               fill=COLORS["text"])
            days = scheduler.INTERVALS[i + 1]
            canvas.create_text(x0 + bar / 2, bottom + px(28), text=f"{days} дн.", font=(FONT, 8),
                               fill=COLORS["muted"])


def run(storage, today=date.today):
    enable_dpi_awareness()
    app = App(storage, today)
    app.mainloop()
