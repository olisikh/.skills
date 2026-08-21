---
name: kindle-transfer
description: Transfer files to Oleksii's Kindle over SSH.
version: 0.1.0
author: Oleksii, Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [Kindle, Paperwhite, SSH, SCP, Screensavers]
    related_skills: [pdf-to-kindle]
---

# Kindle Transfer Skill

Use this skill to send files to Oleksii's jailbroken Kindle Paperwhite 1 over its fixed LAN SSH connection. It handles transfer and verification only; PDF conversion belongs to `pdf-to-kindle`.

## When to Use

- Send an image to the Kindle screensaver directory.
- Send a Kindle-ready book or another document to the Kindle over SSH.
- Verify that a transferred file is present and byte-identical.

Do not use it for jailbreaks, firmware changes, account changes, DRM removal, or files outside the Kindle's user storage unless Oleksii explicitly requests that scope.

## Device Defaults

- Model: Kindle Paperwhite 1 / EY21.
- SSH host: `192.168.2.43` (fixed LAN address).
- SSH port: `2222`.
- SSH user: `root`.
- Authentication: use the configured OpenSSH key; never copy or print the private key.
- Screensavers: `/mnt/us/Screensavers/`.
- Books and documents: `/mnt/us/documents/`.

These are defaults for Oleksii's device. If the connection fails, verify reachability and the live SSH port before changing anything; do not silently fall back to port 22 or another host.

## Procedure

1. **Classify the file.** Use `/mnt/us/Screensavers/` for screensaver images and `/mnt/us/documents/` for books/documents. Preserve the source extension unless Oleksii requests a different output format or filename. Completion criterion: the exact remote path and final filename are known.
2. **Prepare the artifact.** Preserve the local source. If the source is a PDF and a Kindle-native book is requested, run `pdf-to-kindle` first and transfer its verified AZW3; do not silently upload a raw PDF instead. Completion criterion: the intended local file exists and is the file being sent.
3. **Preflight SSH and destination.** Use `terminal` with `ssh -p 2222 -o BatchMode=yes root@192.168.2.43` to confirm the device, then check that the target directory exists. If the exact target already exists, stop and ask before overwriting it. Completion criterion: SSH authentication succeeds, the destination exists, and no unapproved overwrite is pending.
4. **Transfer once.** Use `terminal` with `scp -P 2222` and the configured key selection, quoting local and remote path arguments. Write only below `/mnt/us/`. Completion criterion: `scp` exits successfully.
5. **Verify bytes.** Compute the local SHA-256 with `shasum -a 256`. Compute the remote SHA-256 over SSH with `sha256sum` (or `busybox sha256sum` if needed), and compare the hashes. Also report the remote path and byte count. Completion criterion: hashes match exactly.
6. **Report the real result.** Give the exact remote path and verification result. Do not claim delivery from a successful SSH connection alone; the hash check is required.

## Quick Reference

```text
ssh -p 2222 root@192.168.2.43
scp -P 2222 SOURCE root@192.168.2.43:/mnt/us/Screensavers/NAME.ext
scp -P 2222 SOURCE root@192.168.2.43:/mnt/us/documents/NAME.ext
```

Use the `terminal` tool for these commands. Keep host-key checking enabled and use shell-quoted paths; never disable authentication checks with `StrictHostKeyChecking=no` or copy a private key to the Kindle.

## Pitfalls

- Port `22` is not the configured service for this device; use `2222`.
- `root` is the authenticated SSH account even though the local macOS username may differ.
- A successful `scp` does not prove the file was written correctly; always compare hashes.
- Do not reboot the Kindle automatically after transfer. If its UI does not refresh, handle that as a separate explicit action.
- Keep all writes under `/mnt/us/`; do not modify firmware, SSH configuration, or account state as part of a file transfer.

## Verification

A transfer is complete only when all of the following are true:

- the local source remains present;
- SSH connected to `root@192.168.2.43:2222`;
- the selected `/mnt/us/` subdirectory existed;
- the remote file exists at the requested name;
- local and remote SHA-256 hashes match;
- the final response includes the exact remote path.
