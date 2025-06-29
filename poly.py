import locale
locale.setlocale(locale.LC_ALL, '')

import os
import sys
import threading
import subprocess
import datetime
import time
import getpass
import socket
import curses
import tkinter as tk
from tkinter import filedialog
import subprocess



VERTICAL_COL = 23



class Tab:
    
    def __init__(self, name="New Tab"):
        self.name = name
        self.mode = 'poly'
        self.cwd = os.getcwd()
        self.buffer = []
        self.lock = threading.Lock()
        self.shell_proc = None
        self.readers = []
        self.stdin_lock = threading.Lock()

    def add(self, text):
        with self.lock:
            for line in text.splitlines():
                self.buffer.append(line)

    def run_exec(self, program):
        
        def _worker(cmd, cwd):
            try:
                proc = subprocess.Popen(
                    cmd, shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=cwd, text=True, bufsize=1
                )
            except Exception as e:
                self.add(f"Error launching '{cmd}': {e}")
                return
            for line in proc.stdout:
                self.add(line.rstrip('\n'))
            for line in proc.stderr:
                self.add(line.rstrip('\n'))
            proc.wait()

        threading.Thread(target=_worker, args=(program, self.cwd), daemon=True).start()

    def cd(self, path):
        newdir = os.path.abspath(os.path.join(self.cwd, path))
        if os.path.isdir(newdir):
            self.cwd = newdir
        else:
            self.add(f"cd: no such directory: {path}")

    def show_cwd(self):
        self.add(self.cwd)

    def set_mode(self, mode):
        m = mode.lower()
        if m not in ('poly', 'win', 'pws', 'lnx'):
            self.add(f"Invalid mode: {mode}")
            return
        if self.shell_proc:
            try:
                if self.shell_proc.poll() is None:
                    self.shell_proc.terminate()
                self.shell_proc.wait(1)
            except:
                pass
            self.shell_proc = None
        self.mode = 'poly' if m == 'poly' else m
        if self.mode == 'poly':
            return
        if m == 'win':
            exe = os.environ.get('COMSPEC', 'cmd.exe')
        elif m == 'pws':
            exe = 'powershell.exe'
        elif m == 'lnx':
            grab_shell = subprocess.run('tail -n 1 /etc/shells', capture_output=True, text=True, shell=True)
            if os.path.exists(grab_shell.stdout):
                if grab_shell.stdout in "/bin":
                    exe = grab_shell if sys.platform.startswith('win') else os.environ.get('SHELL', '/bin/sh')
            else:
                exe = 'bash' if sys.platform.startswith('win') else os.environ.get('SHELL', '/bin/sh')
        try:
            self.shell_proc = subprocess.Popen(
                exe, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=self.cwd, text=True, bufsize=1
            )
        except Exception as e:
            self.add(f"Failed to spawn shell '{exe}': {e}")
            self.mode = 'poly'
            return

        def _reader(pipe):
            for line in pipe:
                self.add(line.rstrip('\n'))

        for p in (self.shell_proc.stdout, self.shell_proc.stderr):
            t = threading.Thread(target=_reader, args=(p,), daemon=True)
            t.start()
            self.readers.append(t)

        def _waiter():
            code = self.shell_proc.wait()
            self.add(f"Exited (code {code}); reverting to Poly.")
            self.mode = 'poly'
            self.shell_proc = None

        threading.Thread(target=_waiter, daemon=True).start()

    def write_input(self, text):
        if not self.shell_proc or self.shell_proc.stdin.closed:
            self.add("No shell to send input to.")
            return
        with self.stdin_lock:
            try:
                self.shell_proc.stdin.write(text + "\n")
                self.shell_proc.stdin.flush()
            except Exception as e:
                self.add(f"Error writing to shell stdin: {e}")

    def stop(self):
        if self.shell_proc and self.shell_proc.poll() is None:
            try:
                self.shell_proc.terminate()
                self.shell_proc.wait(1)
            except:
                pass
        self.shell_proc = None



def draw_layout(stdscr):
    h, w = stdscr.getmaxyx()
    left = "Poly"
    now = datetime.datetime.now().strftime("%H:%M:%S")
    center_x = (w - len(now)) // 2
    user_host = f"{getpass.getuser()}@{socket.gethostname()}"
    right_x = w - len(user_host)
    stdscr.addstr(0, 0, left)
    stdscr.addstr(0, max(center_x, len(left) + 1), now)
    stdscr.addstr(0, max(right_x, len(left) + len(now) + 2), user_host)
    if VERTICAL_COL < w:
        stdscr.addstr(1, 0, "─" * VERTICAL_COL)
        stdscr.addstr(1, VERTICAL_COL, "┬")
        stdscr.addstr(1, VERTICAL_COL + 1, "─" * (w - VERTICAL_COL - 1))
    else:
        stdscr.addstr(1, 0, "─" * w)
    for y in range(2, h):
        if VERTICAL_COL < w:
            stdscr.addch(y, VERTICAL_COL, curses.ACS_VLINE)



def draw_sidebar(stdscr, tabs, current_idx):
    h, _ = stdscr.getmaxyx()
    width = VERTICAL_COL - 1
    for i, tab in enumerate(tabs):
        row = 2 + i
        if row >= h:
            break
        title = tab.name
        disp = (title[:width - 3] + "...") if len(title) > width else title
        attr = curses.A_REVERSE if i == current_idx else 0
        stdscr.addstr(row, 0, disp.ljust(width), attr)



def draw_messages(stdscr, tab):
    h, w = stdscr.getmaxyx()
    max_row = h - 2
    with tab.lock:
        msgs = tab.buffer[-(max_row - 3):]
    for i, line in enumerate(msgs):
        y = 3 + i
        if y < max_row:
            stdscr.addnstr(y, VERTICAL_COL + 1, line, w - VERTICAL_COL - 1)



def export_log(tab):
    curses.endwin()
    root = tk.Tk()
    root.withdraw()
    path = filedialog.asksaveasfilename(defaultextension=".txt",
                                        filetypes=[("Text files", "*.txt")])
    root.destroy()
    stdscr = curses.initscr()
    curses.cbreak()
    curses.noecho()
    stdscr.keypad(True)
    if not path:
        tab.add("Export cancelled.")
        return
    try:
        with open(path, "w", encoding="utf-8") as f, tab.lock:
            f.write("\n".join(tab.buffer))
        tab.add(f"Exported to {path}")
    except Exception as e:
        tab.add(f"Export failed: {e}")



def get_completions(inp, tabs, idx):
    if not inp.strip():
        return []
    cwd = tabs[idx].cwd
    i = inp.rfind(' ')
    if i == -1:
        base, token = '', inp
    else:
        base, token = inp[:i+1], inp[i+1:]
    cmd = inp.strip().split(' ', 1)[0].lower()
    if cmd in ('cd', 'run'):
        sep = os.sep
        token_path = token
        if token_path.endswith(sep):
            dir_full = os.path.abspath(os.path.join(cwd, token_path))
            prefix = ''
        else:
            dir_part, prefix = os.path.split(token_path)
            dir_full = os.path.abspath(os.path.join(cwd, dir_part)) if dir_part else cwd
        try:
            entries = os.listdir(dir_full)
        except Exception:
            return []
        matches = []
        for e in entries:
            if e.startswith(prefix):
                sug = os.path.join(dir_part, e) if dir_part else e
                full = base + sug + (sep if os.path.isdir(os.path.join(dir_full, e)) else '')
                matches.append(full)
        return sorted(matches)
    parts = inp.strip().split()
    token = parts[-1] if not inp.endswith(' ') else ''
    if len(parts) == 1 and not inp.endswith(' '):
        opts = ["tab", "run", "cd", "cwd"]
        return [o for o in opts if o.startswith(token)]
    if parts[0].lower() == "tab":
        if len(parts) == 1:
            opts = ["title", "mode", "create", "delete", "export"]
        else:
            sub = parts[1].lower()
            if len(parts) == 2 and not inp.endswith(' '):
                opts = ["title", "mode", "create", "delete", "export"]
            elif sub == "mode":
                opts = ["win", "pws", "lnx"]
            elif sub in ("delete", "export"):
                opts = [t.name for t in tabs]
            else:
                return []
        return [base + o for o in opts if o.startswith(token)]
    return []



def run_cli(stdscr):
    curses.curs_set(1)
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    stdscr.nodelay(True)
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_WHITE, -1)
        if getattr(curses, 'COLORS', 0) >= 16:
            curses.init_pair(2, 8, -1)
        else:
            curses.init_pair(2, curses.COLOR_WHITE, -1)
        normal_attr = curses.color_pair(1) | curses.A_BOLD
        ghost_attr = curses.color_pair(2) | curses.A_DIM
    else:
        normal_attr = curses.A_NORMAL
        ghost_attr = curses.A_DIM
    tabs = [Tab()]
    current = 0
    inp = ""
    suggestions = []
    sugg_idx = 0
    while True:
        h, w = stdscr.getmaxyx()
        stdscr.erase()
        draw_layout(stdscr)
        draw_sidebar(stdscr, tabs, current)
        draw_messages(stdscr, tabs[current])
        mode = tabs[current].mode
        if mode == 'poly':
            new_sugs = get_completions(inp, tabs, current)
        else:
            new_sugs = []
        if new_sugs != suggestions:
            suggestions = new_sugs
            sugg_idx = 0
        ghost = ""
        if suggestions:
            full = suggestions[sugg_idx]
            if full.startswith(inp):
                ghost = full[len(inp):]
        cwd = tabs[current].cwd
        main_width = w - (VERTICAL_COL + 1)
        max_cwd = max(int(main_width * 0.3), 1)
        if len(cwd) > max_cwd:
            cwd_disp = "..." + cwd[-(max_cwd - 3):]
        else:
            cwd_disp = cwd
        prompt_str = f"{cwd_disp} > {inp}"
        stdscr.addstr(h - 1, VERTICAL_COL + 1, prompt_str, normal_attr)
        if ghost:
            stdscr.addstr(h - 1, VERTICAL_COL + 1 + len(prompt_str), ghost, ghost_attr)
        stdscr.move(h - 1, VERTICAL_COL + 4 + len(cwd_disp) + len(inp))
        stdscr.refresh()
        try:
            ch = stdscr.get_wch()
        except curses.error:
            time.sleep(0.05)
            continue
        if ch == curses.KEY_RESIZE:
            continue
        if ch == curses.KEY_DOWN and suggestions:
            sugg_idx = (sugg_idx + 1) % len(suggestions)
            continue
        if ch == curses.KEY_UP and suggestions:
            sugg_idx = (sugg_idx - 1) % len(suggestions)
            continue
        if ch == curses.KEY_RIGHT and suggestions:
            inp = suggestions[sugg_idx]
            continue
        if ch == "\t":
            current = (current + 1) % len(tabs)
            inp = ""
            continue
        if ch == curses.KEY_BTAB:
            current = (current - 1) % len(tabs)
            inp = ""
            continue
        if ch == "\x14":
            tabs.append(Tab())
            current = len(tabs) - 1
            inp = ""
            continue
        if ch == "\x17":
            tabs[current].stop()
            del tabs[current]
            if not tabs:
                return
            current = min(current, len(tabs) - 1)
            inp = ""
            continue
        if ch in ("\n", "\r"):
            line = inp
            inp = ""
            if mode != 'poly':
                tabs[current].write_input(line)
                continue
            if not line.strip():
                continue
            if ' ' in line:
                cmd, rest = line.split(' ', 1)
            else:
                cmd, rest = line, ''
            lc = cmd.lower()
            if lc in ("exit", "quit"):
                return
            if lc == "tab":
                if not rest:
                    tabs[current].add("Usage: tab title <t> | mode <m> | create [t] | delete <t> | export [t]")
                else:
                    parts = rest.split(' ', 1)
                    sub = parts[0].lower()
                    arg = parts[1] if len(parts) > 1 else ''
                    if sub == "title" and arg:
                        tabs[current].name = arg
                    elif sub == "mode" and arg:
                        tabs[current].set_mode(arg)
                    elif sub == "create":
                        title = arg if arg else "New Tab"
                        tabs.append(Tab(title))
                        current = len(tabs) - 1
                    elif sub == "delete" and arg:
                        idxs = [i for i, t in enumerate(tabs) if t.name == arg]
                        if not idxs:
                            tabs[current].add(f"No tabs named '{arg}'")
                        else:
                            for i in reversed(idxs):
                                tabs[i].stop()
                                del tabs[i]
                            if not tabs:
                                return
                            current = min(current, len(tabs) - 1)
                    elif sub == "export":
                        if arg:
                            found = next((t for t in tabs if t.name == arg), None)
                            if not found:
                                tabs[current].add(f"No tabs named '{arg}'")
                            else:
                                export_log(found)
                        else:
                            export_log(tabs[current])
                    else:
                        tabs[current].add("Usage: tab title <t> | mode <m> | create [t] | delete <t> | export [t]")
                continue
            if lc == "cd" and rest:
                tabs[current].cd(rest)
                continue
            if lc == "cwd" and not rest:
                tabs[current].show_cwd()
                continue
            if lc == "run" and rest:
                tabs[current].run_exec(rest)
                continue
            tabs[current].add(f"Unknown: {cmd}")
            continue
        if ch in (curses.KEY_BACKSPACE, "\b", "\x7f"):
            inp = inp[:-1]
            continue
        if isinstance(ch, str) and ch.isprintable():
            inp += ch



def main():
    try:
        curses.wrapper(run_cli)
    except KeyboardInterrupt:
        pass



if __name__ == "__main__":
    main()
