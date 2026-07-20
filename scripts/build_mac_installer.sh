#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Building web assets..."
npm run build

echo "Building macOS installer..."
npm run desktop:mac

echo "Done. Output directory: release/"
