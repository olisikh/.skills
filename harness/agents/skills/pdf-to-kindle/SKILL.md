---
name: pdf-to-kindle
description: Convert local PDFs into reflowable EPUB and Kindle-compatible AZW3 for Paperwhite devices.
version: 1.0.0
author: Oleksii + Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [PDF, EPUB, AZW3, Kindle, Paperwhite, Calibre]
---

# PDF to Kindle

Use this skill when Oleksii asks to convert one or more local PDFs for a Kindle, especially a first-generation Paperwhite (EY21).

## What the outputs mean

- **EPUB** is the reflowable source to upload through Send to Kindle or send to a Kindle document address. Amazon converts it for the account/device when that service supports the device.
- **AZW3** is the reflowable Kindle file to sideload over USB. It is the preferred direct-transfer artifact for a Paperwhite 1; EPUB is not a reliable USB format on that generation.
- Do not call either file “KFX.” KFX is an Amazon-delivery format, not what this local converter creates.

## Workflow

1. Preserve the source PDF. Never delete or overwrite it.
2. Inspect the PDF enough to identify its title/author and whether it contains selectable text. If it is image-only/scanned, route through OCR before conversion; do not pretend a normal PDF conversion produced a good reflow.
3. Ensure Calibre's `ebook-convert` is available. On macOS, the normal installation is:
   ```bash
   brew install --cask calibre
   ```
4. Run the bundled deterministic wrapper. For a normal book, produce both artifacts:
   ```bash
   python scripts/pdf_to_kindle.py book.pdf \
     --format both \
     --title "Book Title" \
     --authors "Author Name"
   ```
   Use `--output-dir` for a separate destination and `--force` only when intentionally replacing files.
5. Verify the wrapper's checks. It checks EPUB ZIP integrity and text presence, and checks the AZW3/MOBI container marker. Also inspect metadata with `ebook-meta` when the title or author matters.
6. Deliver the requested artifact(s) directly. In Telegram, include `MEDIA:/absolute/path/to/file` for each file; do not claim conversion succeeded without real output paths.

## Hard guards

- Never modify the input PDF.
- Never overwrite an existing output unless `--force` is explicit.
- Never remove DRM, bypass access controls, or upload/send a book to Amazon without a separate explicit request.
- Keep the conversion deterministic: PDF → EPUB, then EPUB → AZW3/MOBI. Do not switch to screenshot/page-image output unless the user asks for a fixed-layout copy.
- If Calibre fails on a complex or scanned PDF, report the real error and offer OCR or a fixed-layout PDF instead of silently degrading the book.

## Verification checklist

A successful run must have:

- the source PDF still present;
- a valid, readable EPUB when requested;
- an AZW3 with a `BOOKMOBI` container marker when requested;
- title/author metadata checked when supplied or important;
- absolute output paths ready for delivery.

The wrapper is in `scripts/pdf_to_kindle.py`; keep changes to the conversion policy there rather than duplicating shell recipes in this file.
