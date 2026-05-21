import sys
import traceback
from pathlib import Path


def _install_crash_log() -> None:
    log_dir = Path(__import__('os').environ.get('APPDATA', '.')) / 'ArgusAdmin'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'crash.log'

    def _hook(exc_type, exc, tb):
        try:
            log_file.write_text(
                ''.join(traceback.format_exception(exc_type, exc, tb)),
                encoding='utf-8',
            )
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook


def main() -> int:
    _install_crash_log()
    from .gui import run_gui
    run_gui()
    return 0


if __name__ == '__main__':
    sys.exit(main())
