#!/usr/bin/env python3
"""Small Zotero bridge for CVPR 2026 paper imports.

This wrapper keeps Zotero-specific operations separate from the paper
summarization pipeline. It uses the Zotero helper shipped with the local Codex
Zotero plugin for Desktop Connector import operations.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import cvpr2026_summarize as cvpr


DEFAULT_ZOTERO_HELPER = (
    Path.home()
    / ".codex/plugins/cache/openai-curated/zotero/7fd3161c/skills/zotero/scripts/zotero.py"
)
DEFAULT_ZOTERO_DIR = Path("data/zotero")


def build_helper_command(python_cmd: Path, helper: Path, *args: str) -> list[str]:
    return [str(python_cmd), str(helper), *args]


def run_helper(args: argparse.Namespace, *helper_args: str) -> int:
    helper = args.helper.expanduser().resolve()
    if not helper.exists():
        raise RuntimeError(f"Zotero helper not found: {helper}")
    cmd = build_helper_command(Path(sys.executable), helper, *helper_args)
    return subprocess.run(cmd, check=True).returncode


def category_ris_path(zotero_dir: Path, category: str) -> Path:
    names = cvpr.parse_category_selection(category)
    if len(names) != 1:
        raise RuntimeError(f"expected exactly one category, got {len(names)}: {category}")
    return zotero_dir / "by_category" / cvpr.safe_path_name(names[0]) / "import.ris"


def limited_ris_path(ris_path: Path, limit: int) -> Path:
    return ris_path.with_name(f"{ris_path.stem}.limit{limit}{ris_path.suffix}")


def split_ris_entries(text: str) -> list[str]:
    entries: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.strip() == "TY  - CONF" and current:
            entries.append("\n".join(current).strip() + "\n")
            current = []
        current.append(line)
        if line.strip() == "ER  -":
            entries.append("\n".join(current).strip() + "\n")
            current = []
    if current:
        entries.append("\n".join(current).strip() + "\n")
    return [entry for entry in entries if entry.strip()]


def write_limited_ris(source: Path, target: Path, limit: int) -> int:
    if limit < 1:
        raise RuntimeError("--limit must be >= 1")
    entries = split_ris_entries(source.read_text(encoding="utf-8"))
    selected = entries[:limit]
    target.write_text("\n".join(selected), encoding="utf-8")
    return len(selected)


def prepare_category(args: argparse.Namespace) -> None:
    summarize_args = argparse.Namespace(
        categories=args.category,
        categories_path=args.categories_path,
        zotero_dir=args.zotero_dir,
        pdf_dir=args.pdf_dir,
        output=args.output,
    )
    cvpr.prepare_zotero_import_by_category(summarize_args)


def import_category(args: argparse.Namespace) -> None:
    if args.prepare:
        prepare_category(args)
    ris_path = category_ris_path(args.zotero_dir, args.category)
    if not ris_path.exists():
        raise RuntimeError(
            f"RIS file not found: {ris_path}. Run prepare-category first or pass --prepare."
        )
    if args.limit:
        limited_path = limited_ris_path(ris_path, args.limit)
        count = write_limited_ris(ris_path, limited_path, args.limit)
        print(f"Importing {count} of {args.limit} requested entries from {limited_path}")
        ris_path = limited_path
    run_helper(args, "import-ris", "--file", str(ris_path), "--yes")


def status(args: argparse.Namespace) -> None:
    helper_args = ["status"]
    if args.json:
        helper_args.append("--json")
    run_helper(args, *helper_args)


def selected_target(args: argparse.Namespace) -> None:
    helper_args = ["selected-target"]
    if args.json:
        helper_args.append("--json")
    run_helper(args, *helper_args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Zotero bridge for CVPR 2026 imports.")
    parser.add_argument("--helper", type=Path, default=DEFAULT_ZOTERO_HELPER)
    parser.add_argument("--zotero-dir", type=Path, default=DEFAULT_ZOTERO_DIR)
    parser.add_argument("--categories-path", type=Path, default=cvpr.DEFAULT_CATEGORIES_PATH)
    parser.add_argument("--pdf-dir", type=Path, default=Path("data/pdfs"))
    parser.add_argument("--output", type=Path, default=Path("summaries"))
    subcommands = parser.add_subparsers(dest="command", required=True)

    status_cmd = subcommands.add_parser("status", help="Show Zotero Connector/local API status")
    status_cmd.add_argument("--json", action="store_true")
    status_cmd.set_defaults(func=status)

    target_cmd = subcommands.add_parser(
        "selected-target", help="Show the currently selected Zotero library/collection"
    )
    target_cmd.add_argument("--json", action="store_true")
    target_cmd.set_defaults(func=selected_target)

    prepare_cmd = subcommands.add_parser(
        "prepare-category", help="Write the category-specific RIS file"
    )
    prepare_cmd.add_argument("category", help="CVPR category index or exact category name")
    prepare_cmd.set_defaults(func=prepare_category)

    import_cmd = subcommands.add_parser(
        "import-category", help="Import one category RIS into the selected Zotero target"
    )
    import_cmd.add_argument("category", help="CVPR category index or exact category name")
    import_cmd.add_argument(
        "--prepare", action="store_true", help="Regenerate the category RIS before importing"
    )
    import_cmd.add_argument("--limit", type=int, help="Import only the first N RIS entries")
    import_cmd.set_defaults(func=import_category)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = args.func(args)
    return 0 if result is None else int(result)


if __name__ == "__main__":
    raise SystemExit(main())
