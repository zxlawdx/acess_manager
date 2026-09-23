#!/usr/bin/env python
import os
import sys


BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

sys.path.insert(
    0,
    BASE_DIR
)

from vela.cli.commands import CommandRunner


def main():
    runner = CommandRunner()
    runner.execute(
        sys.argv[1:]
    )


if __name__ == "__main__":
    main()
