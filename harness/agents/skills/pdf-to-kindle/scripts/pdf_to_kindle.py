#!/usr/bin/env python3
"""Deterministic Calibre wrapper for making Kindle-friendly ebook files from PDFs."""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import zipfile
from pathlib import Path


OUTPUT_EXTENSIONS = {
    "epub": ("epub",),
    "azw3": ("azw3",),
    "mobi": ("mobi",),
    "both": ("epub", "azw3"),
}


def fail(message: str) -> "NoReturn":
    print(f"pdf-to-kindle: error: {message}", file=sys.stderr)
    raise SystemExit(2)


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    result = re.sub(r"[^A-Za-z0-9]+", "-", normalized).strip("-").lower()
    return result or "book"


def find_ebook_convert() -> str | None:
    candidates = []
    override = shutil.which("ebook-convert")
    if override:
        candidates.append(override)
    candidates.extend(
        [
            "/Applications/calibre.app/Contents/MacOS/ebook-convert",
            "/opt/homebrew/bin/ebook-convert",
            "/usr/local/bin/ebook-convert",
        ]
    )
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.is_file() and path.stat().st_mode & 0o111:
            return str(path)
    return None


def run_conversion(
    converter: str,
    source: Path,
    target: Path,
    profile: str,
    title: str | None,
    authors: str | None,
) -> None:
    command = [converter, str(source), str(target), "--output-profile", profile]
    if title:
        command.extend(["--title", title])
    if authors:
        command.extend(["--authors", authors])
    print("$ " + " ".join(_quote(arg) for arg in command))
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError:
        fail(f"Calibre converter not found: {converter}")
    except subprocess.CalledProcessError as exc:
        fail(f"Calibre conversion failed with exit code {exc.returncode}")


def _quote(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:-]+", value):
        return value
    return repr(value)


def validate_epub(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            broken = archive.testzip()
            if broken:
                fail(f"EPUB ZIP integrity check failed at {broken}")
            names = set(archive.namelist())
            required = {"mimetype", "META-INF/container.xml"}
            missing = sorted(required - names)
            if missing:
                fail(f"EPUB is missing required entries: {', '.join(missing)}")
            text_entries = [name for name in names if name.lower().endswith((".xhtml", ".html"))]
            text = "\n".join(archive.read(name).decode("utf-8", "ignore") for name in text_entries)
            visible = re.sub(r"<[^>]+>", " ", text)
            visible = re.sub(r"\s+", " ", visible).strip()
            if len(visible) < 1000:
                fail("EPUB contains too little readable text; conversion may have failed")
    except zipfile.BadZipFile as exc:
        fail(f"EPUB is not a valid ZIP container: {exc}")


def validate_kindle(path: Path) -> None:
    data = path.read_bytes()
    if len(data) < 4096 or b"BOOKMOBI" not in data[:256]:
        fail("Kindle output is not a recognizable MOBI/AZW container")


def validate(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        fail(f"expected output was not created: {path}")
    if path.suffix.lower() == ".epub":
        validate_epub(path)
    elif path.suffix.lower() in {".azw3", ".mobi"}:
        validate_kindle(path)
    else:
        fail(f"unsupported output extension for validation: {path.suffix}")
    print(f"OK  {path} ({path.stat().st_size:,} bytes)")


def default_title(source: Path) -> str:
    return re.sub(r"[_.]+", " ", source.stem).strip() or "Book"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a PDF to EPUB, AZW3, or MOBI using Calibre's reflowable pipeline."
    )
    parser.add_argument("pdf", type=Path, help="input PDF")
    parser.add_argument(
        "--format",
        choices=sorted(OUTPUT_EXTENSIONS),
        default="both",
        help="output format (default: both = EPUB + AZW3)",
    )
    parser.add_argument("--output-dir", type=Path, help="destination directory (default: next to the PDF)")
    parser.add_argument("--name", help="output basename without extension")
    parser.add_argument("--title", help="book title passed to Calibre")
    parser.add_argument("--authors", help="author string passed to Calibre")
    parser.add_argument("--profile", default="kindle_pw", help="Calibre output profile (default: kindle_pw)")
    parser.add_argument("--force", action="store_true", help="replace existing output files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.pdf.expanduser().resolve()
    if not source.is_file():
        fail(f"input file does not exist: {source}")
    if source.suffix.lower() != ".pdf":
        fail(f"input must have a .pdf extension: {source}")

    converter = find_ebook_convert()
    if converter is None:
        fail("Calibre's ebook-convert was not found; install Calibre and retry")

    title = args.title or default_title(source)
    output_dir = (args.output_dir or source.parent).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    base = args.name or slugify(title)
    extensions = OUTPUT_EXTENSIONS[args.format]
    outputs = {ext: output_dir / f"{base}.{ext}" for ext in extensions}
    for path in outputs.values():
        if path.exists() and not args.force:
            fail(f"output already exists (use --force to replace): {path}")
        if path.resolve() == source:
            fail("refusing to overwrite the input PDF")
        if args.force and path.exists():
            path.unlink()

    with tempfile.TemporaryDirectory(prefix="pdf-to-kindle-") as temp_dir:
        temp = Path(temp_dir)
        epub = outputs.get("epub") or temp / f"{base}.epub"
        run_conversion(converter, source, epub, args.profile, title, args.authors)
        if "epub" in outputs:
            validate(epub)

        for ext in extensions:
            if ext == "epub":
                continue
            target = outputs[ext]
            run_conversion(converter, epub, target, args.profile, title, args.authors)
            validate(target)

    print("Completed without modifying the source PDF:")
    for path in outputs.values():
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
