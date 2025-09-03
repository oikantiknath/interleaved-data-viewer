#!/usr/bin/env python3
import json, pathlib

BASE = pathlib.Path("/Users/oikantik/wiki-data-samples")

def referenced_images():
    used = set()
    for domain in BASE.iterdir():
        if not domain.is_dir(): continue
        text_root = domain/"text"
        if not text_root.exists(): continue
        for j in text_root.rglob("*.json"):
            try:
                rec = json.loads(j.read_text(encoding="utf-8"))
            except Exception:
                continue
            for b in rec.get("blocks", []):
                if b.get("type") == "image" and b.get("local_path"):
                    used.add(pathlib.Path(b["local_path"]).name)
    return used

def main():
    used = referenced_images()
    for domain in BASE.iterdir():
        if not domain.is_dir(): continue
        img_dir = domain/"images"
        if not img_dir.exists(): continue
        for img in img_dir.iterdir():
            if img.is_file() and img.name not in used:
                img.unlink()  # delete unreferenced image

if __name__ == "__main__":
    main()
