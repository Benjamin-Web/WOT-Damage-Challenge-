"""
server_gui.py — BeastSync Server mit Tkinter-GUI.
Flask laeuft im Hintergrundthread, GUI im Main-Thread.
"""

import sys
import os
import threading
import time
import socket
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

# ─── Ressourcenpfad ───────────────────────────────────────────────────────────

def _res(rel):
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


SERVER_DIR  = _res('server')
OVERLAY_DIR = _res('overlay')
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

import config as cfg
from state import ChallengeState

state = ChallengeState()
state.configure(cfg.INITIAL_GOAL, cfg.STREAMER_NAMES)

# ─── Flask im Hintergrund ─────────────────────────────────────────────────────

def _start_flask():
    from flask import Flask, request, jsonify, send_from_directory
    from flask_cors import CORS
    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)

    app = Flask(__name__, static_folder=OVERLAY_DIR)
    CORS(app)

    def _auth(data):
        return (not cfg.ADMIN_SECRET) or data.get('secret') == cfg.ADMIN_SECRET

    @app.route('/damage', methods=['POST', 'GET'])
    def post_damage():
        if request.method == 'POST':
            data     = request.get_json(force=True, silent=True) or {}
            streamer = str(data.get('streamer', '')).strip()
            raw      = data.get('damage', 0)
            key      = data.get('key')
        else:
            streamer = request.args.get('streamer', '').strip()
            raw      = request.args.get('damage', 0)
            key      = request.args.get('key')
        try:
            damage = int(float(raw))
        except (ValueError, TypeError):
            return jsonify({'ok': False, 'error': 'invalid damage'}), 400
        if damage <= 0:
            return jsonify({'ok': False, 'error': 'damage must be positive'}), 400
        ok, remaining = state.record_damage(streamer, damage, key=key)
        return jsonify({'ok': ok, 'remaining': remaining})

    @app.route('/status')
    def get_status():
        return jsonify(state.to_dict())

    @app.route('/admin/set', methods=['POST'])
    def admin_set():
        data = request.get_json(force=True, silent=True) or {}
        if not _auth(data): return jsonify({'ok': False, 'error': 'unauthorized'}), 403
        new_goal = data.get('goal')
        if bool(data.get('reset', False)):
            state.reset(new_goal=new_goal)
        elif new_goal is not None:
            with state._lock: state.goal = float(new_goal)
        return jsonify({'ok': True, 'state': state.to_dict()})

    @app.route('/admin/pause', methods=['POST'])
    def admin_pause():
        data = request.get_json(force=True, silent=True) or {}
        if not _auth(data): return jsonify({'ok': False, 'error': 'unauthorized'}), 403
        state.paused = bool(data.get('paused', True))
        return jsonify({'ok': True, 'paused': state.paused})

    @app.route('/admin/streamers', methods=['POST'])
    def admin_streamers():
        data   = request.get_json(force=True, silent=True) or {}
        if not _auth(data): return jsonify({'ok': False, 'error': 'unauthorized'}), 403
        action = data.get('action')
        name   = str(data.get('name', '')).strip()
        if not name: return jsonify({'ok': False, 'error': 'name required'}), 400
        if action == 'add':
            ok, msg = state.add_streamer(name)
        elif action == 'remove':
            ok, msg = state.remove_streamer(name)
        else:
            return jsonify({'ok': False, 'error': 'action must be add or remove'}), 400
        return jsonify({'ok': ok, 'message': msg, 'state': state.to_dict()})

    @app.route('/')
    @app.route('/overlay')
    def serve_overlay():
        return send_from_directory(OVERLAY_DIR, 'index.html')

    @app.route('/admin')
    def serve_admin():
        return send_from_directory(OVERLAY_DIR, 'admin.html')

    app.run(host='0.0.0.0', port=cfg.PORT, debug=False,
            threaded=True, use_reloader=False)


threading.Thread(target=_start_flask, daemon=True).start()

# ─── Lokale IP ────────────────────────────────────────────────────────────────

def _local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

LOCAL_IP = _local_ip()

# ─── Design-Konstanten ────────────────────────────────────────────────────────

BG     = '#0d1117'
BG2    = '#161b22'
BDR    = '#30363d'
ACCENT = '#ffe033'
GREEN  = '#3fb950'
RED    = '#f85149'
WHITE  = '#e6edf3'
GRAY   = '#8b949e'
FONT   = 'Segoe UI'


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('BeastSync | Mohjo_beist — Server')
        self.configure(bg=BG)
        self.resizable(False, False)
        self._build()
        self._poll()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        # Farbstreifen oben
        tk.Frame(self, bg=ACCENT, height=4).pack(fill='x')

        # Header
        hdr = tk.Frame(self, bg=BG, padx=18, pady=12)
        hdr.pack(fill='x')
        tk.Label(hdr, text='🐾  BeastSync', bg=BG, fg=ACCENT,
                 font=(FONT, 16, 'bold')).pack(side='left')
        tk.Label(hdr, text='%s:%d' % (LOCAL_IP, cfg.PORT),
                 bg=BG, fg=GRAY, font=(FONT, 9)).pack(side='right', pady=4)

        # ── Restdamage ────────────────────────────────────────────────────────
        counter_card = tk.Frame(self, bg=BG2, padx=18, pady=14)
        counter_card.pack(fill='x', padx=14, pady=(0, 8))

        tk.Label(counter_card, text='RESTDAMAGE', bg=BG2, fg=GRAY,
                 font=(FONT, 9, 'bold')).pack(anchor='w')

        self.lbl_remaining = tk.Label(counter_card, text='–', bg=BG2, fg=WHITE,
                                      font=(FONT, 44, 'bold'))
        self.lbl_remaining.pack(anchor='w')

        # Fortschrittsbalken (Canvas, damit Farbe steuerbar)
        self.canvas_bar = tk.Canvas(counter_card, height=6, bg=BDR,
                                    highlightthickness=0)
        self.canvas_bar.pack(fill='x', pady=(6, 2))
        self.bar_rect = self.canvas_bar.create_rectangle(0, 0, 0, 6,
                                                          fill=ACCENT, width=0)

        stat_row = tk.Frame(counter_card, bg=BG2)
        stat_row.pack(fill='x', pady=(4, 0))
        self.lbl_dealt = tk.Label(stat_row, text='Dealt: –',
                                  bg=BG2, fg=GREEN, font=(FONT, 10, 'bold'))
        self.lbl_dealt.pack(side='left')
        self.lbl_goal = tk.Label(stat_row, text='Ziel: –',
                                 bg=BG2, fg=GRAY, font=(FONT, 10))
        self.lbl_goal.pack(side='left', padx=14)
        self.lbl_paused = tk.Label(stat_row, text='', bg=BG2,
                                   fg=RED, font=(FONT, 10, 'bold'))
        self.lbl_paused.pack(side='right')

        # ── Streamer-Tabelle ──────────────────────────────────────────────────
        tk.Label(self, text='STREAMER', bg=BG, fg=GRAY,
                 font=(FONT, 9, 'bold')).pack(anchor='w', padx=16, pady=(4, 2))

        tbl_outer = tk.Frame(self, bg=BG2)
        tbl_outer.pack(fill='x', padx=14)

        style = ttk.Style()
        style.theme_use('clam')
        for el in ('Treeview', 'Treeview.Heading'):
            style.configure(el, background=BG2, foreground=WHITE,
                            fieldbackground=BG2, borderwidth=0, rowheight=26,
                            font=(FONT, 10))
        style.configure('Treeview.Heading', foreground=GRAY,
                        font=(FONT, 9, 'bold'))
        style.map('Treeview', background=[('selected', BDR)])

        cols = ('Name', 'Damage', 'Zuletzt', 'Status')
        self.tree = ttk.Treeview(tbl_outer, columns=cols, show='headings',
                                 height=6, selectmode='browse')
        for col, w in zip(cols, (170, 100, 90, 90)):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor='center')
        self.tree.pack(fill='x')

        # ── Streamer hinzufuegen / entfernen ──────────────────────────────────
        add_row = tk.Frame(self, bg=BG, padx=14, pady=6)
        add_row.pack(fill='x')

        self.add_entry = tk.Entry(add_row, bg=BG2, fg=WHITE,
                                  insertbackground=WHITE,
                                  font=(FONT, 11), bd=0, relief='flat',
                                  highlightthickness=1,
                                  highlightbackground=BDR,
                                  highlightcolor=ACCENT, width=22)
        self.add_entry.pack(side='left', ipady=5)
        self.add_entry.insert(0, 'WoT-Name hinzufügen…')
        self.add_entry.config(fg=GRAY)
        self.add_entry.bind('<FocusIn>',  self._entry_focus_in)
        self.add_entry.bind('<FocusOut>', self._entry_focus_out)
        self.add_entry.bind('<Return>', lambda _: self._add_streamer())

        _btn(add_row, '+ Hinzufügen', ACCENT, '#0d1117',
             self._add_streamer).pack(side='left', padx=(6, 4))
        _btn(add_row, '✕ Entfernen', BG2, RED,
             self._remove_selected).pack(side='left')

        # ── Aktions-Buttons ───────────────────────────────────────────────────
        btn_row = tk.Frame(self, bg=BG, padx=14, pady=10)
        btn_row.pack(fill='x')

        self.btn_pause = _btn(btn_row, '⏸  Pause', BG2, WHITE,
                              self._toggle_pause)
        self.btn_pause.pack(side='left', padx=(0, 6))
        _btn(btn_row, '↺  Reset',  RED,  WHITE, self._do_reset).pack(side='left', padx=(0, 6))
        _btn(btn_row, '⚙  Ziel',   BG2,  WHITE, self._set_goal).pack(side='left')
        _btn(btn_row, '🌐  Admin',  BG2,  ACCENT,
             self._open_admin).pack(side='right')

        # OBS-URL-Zeile
        url_row = tk.Frame(self, bg=BG, padx=16, pady=(0, 12))
        url_row.pack(fill='x')
        obs_url = 'http://%s:%d/overlay' % (LOCAL_IP, cfg.PORT)
        tk.Label(url_row, text='OBS-URL:', bg=BG, fg=GRAY,
                 font=(FONT, 9)).pack(side='left')
        lbl = tk.Label(url_row, text=obs_url, bg=BG, fg=ACCENT,
                       font=(FONT, 9, 'underline'), cursor='hand2')
        lbl.pack(side='left', padx=6)
        lbl.bind('<Button-1>', lambda _: webbrowser.open(obs_url))

    # ── Entry Placeholder ─────────────────────────────────────────────────────

    def _entry_focus_in(self, _):
        if self.add_entry.get() == 'WoT-Name hinzufügen…':
            self.add_entry.delete(0, 'end')
            self.add_entry.config(fg=WHITE)

    def _entry_focus_out(self, _):
        if not self.add_entry.get():
            self.add_entry.insert(0, 'WoT-Name hinzufügen…')
            self.add_entry.config(fg=GRAY)

    # ── Streamer-Aktionen ─────────────────────────────────────────────────────

    def _add_streamer(self):
        name = self.add_entry.get().strip()
        if not name or name == 'WoT-Name hinzufügen…':
            return
        ok, msg = state.add_streamer(name)
        if ok:
            self.add_entry.delete(0, 'end')
            self.add_entry.insert(0, 'WoT-Name hinzufügen…')
            self.add_entry.config(fg=GRAY)
        else:
            messagebox.showerror('Fehler', msg)

    def _remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('Hinweis', 'Bitte zuerst einen Streamer in der Liste auswählen.')
            return
        name = self.tree.item(sel[0], 'values')[0]
        if messagebox.askyesno('Entfernen', f'"{name}" deaktivieren?'):
            state.remove_streamer(name)

    # ── Event-Kontrolle ───────────────────────────────────────────────────────

    def _toggle_pause(self):
        state.paused = not state.paused

    def _do_reset(self):
        if messagebox.askyesno('Reset', 'Alle Damage-Daten zurücksetzen?',
                               icon='warning'):
            state.reset()

    def _set_goal(self):
        val = simpledialog.askinteger('Neues Ziel', 'Schaden-Ziel:',
                                      initialvalue=int(state.goal), minvalue=1)
        if val:
            with state._lock:
                state.goal = float(val)

    def _open_admin(self):
        webbrowser.open('http://localhost:%d/admin' % cfg.PORT)

    # ── Poll + Render ─────────────────────────────────────────────────────────

    def _poll(self):
        data = state.to_dict()
        self._render(data)
        self.after(600, self._poll)

    def _fmt(self, n):
        return '{:,.0f}'.format(max(0, n)).replace(',', '.')

    def _time_since(self, iso):
        if not iso:
            return '—'
        import datetime
        try:
            ts   = datetime.datetime.strptime(iso, '%Y-%m-%dT%H:%M:%SZ')
            diff = int((datetime.datetime.utcnow() - ts).total_seconds())
            if diff < 5:   return 'gerade'
            if diff < 60:  return '%ds' % diff
            return '%dmin' % (diff // 60)
        except Exception:
            return '?'

    def _render(self, data):
        remaining   = data['remaining']
        goal        = data['goal']
        total_dealt = data['total_dealt']
        paused      = data['paused']

        self.lbl_remaining.config(text=self._fmt(remaining))
        self.lbl_dealt.config(text='Dealt: %s' % self._fmt(total_dealt))
        self.lbl_goal.config(text='Ziel: %s' % self._fmt(goal))
        self.lbl_paused.config(text='⏸ PAUSE' if paused else '')
        self.btn_pause.config(
            text='▶  Fortsetzen' if paused else '⏸  Pause',
            fg=GREEN if paused else WHITE)

        # Fortschrittsbalken
        self.canvas_bar.update_idletasks()
        bar_w = self.canvas_bar.winfo_width()
        pct = min(1.0, total_dealt / goal if goal > 0 else 0)
        self.canvas_bar.coords(self.bar_rect, 0, 0, int(bar_w * pct), 6)

        # Streamer-Tabelle
        for row in self.tree.get_children():
            self.tree.delete(row)

        import datetime
        for name, info in data['streamers'].items():
            active = info.get('active', True)
            if info['last_seen'] and active:
                try:
                    ts     = datetime.datetime.strptime(
                        info['last_seen'], '%Y-%m-%dT%H:%M:%SZ')
                    online = (datetime.datetime.utcnow() - ts).total_seconds() < 90
                except Exception:
                    online = False
            else:
                online = False

            status = ('● Online' if online else ('○ Offline' if active else '— Inaktiv'))
            tag    = 'online' if online else ('inactive' if not active else '')
            iid    = self.tree.insert('', 'end', values=(
                name, self._fmt(info['damage']),
                self._time_since(info['last_seen']), status), tags=(tag,))

        self.tree.tag_configure('online',   foreground=GREEN)
        self.tree.tag_configure('inactive', foreground=GRAY)


# ─── Hilfs-Widget ────────────────────────────────────────────────────────────

def _btn(parent, text, bg, fg, cmd):
    return tk.Button(parent, text=text, bg=bg, fg=fg,
                     font=(FONT, 10, 'bold'), bd=0,
                     padx=12, pady=6, cursor='hand2',
                     activebackground=bg, activeforeground=fg,
                     command=cmd)


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    time.sleep(0.6)   # Flask hochfahren lassen
    App().mainloop()
