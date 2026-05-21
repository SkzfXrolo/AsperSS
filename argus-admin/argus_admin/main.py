import sys
from .gui import run_gui


def main() -> int:
    run_gui()
    return 0


if __name__ == '__main__':
    sys.exit(main())
