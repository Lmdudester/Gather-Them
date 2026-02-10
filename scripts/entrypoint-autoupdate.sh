#!/bin/sh
set -e  # Exit on any error

echo "=== Gather Them Auto-Update Startup ==="

# Clean up any previous source directory
if [ -d /app/src ]; then
    echo "[STARTUP] Cleaning up previous source..."
    chmod -R u+rwX /app/src 2>/dev/null || true
    rm -rf /app/src
fi

echo "[STARTUP] Cloning repository..."
git clone --depth 1 --branch "${GIT_BRANCH:-main}" "${GIT_REPO_URL:-https://github.com/Lmdudester/Gather-Them.git}" /app/src

echo "[STARTUP] Installing dependencies..."
cd /app/src
pip install --no-cache-dir -r requirements.txt

echo "[STARTUP] Running migrations..."
python manage.py migrate --no-input

echo "[STARTUP] Starting Gather Them..."
exec python manage.py runserver 0.0.0.0:${PORT:-3007}
