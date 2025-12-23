#!/usr/bin/env python3
import os
import sys
import subprocess
from PyQt5 import QtWidgets, QtCore, QtGui

# =========================
# Base paths (user-agnostic)
# =========================

HOME = os.path.expanduser("~")
BASE_BACKUP_DIR = os.path.join(HOME, "backup")

RESTIC_LAPTOP_REPO = os.path.join(BASE_BACKUP_DIR, "laptop", "restic")
RESTIC_HOME_REPO   = os.path.join(BASE_BACKUP_DIR, "home", "restic")
RESTIC_SERVER_REPO = os.path.join(BASE_BACKUP_DIR, "server", "restic")

LOG_DIR = os.path.join(BASE_BACKUP_DIR, "logs")
LOG_LAPTOP_FILE = os.path.join(LOG_DIR, "laptop-restic.log")

# =========================
# Local backup paths
# =========================

BACKUP_PATHS = [
    os.path.join(HOME, ".mozilla"),
    os.path.join(HOME, ".ssh"),
    os.path.join(HOME, "mi"),
]

# =========================
# Remote nodes (placeholders)
# =========================
# Replace HOST_* placeholders with your actual hostnames or IPs

REMOTE_NODES = [
    ["HOME_PUBLIC_HOST", "HOME_LAN_IP"],     # home node
    ["SERVER_PUBLIC_HOST", "SERVER_LAN_IP"], # server node
]

REMOTE_JOBS = [
    {
        "host": "HOME_PUBLIC_HOST",
        "repo": RESTIC_HOME_REPO,
        "include": [
            os.path.join(HOME, ".ssh"),
            os.path.join(HOME, "metrics"),
            os.path.join(HOME, "mysoft"),
        ],
    },
    {
        "host": "SERVER_PUBLIC_HOST",
        "repo": RESTIC_SERVER_REPO,
        "include": [
            os.path.join(HOME, ".ssh"),
            os.path.join(HOME, "metrics"),
            os.path.join(HOME, "wg0"),
        ],
    },
]


class BackupThread(QtCore.QThread):
    progress = QtCore.pyqtSignal(str, int)
    done = QtCore.pyqtSignal(str)
    failed = QtCore.pyqtSignal(str)

    def __init__(self, password: str):
        super().__init__()
        self.password = password

    def run(self):
        try:
            os.makedirs(LOG_DIR, exist_ok=True)

            if os.path.exists(LOG_LAPTOP_FILE) and os.path.getsize(LOG_LAPTOP_FILE) > 1_000_000:
                os.rename(LOG_LAPTOP_FILE, LOG_LAPTOP_FILE + ".1")

            env = os.environ.copy()

            def run_cmd(cmd, stage, prog):
                """Run command with logging and progress update"""
                self.progress.emit(stage, prog)
                p = subprocess.run(
                    cmd,
                    input=(self.password + "\n").encode(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=env,
                )
                with open(LOG_LAPTOP_FILE, "ab") as log:
                    log.write(p.stdout)
                if p.returncode != 0:
                    raise RuntimeError(f"Command failed: {' '.join(cmd)}")

            # === 1. Initialize local restic repository if needed ===
            if not os.path.isdir(RESTIC_LAPTOP_REPO):
                os.makedirs(RESTIC_LAPTOP_REPO, exist_ok=True)
                run_cmd(
                    ["restic", "-r", RESTIC_LAPTOP_REPO, "init"],
                    "Initializing local repository…",
                    10,
                )

            # === 2. Laptop backup ===
            run_cmd(
                ["restic", "-r", RESTIC_LAPTOP_REPO, "backup"] + BACKUP_PATHS,
                "Backing up laptop data…",
                45,
            )

            # === 3. Integrity check and retention ===
            run_cmd(
                ["restic", "-r", RESTIC_LAPTOP_REPO, "check"],
                "Checking repository integrity…",
                65,
            )
            run_cmd(
                ["restic", "-r", RESTIC_LAPTOP_REPO, "forget", "--keep-last", "7", "--prune"],
                "Pruning old snapshots…",
                75,
            )

            # === 4. Remote backups via SSH ===
            self.progress.emit("Backing up remote hosts…", 80)

            for job in REMOTE_JOBS:
                host = job["host"]
                repo = job["repo"]
                targets = job.get("include", [HOME])

                self.progress.emit(f"Backing up host {host}…", 82)

                cmd_ssh = [
                    "ssh", f"user@{host}",
                    "restic", "-r", repo, "backup",
                ] + targets

                p = subprocess.run(
                    cmd_ssh,
                    input=(self.password + "\n").encode(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=env,
                )

                with open(LOG_LAPTOP_FILE, "ab") as log:
                    log.write(p.stdout)

                if p.returncode != 0:
                    raise RuntimeError(f"Remote backup failed for host {host}")
            # === 5. Repository synchronization over network ===
            self.progress.emit("Synchronizing backup repositories…", 90)
            
            BASE = BASE_BACKUP_DIR  # ~/backup
            
            # --------------------------------------------------
            # 1. Laptop ↔ Home
            # --------------------------------------------------
            self.progress.emit("Sync: laptop ↔ home", 91)
            
            # 1.1 Laptop -> Home (laptop repo is authoritative)
            subprocess.run([
                "rsync", "-avz", "--delete",
                os.path.join(BASE, "laptop") + "/",
                f"user@HOME_PUBLIC_HOST:{os.path.join(BASE, 'laptop')}/"
            ], check=True)
            
            # 1.2 Home -> Laptop (home repo is authoritative)
            subprocess.run([
                "rsync", "-avz", "--delete",
                f"user@HOME_PUBLIC_HOST:{os.path.join(BASE, 'home')}/",
                os.path.join(BASE, "home") + "/"
            ], check=True)
            
            # --------------------------------------------------
            # 2. Laptop ↔ Server
            # --------------------------------------------------
            self.progress.emit("Sync: laptop ↔ server", 94)
            
            # 2.1 Server -> Laptop (server repo is authoritative)
            subprocess.run([
                "rsync", "-avz", "--delete",
                f"user@SERVER_PUBLIC_HOST:{os.path.join(BASE, 'server')}/",
                os.path.join(BASE, "server") + "/"
            ], check=True)
            
            # 2.2 Laptop -> Server (laptop repo is authoritative)
            subprocess.run([
                "rsync", "-avz", "--delete",
                os.path.join(BASE, "laptop") + "/",
                f"user@SERVER_PUBLIC_HOST:{os.path.join(BASE, 'laptop')}/"
            ], check=True)
            
            # 2.3 Laptop -> Server (home repo, already synchronized)
            subprocess.run([
                "rsync", "-avz", "--delete",
                os.path.join(BASE, "home") + "/",
                f"user@SERVER_PUBLIC_HOST:{os.path.join(BASE, 'home')}/"
            ], check=True)
            
            # --------------------------------------------------
            # 3. Final pass: Server repo -> Home
            # --------------------------------------------------
            self.progress.emit("Sync: server → home", 97)
            
            # 3.1 Laptop -> Home (server repo is authoritative)
            subprocess.run([
                "rsync", "-avz", "--delete",
                os.path.join(BASE, "server") + "/",
                f"user@HOME_PUBLIC_HOST:{os.path.join(BASE, 'server')}/"
            ], check=True)
            
            self.done.emit("✅ Backup and synchronization completed successfully.")


        except Exception as e:
            self.failed.emit(str(e))


class BackupApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Backup & Sync")
        self.resize(460, 220)

        layout = QtWidgets.QVBoxLayout(self)

        self.label = QtWidgets.QLabel("Enter restic password:")
        self.edit = QtWidgets.QLineEdit()
        self.edit.setEchoMode(QtWidgets.QLineEdit.Password)

        self.btn = QtWidgets.QPushButton("Start backup")
        self.btn.clicked.connect(self.start_backup)
        self.edit.returnPressed.connect(self.start_backup)

        self.progress = QtWidgets.QProgressBar()

        layout.addWidget(self.label)
        layout.addWidget(self.edit)
        layout.addWidget(self.btn)
        layout.addWidget(self.progress)

    def start_backup(self):
        password = self.edit.text().strip()
        if not password:
            QtWidgets.QMessageBox.warning(self, "Error", "Password required.")
            return

        self.btn.setEnabled(False)
        self.thread = BackupThread(password)
        self.thread.progress.connect(self.update_progress)
        self.thread.done.connect(self.finish_ok)
        self.thread.failed.connect(self.finish_fail)
        self.thread.start()

    def update_progress(self, text, val):
        self.label.setText(text)
        self.progress.setValue(val)

    def finish_ok(self, msg):
        QtWidgets.QMessageBox.information(self, "Done", msg)
        self.close()

    def finish_fail(self, msg):
        QtWidgets.QMessageBox.critical(self, "Error", msg)
        self.close()


def main():
    app = QtWidgets.QApplication(sys.argv)
    w = BackupApp()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
