#!/usr/bin/env python3
import sys

from app import NotaApplication


def main():
    launched_via_autostart = "--autostart" in sys.argv
    argv = [a for a in sys.argv if a != "--autostart"]
    app = NotaApplication(launched_via_autostart=launched_via_autostart)
    return app.run(argv)


if __name__ == "__main__":
    sys.exit(main())
