#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="$project_dir/extension"
output_dir="$project_dir/outputs"
archive="$output_dir/grammar-ml-extension.zip"

mkdir -p "$output_dir"
python3 - "$source_dir" "$archive" <<'PY'
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import sys

source = Path(sys.argv[1])
archive = Path(sys.argv[2])
with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=9) as bundle:
    for path in sorted(source.rglob("*")):
        if path.is_file() and "dist" not in path.parts:
            bundle.write(path, path.relative_to(source))
print(archive)
PY
