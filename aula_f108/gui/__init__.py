import sys


def main():
    from gi.repository import GLib

    from .app import APP_ID, Application

    # makes the window match the launcher entry, so the dock shows our icon
    GLib.set_prgname(APP_ID)
    return Application().run(sys.argv[:1])
