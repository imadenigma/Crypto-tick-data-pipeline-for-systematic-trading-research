import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from tqdm import tqdm

from orderflow.config import DATA_ROOT
from orderflow.data.catalog import RemoteFile

RAW_ROOT = DATA_ROOT / "raw"
CHUNK = 1 << 20

class ChecksumError(RuntimeError):
    pass

def local_path(remote: RemoteFile, root: Path = RAW_ROOT) -> Path:
    return root / remote.key.removeprefix("data/")

def sha256_of(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()

def _published_sha256(text:str) -> str:
    return text.split()[0].lower()


def verify_local(zip_path: Path) -> bool:
    ck = zip_path.with_name(zip_path.name + ".CHECKSUM")
    return ck.exists() and sha256_of(zip_path) == _published_sha256(ck.read_text())

def download_file(remote: RemoteFile, session: requests.Session, root: Path = RAW_ROOT,
                  retries: int = 3) -> str:
    """Invariant: a zip exists at its final path only if its SHA-256 matched."""
    dest = local_path(remote, root)
    if dest.exists():
        return "skipped"
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    ck = dest.with_name(dest.name + ".CHECKSUM")
    for attempt in range(retries):
        try:
            r = session.get(remote.url + ".CHECKSUM", timeout=30)
            r.raise_for_status()
            ck_text = r.text
            h = hashlib.sha256()
            with session.get(remote.url, stream=True, timeout=60) as resp:
                resp.raise_for_status()
                with part.open("wb") as f:
                    for chunk in resp.iter_content(CHUNK):
                        f.write(chunk)
                        h.update(chunk)
            if h.hexdigest() != _published_sha256(ck_text):
                raise ChecksumError(f"SHA-256 mismatch: {remote.key}")
            ck.write_text(ck_text)
            os.replace(part, dest)  # atomic: the final path never holds a partial file
            return "downloaded"
        except (requests.RequestException, ChecksumError):
            part.unlink(missing_ok=True)
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def download_many(remotes: list[RemoteFile], root: Path = RAW_ROOT, workers: int = 4) -> dict[str, int]:
    counts = {"downloaded": 0, "skipped": 0, "failed": 0}
    failures = []
    with requests.Session() as session, ThreadPoolExecutor(workers) as pool:
        futs = {pool.submit(download_file, r, session, root): r for r in remotes}
        try:
            for fut in tqdm(as_completed(futs), total=len(futs), unit="file"):
                try:
                    counts[fut.result()] += 1
                except Exception as e:  # keep going; report every failure at the end
                    counts["failed"] += 1
                    failures.append(f"{futs[fut].key}: {e}")
        except KeyboardInterrupt:
            for f in futs:
                f.cancel()  # drop queued files; in-flight ones finish or leave only a .part
            raise
    for msg in failures:
        print("FAILED", msg)
    return counts