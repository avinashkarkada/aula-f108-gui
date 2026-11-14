import sys


def main():
    from .app import Application
    return Application().run(sys.argv[:1])
