import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from converters.manager import manager
from converters.youtube import YoutubeDownloader

# ═══════════════════════════════════════════════════════════════
# Палитра (Catppuccin Mocha — утончённая тёмная тема)
# ═══════════════════════════════════════════════════════════════
BG        = "#11111b"   # Самый глубокий фон
BG2       = "#181825"   # Фон карточек
SURFACE   = "#1e1e2e"   # Приподнятые поверхности
OVERLAY   = "#313244"   # Поля ввода, разделители
TEXT      = "#cdd6f4"   # Основной текст
SUBTEXT   = "#a6adc8"   # Приглушённый текст
BLUE      = "#89b4fa"   # Акцент
LAVENDER  = "#b4befe"   # Акцент ховер
GREEN     = "#a6e3a1"   # Успех
RED       = "#f38ba8"   # Ошибка
PEACH     = "#fab387"   # Предупреждение
ROSEWATER = "#f5e0dc"   # Мягкий акцент
MAUVE     = "#cba6f7"   # YouTube-акцент

FONT      = "Segoe UI"


# ═══════════════════════════════════════════════════════════════
# Hover-эффекты
# ═══════════════════════════════════════════════════════════════
def add_hover(widget, enter_bg, leave_bg, enter_fg=None, leave_fg=None):
    def on_enter(e):
        widget.config(bg=enter_bg)
        if enter_fg:
            widget.config(fg=enter_fg)
    def on_leave(e):
        widget.config(bg=leave_bg)
        if leave_fg:
            widget.config(fg=leave_fg)
    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)


# ═══════════════════════════════════════════════════════════════
# Прогресс-бар с градиентом
# ═══════════════════════════════════════════════════════════════
class GradientProgressBar(tk.Canvas):
    def __init__(self, parent, height=8, **kw):
        super().__init__(parent, height=height, bg=BG, highlightthickness=0, bd=0, **kw)
        self.value = 0.0
        self._color_start = BLUE
        self._color_end = LAVENDER
        self.bind("<Configure>", self._draw)

    def set_value(self, v):
        self.value = max(0.0, min(100.0, v))
        self._draw()

    def _lerp_color(self, c1, c2, t):
        r1, g1, b1 = int(c1[1:3],16), int(c1[3:5],16), int(c1[5:7],16)
        r2, g2, b2 = int(c2[1:3],16), int(c2[3:5],16), int(c2[5:7],16)
        r = int(r1 + (r2-r1)*t)
        g = int(g1 + (g2-g1)*t)
        b = int(b1 + (b2-b1)*t)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _draw(self, event=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            return
        r = h // 2
        # Трек
        self.create_round_rect(0, 0, w, h, r, fill=OVERLAY)
        # Заполнение
        if self.value > 0:
            fw = max(h, int(w * self.value / 100))
            fw = min(fw, w)
            steps = max(1, fw // 3)
            for i in range(steps):
                x = int(i * fw / steps)
                x2 = int((i+1) * fw / steps)
                col = self._lerp_color(self._color_start, self._color_end, i/steps)
                self.create_rectangle(x, 0, x2, h, fill=col, outline="")
            # Скруглённые маски по краям
            self.create_round_rect(0, 0, fw, h, r, fill="", outline="")

    def create_round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [
            x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
            x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
            x1, y2, x1, y2-r, x1, y1+r, x1, y1
        ]
        return self.create_polygon(pts, smooth=True, **kw)


# ═══════════════════════════════════════════════════════════════
# Главное приложение
# ═══════════════════════════════════════════════════════════════
class MediaConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Media Converter")
        self.root.geometry("660x680")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        # Иконка окна (опционально)
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

        # Состояние
        self.current_tab = 1
        self.is_converting = False
        self.cancel_requested = False
        self.conversion_thread = None
        self.input_file = ""
        self.file_output_dir = ""
        self.yt_url_var = tk.StringVar()
        self.yt_output_dir = os.path.join(os.path.expanduser("~"), "Downloads")

        self._setup_styles()
        self._build_ui()
        self._setup_keybindings()
        self._setup_context_menu()

    # ───── Стили ─────
    def _setup_styles(self):
        s = ttk.Style()
        s.theme_use("default")
        s.configure("TCombobox",
                     fieldbackground=OVERLAY, background=OVERLAY,
                     foreground=TEXT, bordercolor=OVERLAY, arrowcolor=TEXT,
                     selectbackground=OVERLAY, selectforeground=TEXT)
        s.map("TCombobox",
              fieldbackground=[("readonly", OVERLAY)],
              foreground=[("readonly", TEXT)])

    # ───── Клавиатурные сочетания ─────
    def _setup_keybindings(self):
        def select_all(e):
            e.widget.select_range(0, tk.END); e.widget.icursor(tk.END); return "break"
        def paste(e):
            try: e.widget.delete("sel.first","sel.last")
            except: pass
            try: e.widget.insert("insert", self.root.clipboard_get())
            except: pass
            return "break"
        def copy(e):
            try:
                t=e.widget.get(); s=e.widget.index("sel.first"); en=e.widget.index("sel.last")
                self.root.clipboard_clear(); self.root.clipboard_append(t[s:en])
            except: pass
            return "break"
        def cut(e):
            copy(e)
            try: e.widget.delete("sel.first","sel.last")
            except: pass
            return "break"

        binds = [
            ("<Control-v>",paste),("<Control-V>",paste),
            ("<Control-Cyrillic_em>",paste),("<Control-Cyrillic_EM>",paste),
            ("<Control-c>",copy),("<Control-C>",copy),
            ("<Control-Cyrillic_es>",copy),("<Control-Cyrillic_ES>",copy),
            ("<Control-x>",cut),("<Control-X>",cut),
            ("<Control-Cyrillic_ha>",cut),("<Control-Cyrillic_HA>",cut),
            ("<Control-a>",select_all),("<Control-A>",select_all),
            ("<Control-Cyrillic_a>",select_all),("<Control-Cyrillic_A>",select_all),
        ]
        for ev, fn in binds:
            self.root.bind_class("Entry", ev, fn)

    def _setup_context_menu(self):
        self.ctx = tk.Menu(self.root, tearoff=0, bg=SURFACE, fg=TEXT,
                           activebackground=OVERLAY, activeforeground=TEXT,
                           relief="flat", bd=1, font=(FONT, 9))
        def show(e):
            w = e.widget; self.ctx.delete(0,tk.END)
            has_sel = False
            try: w.index("sel.first"); has_sel=True
            except: pass
            self.ctx.add_command(label="  Вставить", command=lambda: w.event_generate("<<Paste>>"))
            self.ctx.add_command(label="  Копировать", command=lambda: w.event_generate("<<Copy>>"), state="normal" if has_sel else "disabled")
            self.ctx.add_command(label="  Вырезать", command=lambda: w.event_generate("<<Cut>>"), state="normal" if has_sel else "disabled")
            self.ctx.add_separator()
            self.ctx.add_command(label="  Выделить всё", command=lambda: (w.select_range(0,tk.END), w.icursor(tk.END)), state="normal" if w.get() else "disabled")
            self.ctx.post(e.x_root, e.y_root)
        self.root.bind_class("Entry","<Button-3>", show)

    # ═══════════════════════════════════════════════════════════
    # Построение интерфейса
    # ═══════════════════════════════════════════════════════════
    def _build_ui(self):
        root = tk.Frame(self.root, bg=BG, padx=28, pady=22)
        root.pack(fill="both", expand=True)

        # ─── Заголовок ───
        hdr = tk.Frame(root, bg=BG)
        hdr.pack(fill="x", pady=(0, 6))
        tk.Label(hdr, text="Media Converter", font=(FONT, 22, "bold"), fg=TEXT, bg=BG).pack(side="left")
        tk.Label(hdr, text="v1.0", font=(FONT, 10), fg=OVERLAY, bg=BG).pack(side="left", padx=(8,0), pady=(10,0))

        # ─── Таб-бар ───
        tab_frame = tk.Frame(root, bg=BG)
        tab_frame.pack(fill="x", pady=(4, 0))

        self.tab1_btn = tk.Label(tab_frame, text="  Конвертер файлов  ", font=(FONT, 10, "bold"),
                                 fg=BLUE, bg=BG, cursor="hand2", pady=8)
        self.tab1_btn.pack(side="left")
        self.tab1_btn.bind("<Button-1>", lambda e: self._switch_tab(1))

        self.tab2_btn = tk.Label(tab_frame, text="  Конвертер с YouTube  ", font=(FONT, 10, "bold"),
                                 fg=SUBTEXT, bg=BG, cursor="hand2", pady=8)
        self.tab2_btn.pack(side="left", padx=(12, 0))
        self.tab2_btn.bind("<Button-1>", lambda e: self._switch_tab(2))

        # Подчёркивание активного таба
        self.tab_indicator = tk.Frame(root, bg=BLUE, height=2)
        self.tab_indicator.pack(fill="x", pady=(0, 16))

        # Разделитель
        tk.Frame(root, bg=OVERLAY, height=1).pack(fill="x", pady=(0, 16))

        # ─── Контейнер вкладок ───
        self.tab_container = tk.Frame(root, bg=BG)
        self.tab_container.pack(fill="both", expand=True)

        self._build_tab1()
        self._build_tab2()
        self._switch_tab(1)

    # ═══════════════════════════════════════════════════════════
    # Вкладка 1 — Файлы
    # ═══════════════════════════════════════════════════════════
    def _build_tab1(self):
        self.tab1 = tk.Frame(self.tab_container, bg=BG)

        # Карточка выбора файла
        card = self._card(self.tab1)
        self.card_title = tk.Label(card, text="Выберите файл", font=(FONT, 12, "bold"), fg=TEXT, bg=SURFACE)
        self.card_title.pack(anchor="w")
        self.card_sub = tk.Label(card, text="Видео · Аудио · Изображения", font=(FONT, 9), fg=SUBTEXT, bg=SURFACE)
        self.card_sub.pack(anchor="w", pady=(2, 14))

        self.select_btn = self._button(card, "Выбрать файл", BLUE, BG, self._select_file)
        self.select_btn.pack(anchor="w")

        self.details = tk.Frame(card, bg=SURFACE)
        self.fname_lbl = tk.Label(self.details, text="", font=(FONT, 10, "bold"), fg=BLUE, bg=SURFACE, wraplength=540, justify="left")
        self.fname_lbl.pack(anchor="w", pady=(6,1))
        self.fpath_lbl = tk.Label(self.details, text="", font=(FONT, 8), fg=SUBTEXT, bg=SURFACE, wraplength=540, justify="left")
        self.fpath_lbl.pack(anchor="w")

        # Настройки
        card2 = self._card(self.tab1)
        tk.Label(card2, text="Настройки", font=(FONT, 12, "bold"), fg=TEXT, bg=SURFACE).pack(anchor="w", pady=(0, 12))
        row = tk.Frame(card2, bg=SURFACE)
        row.pack(fill="x")

        # Формат
        left = tk.Frame(row, bg=SURFACE)
        left.pack(side="left", padx=(0, 24))
        tk.Label(left, text="ФОРМАТ", font=(FONT, 8, "bold"), fg=SUBTEXT, bg=SURFACE).pack(anchor="w", pady=(0,4))
        self.fmt_var = tk.StringVar()
        self.fmt_combo = ttk.Combobox(left, textvariable=self.fmt_var, state="readonly", width=10, font=(FONT, 10))
        self.fmt_combo.pack(anchor="w")

        # Папка
        right = tk.Frame(row, bg=SURFACE)
        right.pack(side="left", fill="x", expand=True)
        tk.Label(right, text="ПАПКА НАЗНАЧЕНИЯ", font=(FONT, 8, "bold"), fg=SUBTEXT, bg=SURFACE).pack(anchor="w", pady=(0,4))
        frow = tk.Frame(right, bg=SURFACE)
        frow.pack(fill="x")
        self.folder_var = tk.StringVar()
        self.folder_entry = tk.Entry(frow, textvariable=self.folder_var, bg=OVERLAY, fg=TEXT,
                                     insertbackground=TEXT, relief="flat", bd=0, font=(FONT, 9),
                                     state="readonly", readonlybackground=OVERLAY)
        self.folder_entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 6))
        self.folder_btn = self._button(frow, "Обзор", OVERLAY, TEXT, self._select_folder, small=True)
        self.folder_btn.pack(side="right")

        # Прогресс
        prog = tk.Frame(self.tab1, bg=BG)
        prog.pack(fill="x", pady=(16, 0))
        info = tk.Frame(prog, bg=BG)
        info.pack(fill="x", pady=(0, 6))
        self.f_status = tk.Label(info, text="Готов к работе", font=(FONT, 9), fg=SUBTEXT, bg=BG)
        self.f_status.pack(side="left")
        self.f_pct = tk.Label(info, text="", font=(FONT, 9, "bold"), fg=BLUE, bg=BG)
        self.f_pct.pack(side="right")
        self.f_bar = GradientProgressBar(prog)
        self.f_bar.pack(fill="x", pady=(0, 14))

        # Кнопки
        btns = tk.Frame(prog, bg=BG)
        btns.pack(fill="x")
        self.f_go = self._button(btns, "Конвертировать", BLUE, BG, self._start_process, big=True)
        self.f_go.pack(side="right")
        self.f_go.config(state="disabled")
        self.f_cancel = self._button(btns, "Отмена", OVERLAY, TEXT, self._cancel_process, big=True)
        self.f_cancel.pack(side="right", padx=(0, 10))
        self.f_cancel.config(state="disabled")

    # ═══════════════════════════════════════════════════════════
    # Вкладка 2 — YouTube
    # ═══════════════════════════════════════════════════════════
    def _build_tab2(self):
        self.tab2 = tk.Frame(self.tab_container, bg=BG)

        # Карточка ссылки
        card = self._card(self.tab2)
        tk.Label(card, text="Ссылка на видео", font=(FONT, 12, "bold"), fg=TEXT, bg=SURFACE).pack(anchor="w")
        tk.Label(card, text="YouTube · Вставьте URL", font=(FONT, 9), fg=SUBTEXT, bg=SURFACE).pack(anchor="w", pady=(2, 12))
        self.yt_entry = tk.Entry(card, textvariable=self.yt_url_var, bg=OVERLAY, fg=TEXT,
                                 insertbackground=TEXT, relief="flat", bd=0, font=(FONT, 11))
        self.yt_entry.pack(fill="x", ipady=9)

        # Настройки
        card2 = self._card(self.tab2)
        tk.Label(card2, text="Настройки", font=(FONT, 12, "bold"), fg=TEXT, bg=SURFACE).pack(anchor="w", pady=(0, 12))
        row = tk.Frame(card2, bg=SURFACE)
        row.pack(fill="x")

        left = tk.Frame(row, bg=SURFACE)
        left.pack(side="left", padx=(0, 24))
        tk.Label(left, text="ФОРМАТ", font=(FONT, 8, "bold"), fg=SUBTEXT, bg=SURFACE).pack(anchor="w", pady=(0,4))
        self.yt_fmt_var = tk.StringVar(value="MP3 (Аудио)")
        self.yt_fmt_combo = ttk.Combobox(left, textvariable=self.yt_fmt_var, state="readonly",
                                          values=["MP3 (Аудио)", "MP4 (Видео)"], width=14, font=(FONT, 10))
        self.yt_fmt_combo.pack(anchor="w")

        right = tk.Frame(row, bg=SURFACE)
        right.pack(side="left", fill="x", expand=True)
        tk.Label(right, text="ПАПКА НАЗНАЧЕНИЯ", font=(FONT, 8, "bold"), fg=SUBTEXT, bg=SURFACE).pack(anchor="w", pady=(0,4))
        frow = tk.Frame(right, bg=SURFACE)
        frow.pack(fill="x")
        self.yt_folder_var = tk.StringVar(value=self.yt_output_dir)
        self.yt_folder_entry = tk.Entry(frow, textvariable=self.yt_folder_var, bg=OVERLAY, fg=TEXT,
                                        insertbackground=TEXT, relief="flat", bd=0, font=(FONT, 9),
                                        state="readonly", readonlybackground=OVERLAY)
        self.yt_folder_entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 6))
        self.yt_folder_btn = self._button(frow, "Обзор", OVERLAY, TEXT, self._select_folder_yt, small=True)
        self.yt_folder_btn.pack(side="right")

        # Прогресс
        prog = tk.Frame(self.tab2, bg=BG)
        prog.pack(fill="x", pady=(16, 0))
        info = tk.Frame(prog, bg=BG)
        info.pack(fill="x", pady=(0, 6))
        self.yt_status = tk.Label(info, text="Готов к работе", font=(FONT, 9), fg=SUBTEXT, bg=BG)
        self.yt_status.pack(side="left")
        self.yt_pct = tk.Label(info, text="", font=(FONT, 9, "bold"), fg=MAUVE, bg=BG)
        self.yt_pct.pack(side="right")
        self.yt_bar = GradientProgressBar(prog)
        self.yt_bar._color_start = MAUVE
        self.yt_bar._color_end = ROSEWATER
        self.yt_bar.pack(fill="x", pady=(0, 14))

        btns = tk.Frame(prog, bg=BG)
        btns.pack(fill="x")
        self.yt_go = self._button(btns, "Скачать", MAUVE, BG, self._start_process, big=True)
        self.yt_go.pack(side="right")
        self.yt_cancel = self._button(btns, "Отмена", OVERLAY, TEXT, self._cancel_process, big=True)
        self.yt_cancel.pack(side="right", padx=(0, 10))
        self.yt_cancel.config(state="disabled")

    # ═══════════════════════════════════════════════════════════
    # Хелперы UI
    # ═══════════════════════════════════════════════════════════
    def _card(self, parent):
        outer = tk.Frame(parent, bg=OVERLAY, padx=1, pady=1)
        outer.pack(fill="x", pady=(0, 12))
        inner = tk.Frame(outer, bg=SURFACE, padx=20, pady=16)
        inner.pack(fill="both")
        return inner

    def _button(self, parent, text, bg_color, fg_color, command, small=False, big=False):
        px, py = (12, 4) if small else (22, 9) if big else (16, 7)
        fs = 8 if small else 10 if big else 9
        fw = "bold" if big else "normal"
        btn = tk.Button(parent, text=text, bg=bg_color, fg=fg_color,
                        activebackground=bg_color, activeforeground=fg_color,
                        font=(FONT, fs, fw), relief="flat", bd=0,
                        cursor="hand2", padx=px, pady=py, command=command)
        # Hover
        if bg_color == BLUE:
            add_hover(btn, LAVENDER, BLUE)
        elif bg_color == MAUVE:
            add_hover(btn, LAVENDER, MAUVE)
        elif bg_color == OVERLAY:
            add_hover(btn, SURFACE, OVERLAY)
        return btn

    # ═══════════════════════════════════════════════════════════
    # Переключение вкладок
    # ═══════════════════════════════════════════════════════════
    def _switch_tab(self, n):
        if self.is_converting:
            messagebox.showwarning("Внимание", "Дождитесь завершения операции.")
            return
        self.current_tab = n
        if n == 1:
            self.tab1_btn.config(fg=BLUE)
            self.tab2_btn.config(fg=SUBTEXT)
            self.tab_indicator.config(bg=BLUE)
            self.tab2.pack_forget()
            self.tab1.pack(fill="both", expand=True)
        else:
            self.tab1_btn.config(fg=SUBTEXT)
            self.tab2_btn.config(fg=MAUVE)
            self.tab_indicator.config(bg=MAUVE)
            self.tab1.pack_forget()
            self.tab2.pack(fill="both", expand=True)

    # ═══════════════════════════════════════════════════════════
    # Выбор файлов и папок
    # ═══════════════════════════════════════════════════════════
    def _select_file(self):
        filetypes = [
            ("Все поддерживаемые", "*.mp4 *.avi *.mkv *.mov *.webm *.flv *.wmv *.ts *.m4v "
             "*.mp3 *.wav *.aac *.flac *.ogg *.wma *.m4a *.aiff *.opus "
             "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp *.ico"),
            ("Видео", "*.mp4 *.avi *.mkv *.mov *.webm *.flv *.wmv *.ts *.m4v"),
            ("Аудио", "*.mp3 *.wav *.aac *.flac *.ogg *.wma *.m4a *.aiff *.opus"),
            ("Изображения", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp *.ico"),
            ("Все файлы", "*.*"),
        ]
        path = filedialog.askopenfilename(title="Выберите файл", filetypes=filetypes)
        if not path:
            return
        self.input_file = os.path.abspath(path)

        self.card_title.config(text="Выбранный файл:")
        self.card_sub.pack_forget()
        self.select_btn.pack_forget()

        self.fname_lbl.config(text=os.path.basename(self.input_file))
        self.fpath_lbl.config(text=self.input_file)
        self.details.pack(anchor="w", fill="x", pady=(4, 0))

        self.select_btn.config(text="Изменить", padx=10, pady=3)
        self.select_btn.pack(anchor="w", pady=(10, 0))

        if not self.file_output_dir:
            self.file_output_dir = os.path.dirname(self.input_file)
            self.folder_var.set(self.file_output_dir)

        targets = manager.get_supported_targets(self.input_file)
        self.fmt_combo.config(values=targets)
        if targets:
            default = ".mp3" if ".mp3" in targets else targets[0]
            self.fmt_var.set(default)
            self.f_go.config(state="normal")
        else:
            self.fmt_var.set("")
            self.f_go.config(state="disabled")
            messagebox.showerror("Ошибка", "Формат не поддерживается.")

    def _select_folder(self):
        p = filedialog.askdirectory(initialdir=self.file_output_dir or "/")
        if p:
            self.file_output_dir = os.path.abspath(p)
            self.folder_var.set(self.file_output_dir)

    def _select_folder_yt(self):
        p = filedialog.askdirectory(initialdir=self.yt_output_dir)
        if p:
            self.yt_output_dir = os.path.abspath(p)
            self.yt_folder_var.set(self.yt_output_dir)

    # ═══════════════════════════════════════════════════════════
    # Логика конвертации — Файлы
    # ═══════════════════════════════════════════════════════════
    def _start_process(self):
        if self.is_converting:
            return
        if self.current_tab == 1:
            self._start_file()
        else:
            self._start_yt()

    def _start_file(self):
        ext = self.fmt_var.get()
        if not self.input_file or not ext:
            return
        base, _ = os.path.splitext(os.path.basename(self.input_file))
        out = os.path.join(self.file_output_dir, f"{base}{ext}")
        if os.path.exists(out):
            if not messagebox.askyesno("Файл существует", f"'{base}{ext}' уже существует. Перезаписать?"):
                return
        self.is_converting = True
        self.cancel_requested = False
        self._lock_ui()
        self.f_bar.set_value(0); self.f_pct.config(text="0%")
        self.f_status.config(text="Конвертация...", fg=SUBTEXT)
        threading.Thread(target=self._run_file, args=(out,), daemon=True).start()

    def _run_file(self, out):
        err, cancel = None, False
        try:
            c = manager.get_converter(self.input_file, self.fmt_var.get(), out)
            c.convert(progress_callback=self._prog_file, check_cancel=self._chk)
        except InterruptedError: cancel = True
        except Exception as e: err = str(e)
        self.root.after(0, lambda: self._done(cancel, err, out))

    def _prog_file(self, p):
        self.root.after(0, lambda: (self.f_bar.set_value(p), self.f_pct.config(text=f"{int(p)}%")))

    # ═══════════════════════════════════════════════════════════
    # Логика конвертации — YouTube
    # ═══════════════════════════════════════════════════════════
    def _start_yt(self):
        url = self.yt_url_var.get().strip()
        if not url:
            messagebox.showwarning("Ошибка", "Вставьте ссылку на видео.")
            return
        if not ("youtube.com" in url or "youtu.be" in url):
            messagebox.showwarning("Ошибка", "Ссылка должна вести на YouTube.")
            return
        self.is_converting = True
        self.cancel_requested = False
        self._lock_ui()
        self.yt_bar.set_value(0); self.yt_pct.config(text="0%")
        self.yt_status.config(text="Поиск видео...", fg=SUBTEXT)
        fmt = "mp3" if "MP3" in self.yt_fmt_var.get() else "mp4"
        threading.Thread(target=self._run_yt, args=(url, self.yt_output_dir, fmt), daemon=True).start()

    def _run_yt(self, url, d, fmt):
        err, cancel, out = None, False, None
        try:
            dl = YoutubeDownloader(url, d, fmt)
            out = dl.download(progress_callback=self._prog_yt, check_cancel=self._chk)
        except InterruptedError: cancel = True
        except Exception as e:
            err = str(e)
            if "Incomplete YouTube ID" in err or "RegexMatchError" in err:
                err = "Некорректная ссылка."
            elif "HTTP Error 403" in err:
                err = "YouTube отклонил запрос (403)."
        self.root.after(0, lambda: self._done(cancel, err, out))

    def _prog_yt(self, p):
        self.root.after(0, lambda: (self.yt_bar.set_value(p), self.yt_pct.config(text=f"{int(p)}%")))
        if p < 85:
            self.root.after(0, lambda: self.yt_status.config(text="Загрузка...", fg=SUBTEXT))
        elif p < 99:
            self.root.after(0, lambda: self.yt_status.config(text="Конвертация...", fg=SUBTEXT))

    # ═══════════════════════════════════════════════════════════
    # Управление состоянием
    # ═══════════════════════════════════════════════════════════
    def _chk(self):
        return self.cancel_requested

    def _cancel_process(self):
        if not self.is_converting: return
        self.cancel_requested = True
        if self.current_tab == 1:
            self.f_status.config(text="Отмена...", fg=PEACH)
            self.f_cancel.config(state="disabled")
        else:
            self.yt_status.config(text="Отмена...", fg=PEACH)
            self.yt_cancel.config(state="disabled")

    def _lock_ui(self):
        self.tab1_btn.config(state="disabled")
        self.tab2_btn.config(state="disabled")
        self.select_btn.config(state="disabled")
        self.folder_btn.config(state="disabled")
        self.yt_folder_btn.config(state="disabled")
        self.fmt_combo.config(state="disabled")
        self.yt_fmt_combo.config(state="disabled")
        self.yt_entry.config(state="disabled")
        if self.current_tab == 1:
            self.f_go.config(state="disabled"); self.f_cancel.config(state="normal")
        else:
            self.yt_go.config(state="disabled"); self.yt_cancel.config(state="normal")

    def _unlock_ui(self):
        self.tab1_btn.config(state="normal")
        self.tab2_btn.config(state="normal")
        self.select_btn.config(state="normal")
        self.folder_btn.config(state="normal")
        self.yt_folder_btn.config(state="normal")
        self.fmt_combo.config(state="readonly")
        self.yt_fmt_combo.config(state="readonly")
        self.yt_entry.config(state="normal")
        self.f_cancel.config(state="disabled")
        self.yt_cancel.config(state="disabled")
        self.f_go.config(state="normal" if self.input_file else "disabled")
        self.yt_go.config(state="normal")

    def _done(self, cancel, err, path):
        self.is_converting = False
        self._unlock_ui()
        if self.current_tab == 1:
            st, bar, pct = self.f_status, self.f_bar, self.f_pct
        else:
            st, bar, pct = self.yt_status, self.yt_bar, self.yt_pct

        if cancel:
            st.config(text="Отменено", fg=PEACH); bar.set_value(0); pct.config(text="")
        elif err:
            st.config(text="Ошибка", fg=RED)
            messagebox.showerror("Ошибка", err)
        else:
            st.config(text="Готово!", fg=GREEN); bar.set_value(100); pct.config(text="100%")
            if messagebox.askyesno("Успех", "Файл сохранён!\n\nОткрыть папку?") and path:
                p = os.path.normpath(path)
                if sys.platform == "win32":
                    os.system(f'explorer /select,"{p}"')


# ═══════════════════════════════════════════════════════════════
# Точка входа
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    app = MediaConverterApp(root)
    root.mainloop()
