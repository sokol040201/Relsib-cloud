#!/usr/bin/env python3
"""Upload local project files to remote via .vscode/sftp.json"""
from __future__ import annotations

import argparse
import json
import posixpath
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parent
CFG = ROOT / ".vscode" / "sftp.json"

SKIP_PREFIXES = (
	"node_modules/",
	".git/",
	".cursor/",
	"__pycache__/",
)

SKIP_FILES = {
	".vscode/sftp.json",
	"sftp_upload.py",
}


def load_cfg() -> dict:
	if not CFG.is_file():
		raise FileNotFoundError(f"SFTP config not found: {CFG}")
	return json.loads(CFG.read_text(encoding="utf-8"))


def normalize_rel(path: str) -> str:
	rel = path.replace("\\", "/")
	while rel.startswith("./"):
		rel = rel[2:]
	return rel.lstrip("/")


def should_skip(rel: str) -> bool:
	if rel in SKIP_FILES:
		return True
	return any(rel.startswith(prefix) for prefix in SKIP_PREFIXES)


def remote_path(remote_root: str, rel: str) -> str:
	root = remote_root.rstrip("/") + "/"
	return posixpath.join(root.rstrip("/"), rel)


def upload(paths: list[str], *, dry_run: bool = False) -> int:
	cfg = load_cfg()
	host = cfg["host"]
	port = int(cfg.get("port") or 22)
	user = cfg["username"]
	password = cfg["password"]
	remote_root = cfg.get("remotePath") or "/"
	if not remote_root.endswith("/"):
		remote_root += "/"

	print(f"SFTP target: {user}@{host}:{port}{remote_root}")

	if dry_run:
		ok = 0
		for rel in paths:
			rel = normalize_rel(rel)
			if should_skip(rel):
				print(f"SKIP ignored: {rel}")
				continue
			local = ROOT / rel
			if not local.is_file():
				print(f"SKIP missing: {rel}")
				continue
			print(f"DRY-RUN {rel} -> {remote_path(remote_root, rel)}")
			ok += 1
		return ok

	client = paramiko.SSHClient()
	client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
	client.connect(hostname=host, port=port, username=user, password=password, timeout=30)
	sftp = client.open_sftp()
	ok = 0
	try:
		for rel in paths:
			rel = normalize_rel(rel)
			if should_skip(rel):
				print(f"SKIP ignored: {rel}")
				continue
			local = ROOT / rel
			if not local.is_file():
				print(f"SKIP missing: {rel}")
				continue
			remote = remote_path(remote_root, rel)
			remote_dir = posixpath.dirname(remote)
			parts = remote_dir.strip("/").split("/")
			cur = ""
			for part in parts:
				cur += "/" + part
				try:
					sftp.stat(cur)
				except OSError:
					try:
						sftp.mkdir(cur)
					except OSError:
						pass
			sftp.put(str(local), remote)
			print(f"OK {rel} -> {remote}")
			ok += 1
	finally:
		sftp.close()
		client.close()
	return ok


def main() -> int:
	parser = argparse.ArgumentParser(description="Upload project files via .vscode/sftp.json")
	parser.add_argument("files", nargs="*", help="Relative paths to upload")
	parser.add_argument("--dry-run", action="store_true", help="Show remote targets without uploading")
	parser.add_argument("--verify", action="store_true", help="Print SFTP config and exit")
	args = parser.parse_args()

	if args.verify:
		cfg = load_cfg()
		print(f"local root:  {ROOT}")
		print(f"config file: {CFG}")
		print(f"host:        {cfg.get('host')}")
		print(f"port:        {cfg.get('port', 22)}")
		print(f"username:    {cfg.get('username')}")
		print(f"remotePath:  {cfg.get('remotePath')}")
		print("example:     index.html -> "
		      f"{remote_path(cfg.get('remotePath') or '/', 'index.html')}")
		return 0

	if not args.files:
		parser.print_help()
		return 2

	count = upload(args.files, dry_run=args.dry_run)
	print(f"Uploaded {count}/{len(args.files)}")
	return 0 if count else 1


if __name__ == "__main__":
	sys.exit(main())
