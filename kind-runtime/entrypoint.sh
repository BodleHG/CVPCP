#!/bin/sh

# Start Docker daemon
dockerd-entrypoint.sh &

# Wait for Docker daemon to be ready
echo "[INFO] Waiting for Docker daemon..."
until docker info >/dev/null 2>&1; do
  sleep 1
done

# Create KIND cluster if not already created
if ! kind get clusters | grep -q nested; then
  echo "[INFO] Creating KIND cluster..."
  kind create cluster --name nested
fi

sleep 5

# Start ttyd (web terminal on :7681)
echo "[INFO] Starting ttyd web terminal..."
ttyd --writable -p 7681 -c user:pass /bin/bash &
tail -f /dev/null
