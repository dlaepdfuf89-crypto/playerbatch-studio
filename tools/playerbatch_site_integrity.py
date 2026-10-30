"""Read-only QA for the public PlayerBatch Studio landing page and trial assets."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
import sys
import zipfile
import struct

ROOT = Path(__file__).resolve().parents[1]
PAGES = ("index.html", "sample-output-pack.html")
MANDATORY = (
    "index.html", "sample-output-pack.html", "sample_roster_20.csv",
    "assets/playerbatch_social_hero.png", "assets/playerbatch_app_real.png",
    "assets/pro_actual_0.jpg", "assets/pro_actual_1.jpg",
    "assets/pro_actual_2.jpg", "assets/pro_actual_3.jpg",
    "downloads/PlayerBatch_Studio_Evaluation_3_Athletes.zip",
)
HOST = "dlaepdfuf89-crypto.github.io"
PREFIX = "/playerbatch-studio/"


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if not value:
                continue
            if key in ("href", "src", "poster"):
                self.urls.append(value)
            elif key == "srcset":
                self.urls.extend(x.strip().split()[0] for x in value.split(",") if x.strip())


def local_path(source, raw):
    url = urlsplit(raw.strip())
    if url.scheme and url.scheme not in ("http", "https"):
        return None
    if url.netloc:
        if url.netloc.lower() != HOST or not url.path.startswith(PREFIX):
            return None
        target = ROOT / unquote(url.path[len(PREFIX):])
    else:
        if not url.path:
            return None
        target = source.parent / unquote(url.path.lstrip("/"))
    target = target.resolve()
    if not target.is_relative_to(ROOT):
        raise ValueError(f"path traversal: {raw}")
    return target / "index.html" if target.is_dir() else target


def main():
    errors = []
    checked = set()
    for rel in MANDATORY:
        path = ROOT / rel
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"MISSING OR EMPTY mandatory: {rel}")
    expected_dimensions = {
        "assets/playerbatch_v222_real_social_1080x1350.png": (1080, 1350),
        "assets/playerbatch_v222_real_print_2400x3000.png": (2400, 3000),
    }
    for rel, expected in expected_dimensions.items():
        image = ROOT / rel
        if not image.is_file():
            errors.append(f"MISSING real export proof: {rel}")
            continue
        with image.open("rb") as f:
            header = f.read(24)
        if len(header) != 24 or header[:8] != bytes((137,80,78,71,13,10,26,10)) or header[12:16] != b"IHDR":
            errors.append(f"INVALID PNG proof: {rel}")
            continue
        actual = struct.unpack(">II", header[16:24])
        if actual != expected:
            errors.append(f"WRONG EXPORT SIZE {rel}: {actual} expected {expected}")
    for rel in PAGES:
        page = ROOT / rel
        if not page.is_file():
            continue
        parser = Assets()
        parser.feed(page.read_text(encoding="utf-8"))
        for raw in parser.urls:
            try:
                target = local_path(page, raw)
            except ValueError as e:
                errors.append(f"{rel}: {e}")
                continue
            if target is None:
                continue
            checked.add(str(target.relative_to(ROOT)))
            if not target.is_file() or target.stat().st_size == 0:
                errors.append(f"{rel}: broken local link {raw}")
    trial = ROOT / MANDATORY[-1]
    if trial.is_file():
        if trial.stat().st_size < 10_000_000:
            errors.append(f"Evaluation ZIP unexpectedly small: {trial.stat().st_size} bytes")
        elif not zipfile.is_zipfile(trial):
            errors.append("Evaluation ZIP is not a valid ZIP archive")
        else:
            with zipfile.ZipFile(trial) as archive:
                bad = archive.testzip()
                if bad:
                    errors.append(f"Evaluation ZIP CRC error in {bad}")
    print(f"PlayerBatch static-site QA: {len(PAGES)} pages, {len(checked)} unique local links, {len(MANDATORY)} mandatory assets")
    if errors:
        for error in errors:
            print("FAIL", error)
        return 1
    print("PASS: local navigation, asset presence and trial ZIP integrity")
    return 0


if __name__ == "__main__":
    sys.exit(main())
