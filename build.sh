#!/usr/bin/env bash
# Build script for Render deployment
# This runs during the build phase to install dependencies and build the frontend.

set -o errexit  # Exit on error

echo "=== Installing Python dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Installing Node.js and building frontend ==="
cd frontend
npm install
npm run build
cd ..

echo "=== Build complete ==="
