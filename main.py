#!/usr/bin/env python3
import sys

from app import NotaApplication


def main():
    app = NotaApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
