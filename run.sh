#!/bin/bash
set -e

BUILD_DIR="build"
CONFIG_FILE="config.yml"   # <-- FIX

echo "🔧 Configuring..."
cmake -S . -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=Release

echo "🔨 Building..."
cmake --build "$BUILD_DIR" --parallel

echo
echo "🚀 Running simulator with: $CONFIG_FILE"
"$BUILD_DIR/src/ssd_simulator" "$CONFIG_FILE"
