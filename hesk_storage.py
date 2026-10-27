import os
import posixpath
import shlex
import paramiko

from database import SSH_HOST, SSH_PORT, SSH_USER, SSH_PASSWORD, SSH_KEY_PATH

HESK_ATTACH_DIR = os.getenv("HESK_ATTACH_DIR", "/var/www/hesk/attachments")
# Hesk dijalankan oleh web server; file milik root tidak bisa dihapus dari panel Hesk.
HESK_FILE_OWNER = os.getenv("HESK_FILE_OWNER", "www-data:www-data")

def _connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    auth = {"key_filename": SSH_KEY_PATH} if SSH_KEY_PATH else {"password": SSH_PASSWORD}
    client.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, timeout=15, **auth)
    return client

def save_attachment(saved_name: str, data: bytes):
    path = posixpath.join(HESK_ATTACH_DIR, saved_name)
    client = _connect()
    try:
        sftp = client.open_sftp()
        try:
            with sftp.open(path, "wb") as remote_file:
                remote_file.write(data)
            sftp.chmod(path, 0o644)
        finally:
            sftp.close()
        _, stdout, _ = client.exec_command(f"chown {shlex.quote(HESK_FILE_OWNER)} {shlex.quote(path)}")
        stdout.channel.recv_exit_status()
    finally:
        client.close()

def delete_attachment(saved_name: str):
    client = _connect()
    try:
        sftp = client.open_sftp()
        try:
            sftp.remove(posixpath.join(HESK_ATTACH_DIR, saved_name))
        finally:
            sftp.close()
    finally:
        client.close()
