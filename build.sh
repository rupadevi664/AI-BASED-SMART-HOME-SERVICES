#!/usr/bin/env bash
# Exit on any error
set -o errexit

echo "=== Python version ==="
python --version

echo "=== Upgrading pip ==="
pip install --upgrade pip

echo "=== Installing backend dependencies ==="
pip install -r backend/requirements.txt

echo "=== Build succeeded ==="
