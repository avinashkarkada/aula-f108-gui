# aula-f108-gui

Configure the Aula F108 Pro keyboard on Linux. The official software only runs
on Windows.

There is a small GTK app and a command line tool. Still a work in progress.

## What it can do

- switch between the 20 built-in backlight effects and set colour, brightness,
  speed and direction
- paint individual keys in any colour
- set the clock on the keyboard's screen

Planned: key remapping.

## Requirements

- Python 3.10 or newer
- GTK 4 and libadwaita with their Python bindings for the app. On Ubuntu:
  `sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1`. The command line
  tool needs nothing besides Python.
- the keyboard connected with the USB cable and switched to USB mode. Settings
  can't be written over the 2.4G receiver or Bluetooth, but once written they
  stay on the keyboard and keep working wirelessly.

## Setup

Install the udev rule so the keyboard can be reached without root, then unplug
and replug the cable:

```
sudo cp udev/70-aula-f108.rules /etc/udev/rules.d/
sudo udevadm control --reload
```

## Usage

Run from the checkout. Without arguments the app opens:

```
python3 -m aula_f108
```

With arguments it works as a command line tool:

```
python3 -m aula_f108 status
python3 -m aula_f108 light breath --color ff0080 --brightness 4
python3 -m aula_f108 light rolling --rainbow --speed 2
python3 -m aula_f108 light off
python3 -m aula_f108 paint w=00ff00 a=00ff00 s=00ff00 d=00ff00 --all 202020
python3 -m aula_f108 clock
```

`--dry-run` prints the packets instead of sending them.

## Good to know

- The keyboard can't be asked for its current settings, it only accepts new
  ones.
- The light bar above the arrow keys and the side lights aren't reachable from
  software. Use the Fn shortcuts from the manual for those.

## Tests

```
python3 -m pytest
```

## Credits

The protocol was worked out by Parsia Hakimian in
[parsiya/f108-pro](https://github.com/parsiya/f108-pro). This project
reimplements the parts it needs in Python based on those notes.

## License

MIT
