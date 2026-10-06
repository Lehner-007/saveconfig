#!/bin/sh
# Nur lokale Quellvorbereitung. Kein Commit, Tag, Push oder Upload.
set -eu
TASK_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec /usr/bin/python3 "$TASK_DIR/tools/package.py" source
