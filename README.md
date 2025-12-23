# Backup Orchestrator (restic + rsync) wbackup

Personal backup orchestration tool for small setups (2–3 machines).

The project is built around a simple idea:

- **restic** is responsible for backups, encryption, snapshots and integrity
- **rsync** is used only as a transport layer to replicate restic repositories
- restore is performed manually via CLI to avoid unsafe automation

The tool favors explicit workflows, predictability and verifiable recovery
over convenience or full automation.

---

## Key principles

- Backup, replication and restore are **separate concerns**
- No hidden magic or background services
- No automatic restore
- Every operation is visible and testable
- Any node can become a restore point

---

## Requirements

All machines involved must have:

- Python 3
- restic
- rsync
- SSH access between nodes

### Debian / Ubuntu

```bash
sudo apt install python3 python3-pyqt5 restic rsync openssh-client

---

Directory layout

The tool assumes the following directory structure inside the user's home directory:

~/backup/
├── laptop/
│   └── restic/
├── home/
│   └── restic/
├── server/
│   └── restic/
└── logs/

Directories are created automatically if missing.

---

Configuration

Before running the tool, open the Python file and replace placeholder values
with your actual hosts or IP addresses:

HOME_PUBLIC_HOST
SERVER_PUBLIC_HOST
HOME_LAN_IP
SERVER_LAN_IP

Adjust backup paths if needed.

The same user must exist on all machines.

---

SSH setup

Passwordless SSH access is recommended.

Example:

ssh-copy-id user@HOME_PUBLIC_HOST
ssh-copy-id user@SERVER_PUBLIC_HOST

---

Running the application

Run the application locally on the orchestrator machine (laptop):

python3 wbackup.py


Enter the restic password when prompted.

The password is not stored anywhere and is passed only to restic.

---

What the tool does


Initializes local restic repository (if missing)

Creates a local backup on the orchestrator

Verifies repository integrity

Applies snapshot retention policy

Runs restic backups on remote machines via SSH

Replicates restic repositories using rsync

All operations are executed sequentially.

---

Restore (very important)


Restore is intentionally not automated.

Example restore from a replicated server repository:

restic -r ~/backup/server/restic restore latest --target ~/restore_test


Always restore into a separate directory.
Restore is considered a critical operation and should be performed consciously.

---

Supported topologies


1 node

Local backups only

No replication

Useful for standalone machines


2 nodes (Laptop + Remote)

Symmetric replication

Each node stores:

its own restic repository

a replicated copy of the other node

Either node can be used for restore


3 nodes (Laptop + Home + Server)

Laptop acts as an orchestrator

Backups are executed sequentially

Repositories are replicated so that:

every node ends up with all repositories

any node can serve as a restore point


More than 3 nodes

Running the tool with more than 3 nodes is not supported without refactoring.

Reason:

Backup jobs are already data-driven

Repository replication is currently implemented as a fixed scenario

For 4+ nodes, replication logic must be generalized into an iterative process

This is a design decision, not a limitation of restic or rsync.

Over-generalization was avoided intentionally.

---

Notes

This is a personal tool, not a general-purpose backup framework

The project reflects a preference for control, clarity and recoverability

Tested restore workflow is considered part of the system design
