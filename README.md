# aula-f108-gui

Configure the Aula F108 Pro keyboard on Linux. The official software only runs
on Windows.

This is a work in progress. So far there is a command line tool; a GTK app is
being built on top of it.

## What it can do

- switch between the 20 built-in backlight effects and set colour, brightness,
  speed and direction
- set the clock on the keyboard's screen

Planned: per-key colours and key remapping.

## Requirements

- Python 3.10 or newer, nothing else
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

Run from the checkout:

```
python3 -m aula_f108 status
python3 -m aula_f108 light breath --color ff0080 --brightness 4
python3 -m aula_f108 light rolling --rainbow --speed 2
python3 -m aula_f108 light off
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
