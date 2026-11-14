import argparse
import datetime
import sys

from . import device, keys, protocol, wireless
from . import remap as remapping


def _effect(value):
    if value.isdigit():
        return int(value)
    wanted = value.lower().replace(" ", "").replace("-", "")
    for e in protocol.EFFECTS:
        if e.name.lower().replace(" ", "") == wanted:
            return e.id
    names = ", ".join(e.name.lower().replace(" ", "") for e in protocol.EFFECTS)
    raise argparse.ArgumentTypeError(f"unknown effect, pick one of: {names}")


def _color(value):
    value = value.lstrip("#")
    if len(value) != 6:
        raise argparse.ArgumentTypeError("colour should look like ff8800")
    try:
        return tuple(bytes.fromhex(value))
    except ValueError:
        raise argparse.ArgumentTypeError("colour should look like ff8800")


def _key_color(value):
    name, sep, color = value.partition("=")
    if not sep or name.lower() not in keys.BY_NAME:
        raise argparse.ArgumentTypeError(
            f"expected KEY=COLOUR with a known key name, got {value!r}")
    return keys.BY_NAME[name.lower()].index, _color(color)


class _Printer(device._Base):
    """Stands in for the keyboard with --dry-run: prints what would go out."""

    def __init__(self, packets):
        self._packets = packets

    def send(self, packets, progress=None):
        for packet in packets:
            if isinstance(packet, bytes):
                print(packet.hex(" "))
            else:
                tail = "  <- read back" if packet.readback else ""
                print(packet.payload.hex(" ") + tail)


def _run(job, args):
    if args.dry_run:
        job(_Printer(wireless if args.receiver else protocol))
    else:
        device.run(job)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="aula-f108", description="Configure an Aula F108 Pro keyboard.")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the packets instead of sending them")
    parser.add_argument("--receiver", action="store_true",
                        help="with --dry-run, show the packets for the 2.4G "
                             "receiver instead of the cable")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="check that the keyboard can be reached")

    light = sub.add_parser("light", help="set a backlight effect")
    light.add_argument("effect", type=_effect, help="effect name or number")
    light.add_argument("-c", "--color", type=_color, default=(255, 255, 255))
    light.add_argument("-b", "--brightness", type=int, default=5)
    light.add_argument("-s", "--speed", type=int, default=3)
    light.add_argument("-r", "--reverse", action="store_true")
    light.add_argument("--rainbow", action="store_true")

    paint = sub.add_parser("paint", help="set colours for individual keys")
    paint.add_argument("keys", nargs="*", type=_key_color, metavar="KEY=COLOUR",
                       help="for example w=00ff00 esc=ff0000")
    paint.add_argument("--all", type=_color, metavar="COLOUR",
                       help="colour for every key not listed")
    paint.add_argument("-b", "--brightness", type=int, default=5)

    remap = sub.add_parser(
        "remap", help="change what keys send (replaces all earlier remaps)")
    remap.add_argument("bindings", nargs="*", metavar="KEY=TARGET",
                       help="for example capslock=lctrl f1=media:play "
                            "pause=ctrl+shift+c")
    remap.add_argument("--reset", action="store_true",
                       help="put every key back to normal")

    sub.add_parser("clock", help="set the screen clock to the current time")

    args = parser.parse_args(argv)

    try:
        if args.command == "status":
            def report(kb):
                if kb.kind == device.USB:
                    print(f"keyboard ready on {kb.path} (USB cable)")
                    return
                level = kb.battery()
                charge = f", battery {level}%" if level is not None else ""
                print(f"keyboard ready on {kb.path} (2.4G receiver{charge})")
            device.run(report)
        elif args.command == "light":
            _run(lambda kb: kb.lighting(args.effect, args.color,
                                        args.brightness, args.speed,
                                        args.reverse, args.rainbow), args)
        elif args.command == "paint":
            table = {}
            if args.all:
                table = {k.index: args.all for k in keys.KEYS}
            table.update(args.keys)
            _run(lambda kb: kb.per_key(table, args.brightness), args)
        elif args.command == "remap":
            if bool(args.bindings) == args.reset:
                parser.error("give some KEY=TARGET pairs, or --reset")
            bindings = {}
            for pair in args.bindings:
                name, sep, target = pair.partition("=")
                if not sep:
                    parser.error(f"expected KEY=TARGET, got {pair!r}")
                bindings[name.lower()] = target
            slots = remapping.table(bindings)
            _run(lambda kb: kb.remap(slots), args)
        elif args.command == "clock":
            _run(lambda kb: kb.clock(datetime.datetime.now()), args)
    except (device.KeyboardError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
