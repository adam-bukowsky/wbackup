# wbackup — Backup Orchestrator (restic + rsync)

`wbackup` is a personal backup orchestrator for a small setup (1–3 machines).
It combines:

- **restic** for encrypted backups, snapshots, retention, and integrity checks,
- **rsync** for repository replication between machines,
- a tiny **PyQt5 GUI** to run the workflow from one machine.

The design favors **explicit and verifiable recovery** over “magic automation”.

---

## Why this project exists

This tool is built around a few strict ideas:

- Backup, replication, and restore are **separate** concerns.
- Restore is **not automated** (to avoid dangerous one-click mistakes).
- Operations are sequential, visible, and testable.
- Any synced node can become a restore source.

---

## What it does

On each run, `wbackup.py` performs this flow:

1. Initialize local restic repo (if missing).
2. Create local backup for configured paths.
3. Run `restic check`.
4. Apply retention (`forget --keep-last 7 --prune`).
5. Run remote backups over SSH.
6. Replicate repositories using `rsync`.

---

## Requirements

All participating machines should have:

- Python 3
- PyQt5
- restic
- rsync
- SSH access between nodes (passwordless recommended)

### Debian / Ubuntu

```bash
sudo apt update
sudo apt install -y python3 python3-pyqt5 restic rsync openssh-client
```

---

## Expected directory layout

`wbackup` uses the following structure in the user home directory:

```text
~/backup/
├── laptop/
│   └── restic/
├── home/
│   └── restic/
├── server/
│   └── restic/
└── logs/
```

Missing directories are created automatically.

---

## Quick start (first run)

### 1) Clone repository

```bash
git clone https://github.com/adam-bukowsky/wbackup.git
cd wbackup
```

### 2) Configure hosts and user in `wbackup.py`

Replace placeholders with real values:

- `HOME_PUBLIC_HOST`
- `SERVER_PUBLIC_HOST`
- `HOME_LAN_IP`
- `SERVER_LAN_IP`
- `user@...` in SSH/rsync commands

Also verify backup include paths:

- local: `BACKUP_PATHS`
- remote jobs: `REMOTE_JOBS[*]["include"]`

> Important: this script currently assumes your remote backup paths match the same user home layout.

### 3) Configure passwordless SSH

```bash
ssh-copy-id user@HOME_PUBLIC_HOST
ssh-copy-id user@SERVER_PUBLIC_HOST
```

### 4) Run app

```bash
python3 wbackup.py
```

Enter your restic password in the GUI prompt.

---

## Restore (intentional manual step)

Restore is intentionally done only via CLI.

Example:

```bash
restic -r ~/backup/server/restic restore latest --target ~/restore_test
```

Always restore into a separate directory first.

---

## Supported topologies

### 1 node

- Local backup only.
- No replication.

### 2 nodes (Laptop + Remote)

- Symmetric replication.
- Either node can be used as restore source.

### 3 nodes (Laptop + Home + Server)

- Laptop is orchestrator.
- Repositories are synced so each node can store all repos.

### 4+ nodes

Not supported without refactoring replication logic (currently hardcoded for up to 3 nodes).

---

## Current limitations (important for new users)

- Hostnames and usernames are hardcoded placeholders.
- Replication flow is scenario-specific (not generic N-node logic).
- Remote paths assume similar directory layout across machines.
- No config file yet (all config in Python source).

---

## Suggested next improvements

If you are learning and want to improve this project incrementally:

1. Move host/user/path settings into a YAML/JSON config.
2. Add `--dry-run` mode for rsync/restic.
3. Add preflight checks (`restic`/`rsync`/`ssh` availability).
4. Add structured logs per run with timestamps.
5. Replace hardcoded replication graph with a data-driven loop.

---

## Safety notes

- Test restore regularly (backups are only useful if restore works).
- Keep at least one offsite copy.
- Avoid running prune/forget until restore has been tested.

