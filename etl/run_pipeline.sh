#!/bin/sh
set -e
cd "$(dirname "$0")"
python export_to_minio.py
python build_marts.py
