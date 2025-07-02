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
import glob
import shutil
import shlex
import urllib.request
import urllib.parse
import importlib.util
import random
import colorama
import re
import textwrap
import argparse



VERTICAL_COL = 23
ALIASES = {}
CUSTOM_COMMANDS = {}
variables = {}
variable_pattern = re.compile(r'\{([A-Za-z0-9_-]+)\}')
CLI_MODE = False



def expand_variables(text, tab):
    def repl(match):
        name = match.group(1)
        if name in variables:
            return variables[name]
        if name == 'computer':
            return socket.gethostname()
        elif name == 'date':
            return datetime.datetime.now().strftime('%m/%d/%Y')
        elif name == 'homedrive':
            if os.name == 'nt':
                return os.environ.get('SystemDrive', os.path.splitdrive(tab.cwd)[0])
            else:
                return '/'
        elif name == 'homepath':
            return os.path.expanduser('~')
        elif name == 'os':
            return 'windows' if os.name == 'nt' else 'linux'
        elif name == 'random':
            return str(random.randint(0, 32767))
        elif name == 'appdata':
            if os.name == 'nt':
                return os.environ.get('APPDATA', '')
            else:
                return os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
        elif name == 'time':
            return datetime.datetime.now().strftime('%H:%M:%S')
        elif name == 'username':
            return getpass.getuser()
        elif name == 'cwd':
            return tab.cwd
        return match.group(0)
    return variable_pattern.sub(repl, text)



def define_alias(original, alias):
    ALIASES[original] = alias



def define_command(name, function, arguments):
    CUSTOM_COMMANDS[name] = function
    CUSTOM_COMMANDS[f"__{name}_args"] = arguments



def load_icon(icon_name):
    icon_path = os.path.join(os.path.dirname(__file__), icon_name)
    if getattr(sys, 'frozen', False):
        icon_path = os.path.join(sys._MEIPASS, icon_name)
    if os.path.exists(icon_path):
        return QIcon(icon_path)
    return None



def load_plugins(app_context):
    user_home = os.path.expanduser("~")
    plugins_dir = os.path.join(user_home, "plplugins")
    os.makedirs(plugins_dir, exist_ok=True)
    loaded_plugins = []
    for filename in os.listdir(plugins_dir):
        if filename.endswith(".py") and not filename.startswith("_"):
            plugin_path = os.path.join(plugins_dir, filename)
            mod_name = os.path.splitext(filename)[0]
            spec = importlib.util.spec_from_file_location(mod_name, plugin_path)
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
                if hasattr(module, "register_plugin"):
                    module.register_plugin(app_context)
                    loaded_plugins.append(mod_name)
                    print(f"Plugin '{mod_name}' loaded successfully from {plugins_dir}")
            except Exception as e:
                print(f"Failed to load plugin '{filename}' from {plugins_dir}: {e}")
    return loaded_plugins



class Tab:

    def __init__(self, name="New Tab"):
        self.name = name
        self.mode = 'poly'
        self.cwd = os.getcwd()
        self.buffer = []
        self.history = []
        self.scroll = 0
        self.color_settings = {}
        self._next_color_pair = 3
        self.lock = threading.Lock()
        self.shell_proc = None
        self.readers = []
        self.stdin_lock = threading.Lock()
        app_context = {
            "tab": self,
            "define_command": define_command,
            "define_alias": define_alias
        }
        self.plugins = load_plugins(app_context)

    def add(self, text):
        with self.lock:
            for line in text.splitlines():
                self.buffer.append(line)
                if CLI_MODE:
                    print(line, flush=True)
    
    def clear(self):
        with self.lock:
            self.buffer = []

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
        if CLI_MODE:
            _worker(program, self.cwd)
        else:
            threading.Thread(target=_worker, args=(program, self.cwd), daemon=True).start()

    def cd(self, path):
        newdir = os.path.abspath(os.path.join(self.cwd, path))
        if os.path.isdir(newdir):
            self.cwd = newdir
        else:
            self.add(f"cd: no such directory: {path}")

    def files(self, path):
        requested_dir = os.path.abspath(os.path.join(self.cwd, path))
        if os.path.isdir(requested_dir):
            for item in os.listdir(requested_dir):
                self.add(item)
        else:
            self.add(f"files: no such directory: {path}")

    def makedir(self, path):
        newdir = os.path.abspath(os.path.join(self.cwd, path))
        try:
            if os.path.exists(newdir) :
                self.add(f"makedir: directory already exists: {newdir}")
                return
            os.mkdir(newdir)
            self.add(f"Created directory: {newdir}")
        except FileNotFoundError:
            self.add(f"makedir: cannot create directory: '{path}': No such file or directory")
        except PermissionError:
            self.add(f"makedir: permission denied: '{newdir}'")
        except OSError as e:
            self.add(f"makedir: error creating directory: '{newdir}': {e}")
        except Exception as e:
            self.add(f"makedir: error creating directory: '{newdir}': {e}")
    
    def deldir(self, pattern):
        glob_path = os.path.join(self.cwd, pattern)
        matches = glob.glob(glob_path)
        if not matches:
            self.add(f"deldir: no matches for: {pattern}")
            return
        for p in matches:
            if os.path.isdir(p):
                try:
                    shutil.rmtree(p)
                    self.add(f"Removed directory: {p}")
                except Exception as e:
                    self.add(f"deldir: error removing '{p}': {e}")
            else:
                self.add(f"deldir: not a directory: {p}")

    def remove(self, pattern):
        glob_path = os.path.join(self.cwd, pattern)
        matches = glob.glob(glob_path)
        if not matches:
            self.add(f"remove: no matches for: {pattern}")
            return
        for p in matches:
            if os.path.isfile(p):
                try:
                    os.remove(p)
                    self.add(f"Removed file: {p}")
                except Exception as e:
                    self.add(f"remove: error removing '{p}': {e}")
            else:
                self.add(f"remove: not a file: {p}")

    def make(self, filename):
            newfile = os.path.abspath(os.path.join(self.cwd, filename))
            try:
                if os.path.exists(newfile):
                    self.add(f"make: file already exists: {newfile}")
                    return
                with open(newfile, 'w', encoding='utf-8'):
                    pass
                self.add(f"Created file: {newfile}")
            except Exception as e:
                self.add(f"make: error creating file '{filename}': {e}")

    def download(self, url, filename=None):
        def _worker(u, fn):
            from urllib.request import urlopen
            from urllib.error import URLError, HTTPError
            import os, shutil
            parsed = urllib.parse.urlparse(u)
            if parsed.scheme not in ('http', 'https'):
                self.add(f"download: unsupported URL scheme")
                return
            local_name = fn or os.path.basename(parsed.path) or 'download'
            dest = os.path.abspath(os.path.join(self.cwd, local_name))
            try:
                with urlopen(u, timeout=15) as resp, open(dest, 'wb') as out:
                    shutil.copyfileobj(resp, out)
                self.add(f"Downloaded {u} -> {dest}")
            except (HTTPError, URLError) as e:
                self.add(f"download: network error: {e}")
            except Exception as e:
                self.add(f"download: error saving file: {e}")
        threading.Thread(target=_worker, args=(url, filename), daemon=True).start()

    def tree(self, path=None):
        def _worker(p):
            import os
            target = os.path.abspath(os.path.join(self.cwd, p)) if p else self.cwd
            if not os.path.exists(target):
                self.add(f"tree: no such directory: {p}")
                return
            if not os.path.isdir(target):
                self.add(f"tree: not a directory: {p}")
                return
            root_label = p or "."
            self.add(root_label)
            def walk(dir_path, prefix=""):
                try:
                    entries = sorted(os.listdir(dir_path), key=lambda n: n.lower())
                except PermissionError:
                    self.add(f"{prefix}[Permission denied]")
                    return
                for idx, name in enumerate(entries):
                    full = os.path.join(dir_path, name)
                    is_last = (idx == len(entries) - 1)
                    connector = "└── " if is_last else "├── "
                    self.add(f"{prefix}{connector}{name}")
                    if os.path.isdir(full):
                        extension = "    " if is_last else "│   "
                        walk(full, prefix + extension)
            walk(target)
        threading.Thread(target=_worker, args=(path,), daemon=True).start()

    def color(self, thing, color_name):
        import curses
        valid_things = {
            "borders", "logotext", "clock", "userinfo",
            "currenttab", "tab", "prompt", "input", "output"
        }
        curses_color_map = {
            "black":   curses.COLOR_BLACK,
            "red":     curses.COLOR_RED,
            "green":   curses.COLOR_GREEN,
            "yellow":  curses.COLOR_YELLOW,
            "blue":    curses.COLOR_BLUE,
            "magenta": curses.COLOR_MAGENTA,
            "cyan":    curses.COLOR_CYAN,
            "white":   curses.COLOR_WHITE,
        }
        thing_lc = thing.lower()
        col_norm = color_name.lower().replace(" ", "")
        if thing_lc not in valid_things:
            self.add(f"color: invalid target '{thing}'")
            return
        if col_norm.startswith("dark"):
            base = col_norm[len("dark"):]
            bold = curses.A_NORMAL
        else:
            base = col_norm
            bold = curses.A_BOLD
        if base not in curses_color_map:
            self.add(f"color: invalid color '{color_name}'")
            return
        if not curses.has_colors():
            self.add("color: terminal does not support colors")
            return
        pair_id = getattr(self, "_next_color_pair", 3)
        curses.init_pair(pair_id, curses_color_map[base], -1)
        self._next_color_pair = pair_id + 1
        self.color_settings[thing_lc] = (pair_id, bold)
        self.add(f"{thing_lc} color set to {col_norm}")

    def read(self, path):
        file_path = os.path.abspath(os.path.join(self.cwd, path))
        if not os.path.exists(file_path):
            self.add(f"read: no such file: {path}")
            return
        if os.path.isdir(file_path):
            self.add(f"read: '{path}' is a directory")
            return
        try:
            with open(file_path, 'rb') as f:
                sample = f.read(4096)
                is_text = (b'\x00' not in sample)
                f.seek(0)

                if is_text:
                    with open(file_path, 'r', encoding='latin-1', errors='replace') as tf:
                        for line in tf:
                            self.add(line.rstrip('\n'))
                else:
                    offset = 0
                    while True:
                        chunk = f.read(16)
                        if not chunk:
                            break
                        hex_bytes = [f"{b:02x}" for b in chunk]
                        first8 = hex_bytes[:8]
                        last8  = hex_bytes[8:]
                        hex_col = ' '.join(first8)
                        if last8:
                            hex_col += '  ' + ' '.join(last8)
                        hex_col = hex_col.ljust(48)
                        ascii_col = ''.join(
                            chr(b) if 32 <= b <= 126 else '.'
                            for b in chunk
                        )
                        self.add(f"{offset:08x}  {hex_col}  {ascii_col}")
                        offset += len(chunk)
        except PermissionError:
            self.add(f"read: permission denied: '{path}'")
        except Exception as e:
            self.add(f"read: error reading '{path}': {e}")

    def move(self, source, destination):
        src = os.path.abspath(os.path.join(self.cwd, source))
        dst = os.path.abspath(os.path.join(self.cwd, destination))
        try:
            shutil.move(src, dst)
            self.add(f"Moved '{src}' -> '{dst}'")
        except FileNotFoundError:
            self.add(f"move: file not found: '{source}'")
        except PermissionError:
            self.add(f"move: permission denied: '{source}' or '{destination}'")
        except Exception as e:
            self.add(f"move: error moving '{source}' to '{destination}': {e}")

    def copy(self, source, destination):
        src = os.path.abspath(os.path.join(self.cwd, source))
        dst = os.path.abspath(os.path.join(self.cwd, destination))
        try:
            if os.path.isdir(src):
                self.add(f"copy: cannot copy directory: '{source}'")
                return
            shutil.copy2(src, dst)
            self.add(f"Copied '{src}' -> '{dst}'")
        except FileNotFoundError:
            self.add(f"copy: file not found: '{source}'")
        except PermissionError:
            self.add(f"copy: permission denied: '{source}' or '{destination}'")
        except Exception as e:
            self.add(f"copy: error copying '{source}' to '{destination}': {e}")

    def kill(self, process_name):
        try:
            result = subprocess.run(
                ["taskkill", "/F", "/IM", process_name],
                capture_output=True,
                text=True
            )
            output = (result.stdout or "") + (result.stderr or "")
            self.add(output.strip() or f"No output from taskkill for '{process_name}'")
        except FileNotFoundError:
            self.add("kill: system command not found on system")
        except Exception as e:
            self.add(f"kill: error terminating '{process_name}': {e}")

    def show_cwd(self):
        self.add(self.cwd)

    def show_history(self):
        if not self.history:
            self.add("No history available.")
            return
        for i, entry in enumerate(self.history):
            self.add(f"{i + 1}: {entry}")

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

        ansi_escape_pattern = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

        def _reader(pipe):
            for line in pipe:
                clean_line = ansi_escape_pattern.sub('', line).rstrip('\n')
                if clean_line:
                    self.add(clean_line)

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



def draw_layout(stdscr, tab):
    h, w = stdscr.getmaxyx()
    left = "Poly"
    pid, bold = tab.color_settings.get("logotext", (1, curses.A_BOLD))
    stdscr.addstr(0, 0, left, curses.color_pair(pid) | bold)
    now = datetime.datetime.now().strftime("%H:%M:%S")
    center_x = (w - len(now)) // 2
    pid, bold = tab.color_settings.get("clock", (1, curses.A_BOLD))
    stdscr.addstr(0, max(center_x, len(left) + 1), now,
                  curses.color_pair(pid) | bold)
    user_host = f"{getpass.getuser()}@{socket.gethostname()}"
    right_x = w - len(user_host)
    pid, bold = tab.color_settings.get("userinfo", (1, curses.A_BOLD))
    stdscr.addstr(0, max(right_x, len(left) + len(now) + 2), user_host,
                  curses.color_pair(pid) | bold)
    pid, bold = tab.color_settings.get("borders", (1, curses.A_NORMAL))
    border_attr = curses.color_pair(pid) | bold

    if VERTICAL_COL < w:
        stdscr.addstr(1, 0, "─" * VERTICAL_COL, border_attr)
        stdscr.addstr(1, VERTICAL_COL, "┬",       border_attr)
        stdscr.addstr(1, VERTICAL_COL + 1, "─" * (w - VERTICAL_COL - 1), border_attr)
    else:
        stdscr.addstr(1, 0, "─" * w, border_attr)
    for y in range(2, h):
        if VERTICAL_COL < w:
            stdscr.addch(y, VERTICAL_COL, curses.ACS_VLINE, border_attr)



def draw_sidebar(stdscr, tabs, current_idx):
    h, _ = stdscr.getmaxyx()
    width = VERTICAL_COL - 1
    for i, tab in enumerate(tabs):
        row = 2 + i
        if row >= h:
            break
        title = tab.name
        disp = (title[:width - 3] + "...") if len(title) > width else title
        if i == current_idx:
            pid, bold = tab.color_settings.get("currenttab", (0, curses.A_REVERSE))
        else:
            pid, bold = tab.color_settings.get("tab", (1, curses.A_NORMAL))
        attr = curses.color_pair(pid) | bold
        stdscr.addstr(row, 0, disp.ljust(width), attr)



def wrap_lines(lines, width):
    if width <= 0:
        return list(lines)
    out = []
    for line in lines:
        wrapped = textwrap.wrap(line, width, replace_whitespace=False)
        out.extend(wrapped if wrapped else [""])
    return out



def draw_messages(stdscr, tab):
    h, w = stdscr.getmaxyx()
    max_row = h - 2
    available = max_row - 2
    width = w - VERTICAL_COL - 1
    with tab.lock:
        wrapped = wrap_lines(tab.buffer, width)
        length = len(wrapped)
        offset = min(max(tab.scroll, 0), max(length - available, 0))
        start = max(length - available - offset, 0)
        msgs = wrapped[start:start + available]
    pid, bold = tab.color_settings.get("output", (1, curses.A_NORMAL))
    attr = curses.color_pair(pid) | bold
    for i, line in enumerate(msgs):
        y = 2 + i
        if y < max_row:
            stdscr.addnstr(y, VERTICAL_COL + 1, line, width, attr)



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
    curses.mousemask(curses.ALL_MOUSE_EVENTS)
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
    cwd = tabs[idx].cwd
    i = inp.rfind(' ')
    if i == -1:
        base, token = '', inp
    else:
        base, token = inp[:i+1], inp[i+1:]
    cmd = inp.strip().split(' ', 1)[0].lower()
    commands = ["tab", "run", "cd", "cwd", "files", "makedir", "deldir", "remove", "echo", "make", "download", "alias", "tree", "history", "color", "clear", "read", "move", "copy", "kill", "variable", "shutdown", "restart"]
    for command in CUSTOM_COMMANDS.keys():
        if not command.startswith("__"):
            commands.append(command)
    if not inp.strip():
        return commands
    if cmd in ('cd', 'run', 'deldir', 'remove', "read", "move", "copy"):
        sep = os.sep
        token_path = token
        if token_path.endswith(sep):
            dir_part = token_path
            prefix = ''
            dir_full = os.path.abspath(os.path.join(cwd, dir_part))
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
        return [o for o in commands if o.startswith(token)]
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
    if parts[0].lower() == "color":
        valid_things = [
            "borders", "logotext", "clock", "userinfo",
            "currenttab", "tab", "prompt", "input", "output"
        ]
        ansi_colors = [
            "black", "darkred", "darkgreen", "darkyellow",
            "darkblue", "darkmagenta", "darkcyan", "gray",
            "darkgray", "red", "green", "yellow",
            "blue", "magenta", "cyan", "white"
        ]
        if len(parts) == 1:
            opts = valid_things
        elif len(parts) == 2:
            opts = ansi_colors
        else:
            return []
        return [base + o for o in opts if o.startswith(token)]
    if parts[0].lower() == "alias":
        opts = commands
        return [base + o for o in opts if o.startswith(token)]
    return []

def handle_single_command(cmd_line, tabs, current):
    line = expand_variables(cmd_line, tabs[current])
    mode = tabs[current].mode
    if mode != 'poly':
        run = line.strip().lower()
        if run in ('cls', 'clear', 'clear-host'):
            tabs[current].clear()
        else:
            tabs[current].write_input(line)
        return current, False
    if not line.strip():
        return current, False
    if ' ' in line:
        cmd, rest = line.split(' ', 1)
    else:
        cmd, rest = line, ''
    lc = cmd.lower()
    if lc == "variable":
        if rest:
            parts = rest.split(' ', 1)
            name = parts[0]
            value = parts[1] if len(parts) > 1 else ''
            if not re.match(r'^[A-Za-z0-9_-]+$', name):
                tabs[current].add(f"Invalid variable name: {name}")
            else:
                variables[name] = value
                tabs[current].add(f"Variable '{name}' set to '{value}'")
        else:
            tabs[current].add("Usage: variable <name> <value>")
        return current, False
    if lc in ALIASES.keys():
        lc = ALIASES[lc]
    if lc in CUSTOM_COMMANDS.keys():
        CUSTOM_COMMANDS[lc](tabs[current], CUSTOM_COMMANDS[f"__{lc}_args"], rest)
        return current, False
    if lc in ("exit", "quit"):
        return current, True
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
                        return current, True
                    current = min(current, len(tabs) - 1)
            elif sub == "export":
                if arg:
                    found = next((t for t in tabs if t.name == arg), None)
                    if not found:
                        tabs[current].add(f"No tabs named '{arg}")
                    else:
                        export_log(found)
                else:
                    export_log(tabs[current])
            else:
                tabs[current].add("Usage: tab title <t> | mode <m> | create [t] | delete <t> | export [t]")
        return current, False
    if lc == "cd" and rest:
        tabs[current].cd(rest)
        return current, False
    if lc == "cwd" and not rest:
        tabs[current].show_cwd()
        return current, False
    if lc == "run" and rest:
        script_chars = []
        if rest.strip().endswith(".poly"):
            script_chars = read_poly_script(rest)
        else:
            tabs[current].run_exec(rest)
        return current, False, script_chars
    if lc == "makedir" and rest:
        tabs[current].makedir(rest)
        return current, False
    if lc == "deldir" and rest:
        tabs[current].deldir(rest)
        return current, False
    if lc == "history":
        tabs[current].show_history()
        return current, False
    if lc == "files":
        if rest:
            tabs[current].files(rest)
        else:
            tabs[current].files("")
        return current, False
    if lc == "remove" and rest:
        tabs[current].remove(rest)
        return current, False
    if lc == "echo":
        if rest:
            tabs[current].add(rest)
        else:
            tabs[current].add("\n")
        return current, False
    if lc == "make" and rest:
        tabs[current].make(rest)
        return current, False
    if lc == "download" and rest:
        try:
            parts = shlex.split(rest)
            url = parts[0]
            fname = parts[1] if len(parts) > 1 else None
            tabs[current].download(url, fname)
        except ValueError:
            tabs[current].add("Usage: download <url> \"<filename>\"")
        return current, False
    if lc == "shutdown" and not rest:
        if os.name == "nt":
            subprocess.run(["shutdown", "/s", "/t", "0"])
        else:
            subprocess.run(["shutdown", "now"])
        return current, False
    if lc == "restart" and not rest:
        if os.name == "nt":
            subprocess.run(["shutdown", "/r", "/t", "0"])
        else:
            subprocess.run(["reboot"])
        return current, False
    if lc == "alias" and rest:
        define_alias(rest.split()[0], rest.split()[1])
        return current, False
    if lc == "tree":
        try:
            parts = shlex.split(rest)
        except ValueError:
            tabs[current].add('Usage: tree "<dir>"')
            return current, False
        dir_arg = parts[0] if parts else None
        tabs[current].tree(dir_arg)
        return current, False
    if lc == "color":
        try:
            parts = shlex.split(rest)
        except ValueError:
            tabs[current].add('Usage: color <thingtocolor> <color>')
            return current, False
        if len(parts) != 2:
            tabs[current].add('Usage: color <thingtocolor> <color>')
            return current, False
        target, col = parts
        tabs[current].color(target, col)
        return current, False
    if lc == "clear":
        tabs[current].clear()
        return current, False
    if lc == "read" and rest:
        tabs[current].read(rest)
        return current, False
    if lc == "move" and rest:
        try:
            parts = shlex.split(rest)
            if len(parts) != 2:
                raise ValueError
            tabs[current].move(parts[0], parts[1])
        except ValueError:
            tabs[current].add("Usage: move <source> <destination>")
        return current, False
    if lc == "copy" and rest:
        try:
            parts = shlex.split(rest)
            if len(parts) != 2:
                raise ValueError
            tabs[current].copy(parts[0], parts[1])
        except ValueError:
            tabs[current].add("Usage: copy <source> <destination>")
        return current, False
    if lc == "kill" and rest:
        try:
            parts = shlex.split(rest)
            if len(parts) != 1:
                raise ValueError
            tabs[current].kill(parts[0])
        except ValueError:
            tabs[current].add("Usage: kill <processname>")
        return current, False
    tabs[current].add(f"Unknown: {cmd}")
    return current, False

def handle_command(cmd_line, tabs, current):
    if " | " in cmd_line and tabs[current].mode == "poly":
        if len(cmd_line.split(" | ")) < 2:
            tabs[current].add("Piping requires a second operand")
            return current, False
        
        buffer_len_before = len(tabs[current].buffer)
        current, should_exit, *script_chars = handle_single_command(cmd_line.split(" | ")[0], tabs, current)
        if should_exit:
            return current, True
        buffer_len_after = len(tabs[current].buffer)
        output_len = buffer_len_after - buffer_len_before
        output = "\n".join(tabs[current].buffer[-output_len:])
        output = output.replace("\\", "\\\\")
        tabs[current].buffer = tabs[current].buffer[:-output_len]

        try:
            commands = cmd_line.split(" | ")
            if len(commands) > 2:
                return handle_command(commands[1] + " " + output + " | " + " | ".join(commands[2:]), tabs, current)
            else:
                return handle_command(commands[1] + " " + output, tabs, current)
        except RecursionError:
            tabs[current].add("Pipe operation too deep")
            return current, False

    return handle_single_command(cmd_line, tabs, current)

def run_cli(stdscr):
    curses.curs_set(1)
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    stdscr.nodelay(True)
    curses.mousemask(curses.ALL_MOUSE_EVENTS)
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
    script_chars = read_polyrc()
    script_index = 0
    reading_script = True
    while True:
        h, w = stdscr.getmaxyx()
        width = w - (VERTICAL_COL + 1)
        stdscr.erase()
        draw_layout(stdscr, tabs[current])
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
        main_width = width
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
            if script_index >= len(script_chars):
                reading_script = False
                ch = stdscr.get_wch()
            else:
                ch = script_chars[script_index]
        except curses.error:
            time.sleep(0.05)
            continue
        if ch == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
            except Exception:
                continue
            tab = tabs[current]
            max_scroll = max(len(wrap_lines(tab.buffer, width)) - (h - 4), 0)
            if bstate & curses.BUTTON4_PRESSED:
                tab.scroll = min(tab.scroll + 1, max_scroll)
            elif bstate & curses.BUTTON5_PRESSED:
                tab.scroll = max(tab.scroll - 1, 0)
            continue
        if ch == curses.KEY_PPAGE:
            tab = tabs[current]
            max_scroll = max(len(wrap_lines(tab.buffer, width)) - (h - 4), 0)
            tab.scroll = min(tab.scroll + (h - 4), max_scroll)
            continue
        if ch == curses.KEY_NPAGE:
            tab = tabs[current]
            tab.scroll = max(tab.scroll - (h - 4), 0)
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
            script_index += 1
            line = inp
            inp = ""
            if line.strip():
                tabs[current].history.append(line)
            if not reading_script:
                tabs[current].add(f"> {line}")
            commands = [c.strip() for c in line.split('&&') if c.strip()]
            for cmd_line in commands:
                current, should_exit, *script_chars_2 = handle_command(cmd_line, tabs, current)
                if script_chars_2 and script_chars_2 != []:
                    script_chars = script_chars_2[0]
                    reading_script = True
                    script_index = 0

                if should_exit:
                    return
            continue
        if ch in (curses.KEY_BACKSPACE, "\b", "\x7f"):
            inp = inp[:-1]
            continue
        if isinstance(ch, str) and ch.isprintable():
            inp += ch
            script_index += 1

def read_polyrc():
    return read_poly_script("~/.polyrc")

def read_poly_script(path):
    try:
        chars = []
        with open(os.path.expanduser(path), "r") as scriptfile:
            for line in scriptfile.readlines():
                if line.startswith("#") or line == "\n" or line == "":
                    continue
                for char in list(line):
                    chars.append(char)
        chars.append("\n")
        return chars
    except FileNotFoundError:
        return []

def read_poly_script_nosplit(path):
    try:
        with open(os.path.expanduser(path), "r") as scriptfile:
            return scriptfile.read()
    except FileNotFoundError:
        return 1

def run_commands(cmds):
    global CLI_MODE
    CLI_MODE = True
    tabs = [Tab()]
    current = 0
    for line in cmds.splitlines():
        if not line.strip():
            continue
        print(f"> {line}")
        commands = [c.strip() for c in line.split('&&') if c.strip()]
        for cmd_line in commands:
            current, should_exit = handle_single_command(cmd_line, tabs, current)
            if should_exit:
                return

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-c', '--command', help='Run commands and exit')
    group.add_argument('scriptname', help='Run a script file', nargs='?')
    args = parser.parse_args()
    if args.command:
        run_commands(args.command)
    elif args.scriptname:
        content = read_poly_script_nosplit(args.scriptname)
        if content == 1:
            print(f"File not found: {args.scriptname}")
            return
        run_commands(content)
    else:
        try:
            curses.wrapper(run_cli)
        except KeyboardInterrupt:
            pass



if __name__ == "__main__":
    main()
