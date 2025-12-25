# usbmount TUI

Minimal TUI to combine `lsusb`, `lsblk`, and a mount command in one place.

## Run

```bash
# If you installed it:
usbmount

# Or run directly from the file:
python3 usbmount.py
```

## Install (generic, no sudo)

Option A: copy from your local machine (over SSH):

```bash
# local machine
scp /path/to/usbmount.py user@server:~/usbmount.py

# on the server
mkdir -p ~/.local/bin
cp ~/usbmount.py ~/.local/bin/usbmount
chmod +x ~/.local/bin/usbmount
usbmount
```

Option B: download from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/josephma93/usbmount/refs/heads/main/usbmount.py -o ~/usbmount.py
mkdir -p ~/.local/bin
cp ~/usbmount.py ~/.local/bin/usbmount
chmod +x ~/.local/bin/usbmount
usbmount
```

## Keys

- Up/Down or j/k: select USB partition
- Tab: switch focus between list and mountpoint input
- Type: edit mountpoint (or start typing to focus it)
- Enter: print command and exit (mount or umount auto-detected)
- q or Esc: quit
