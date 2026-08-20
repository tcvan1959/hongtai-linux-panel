"""Preview or install experimental, unsupported automatic dashboard startup."""

from __future__ import annotations

import argparse

from .config import default_config_path
from .user_service import install_user_service, render_user_unit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Experimental unsupported systemd user service; not part of accepted v1"
        )
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help=(
            "write files and enable an unsupported experimental service; "
            "omission is preview-only"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.install:
        print("Preview only; no files or services were changed.\n")
        print(f"Configuration: {default_config_path()}")
        print(render_user_unit())
        return 0

    config_path, unit_path = install_user_service()
    print(f"Configuration: {config_path}")
    print(f"User service: {unit_path}")
    print("Hongtai dashboard enabled for automatic login startup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
