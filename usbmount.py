#!/usr/bin/env python3
import curses
import json
import subprocess
import sys


def run(cmd):
    return subprocess.check_output(cmd, text=True)


def load_lsusb():
    try:
        return run(["lsusb"]).strip().splitlines()
    except Exception as exc:
        return [f"lsusb error: {exc}"]


def load_lsblk():
    try:
        raw = run(
            [
                "lsblk",
                "-J",
                "-o",
                "NAME,KNAME,PATH,TYPE,SIZE,FSTYPE,MOUNTPOINT,LABEL,MODEL,TRAN,UUID,SERIAL",
            ]
        )
        data = json.loads(raw)
        return data.get("blockdevices", [])
    except Exception as exc:
        return [{"error": f"lsblk error: {exc}"}]


def _inherit_attrs(node, parent):
    if not parent:
        return node
    for key in ("model", "tran", "serial"):
        if not node.get(key):
            node[key] = parent.get(key)
    return node


def flatten_nodes(nodes, parent=None):
    items = []
    for node in nodes:
        if "error" in node:
            items.append(node)
            continue
        node = _inherit_attrs(node, parent)
        items.append(node)
        for child in node.get("children", []) or []:
            items.extend(flatten_nodes([child], node))
    return items


def build_mount_command(dev, mountpoint, fstype=None):
    base = f"sudo mount {dev} {mountpoint}"
    if fstype:
        return f"sudo mount -t {fstype} {dev} {mountpoint}"
    return base


def sanitize_label(label):
    if not label:
        return ""
    safe = []
    for ch in label:
        if ch.isalnum():
            safe.append(ch.lower())
        elif ch in (" ", "-", "_"):
            safe.append("_")
    return "".join(safe).strip("_")


def default_mountpoint(part):
    label = sanitize_label(part.get("label") or "")
    if label:
        return f"/mnt/{label}"
    return "/mnt/usb"


def draw_main(stdscr, lsusb_lines, parts, selected, mountpoint, focus, message):
    stdscr.erase()
    height, width = stdscr.getmaxyx()

    title = "USB Storage Helper"
    stdscr.addstr(0, 0, title[: width - 1])

    row = 2
    stdscr.addstr(row, 0, "lsusb:")
    row += 1
    max_lsusb = max(1, min(5, height // 4))
    for line in lsusb_lines[:max_lsusb]:
        stdscr.addstr(row, 2, line[: width - 3])
        row += 1

    row += 1
    stdscr.addstr(row, 0, "USB partitions (select with arrows):")
    row += 1

    list_height = height - row - 5
    start = max(0, selected - list_height + 1)
    visible = parts[start : start + list_height]
    for idx, part in enumerate(visible):
        row_idx = row + idx
        prefix = ">" if start + idx == selected else " "
        if "error" in part:
            line = part["error"]
        else:
            path = part.get("path", "")
            size = part.get("size", "")
            fstype = part.get("fstype") or "-"
            mnt = part.get("mountpoint") or "-"
            label = part.get("label") or "-"
            model = part.get("model") or "-"
            line = f"{path}  {size}  {fstype}  {mnt}  {label}  {model}"
        stdscr.addstr(row_idx, 0, (prefix + " " + line)[: width - 1])

    row = height - 3
    current = parts[selected] if parts else {}
    mounted = current.get("mountpoint")
    if mounted:
        mp_line = f"mounted at: {mounted}"
    else:
        mp_label = "mountpoint"
        mp_indicator = "*" if focus == "mountpoint" else ""
        mp_line = f"{mp_label}{mp_indicator}: {mountpoint}"
    stdscr.addstr(row, 0, mp_line[: width - 1])

    footer = "Enter=print cmd  Tab=focus  q=quit"
    stdscr.addstr(height - 2, 0, footer[: width - 1])
    if message:
        stdscr.addstr(height - 1, 0, message[: width - 1])

    stdscr.refresh()


def is_printable(key):
    if isinstance(key, str):
        return key.isprintable()
    return 32 <= key <= 126


def read_key(stdscr):
    try:
        return stdscr.get_wch()
    except curses.error:
        return None


def wizard(stdscr, parts):
    lsusb_lines = load_lsusb()
    selected = 0
    message = ""
    focus = "list"
    mountpoint = ""
    mountpoints = {}
    last_path = None

    while True:
        if not parts:
            parts = [{"error": "No USB partitions found"}]
        selected = min(selected, max(0, len(parts) - 1))
        current = parts[selected]
        path = current.get("path")
        if path != last_path:
            if current.get("mountpoint"):
                mountpoint = ""
            else:
                mountpoint = mountpoints.get(path, default_mountpoint(current))
            last_path = path
        draw_main(stdscr, lsusb_lines, parts, selected, mountpoint, focus, message)
        message = ""
        key = read_key(stdscr)
        if key is None:
            continue
        if key in (ord("q"), 27):
            return None
        if key == "\t":
            focus = "mountpoint" if focus == "list" else "list"
            continue
        if key in (curses.KEY_UP, "k"):
            if focus == "list":
                selected = max(0, selected - 1)
            continue
        if key in (curses.KEY_DOWN, "j"):
            if focus == "list":
                selected = min(len(parts) - 1, selected + 1)
            continue
        if key in (curses.KEY_ENTER, "\n", "\r"):
            if "error" in current:
                message = "Selection is not a device"
                continue
            if current.get("mountpoint"):
                return f"sudo umount {current.get('path')}"
            return build_mount_command(current.get("path"), mountpoint, current.get("fstype"))

        if current.get("mountpoint"):
            continue
        if focus == "mountpoint":
            if key in (curses.KEY_BACKSPACE, "\b", "\x7f"):
                mountpoint = mountpoint[:-1]
            elif is_printable(key):
                mountpoint += key if isinstance(key, str) else chr(key)
            if path:
                mountpoints[path] = mountpoint
            continue
        if focus == "list" and is_printable(key):
            focus = "mountpoint"
            mountpoint = mountpoint + (key if isinstance(key, str) else chr(key))
            if path:
                mountpoints[path] = mountpoint


def main(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    parts = []
    for node in flatten_nodes(load_lsblk()):
        if "error" in node:
            parts.append(node)
            continue
        if node.get("type") != "part":
            continue
        if node.get("tran") != "usb":
            continue
        parts.append(node)
    command = wizard(stdscr, parts)
    if not command:
        return ""
    return command


def run_tui():
    command = curses.wrapper(main)
    if command:
        print(command)


if __name__ == "__main__":
    run_tui()
