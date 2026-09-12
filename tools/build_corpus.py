#!/usr/bin/env python3
import json, sys
from pathlib import Path

def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "corpus")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    fixtures = []
    for _, rel in manifest["files"].items():
        data = json.loads((root / rel).read_text(encoding="utf-8"))
        fixtures.extend(data["fixtures"])
    out = {
        "corpus_version": manifest["corpus_version"],
        "schema": Path(manifest["schema"]).name,
        "description": manifest["description"],
        "fixtures": fixtures,
    }
    dest = Path(sys.argv[2] if len(sys.argv) > 2 else "corpus/corpus-fixtures-v1.generated.json")
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(dest)

if __name__ == "__main__":
    main()
