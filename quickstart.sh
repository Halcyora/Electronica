#!/bin/bash

# FractalPulse Quick Start Script
# Downloads datasets and starts Docker Compose

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "================================================"
echo "FractalPulse — Software-Only Prototype"
echo "Quick Start Setup"
echo "================================================"

# Check prerequisites
echo ""
echo "✓ Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "✗ Docker not found. Please install Docker: https://docker.com"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "✗ Docker Compose not found. Please install Docker Compose."
    exit 1
fi

echo "✓ Docker is installed"

# Create data directories
echo ""
echo "✓ Creating data directories..."
mkdir -p data/raw/{mitdb,afdb,bidmc}
mkdir -p data/db
mkdir -p models

# Check if datasets exist
echo ""
echo "📊 Checking datasets..."

check_dataset() {
    local dataset=$1
    local path=$2
    local count=$(find "$path" -maxdepth 1 -name "*.hea" -o -name "*.dat" | wc -l)
    if [ "$count" -gt 0 ]; then
        echo "  ✓ $dataset: Found $count record files"
        return 0
    else
        echo "  ⚠ $dataset: No records found in $path"
        return 1
    fi
}

mitdb_ok=0
afdb_ok=0
bidmc_ok=0

check_dataset "MIT-BIH Arrhythmia" "data/raw/mitdb" || mitdb_ok=1
check_dataset "MIT-BIH AFib" "data/raw/afdb" || afdb_ok=1
check_dataset "BIDMC" "data/raw/bidmc" || bidmc_ok=1

if [ "$mitdb_ok" -ne 0 ] || [ "$afdb_ok" -ne 0 ] || [ "$bidmc_ok" -ne 0 ]; then
    echo ""
    echo "⚠️  Some datasets are missing. Downloading..."
    echo ""
    
    if [ "$mitdb_ok" -ne 0 ]; then
        echo "  Downloading MIT-BIH Arrhythmia Database..."
        wget -q "https://physionet.org/content/mitdb/get-zip/1.0.0/" -O /tmp/mitdb.zip || true
        if [ -f "/tmp/mitdb.zip" ]; then
            unzip -q /tmp/mitdb.zip -d data/raw/mitdb/ && echo "  ✓ MIT-BIH extracted"
            rm /tmp/mitdb.zip
        else
            echo "  ✗ Failed to download. Continuing anyway..."
        fi
    fi
    
    if [ "$afdb_ok" -ne 0 ]; then
        echo "  Downloading MIT-BIH AFib Database..."
        wget -q "https://physionet.org/content/afdb/get-zip/1.0.0/" -O /tmp/afdb.zip || true
        if [ -f "/tmp/afdb.zip" ]; then
            unzip -q /tmp/afdb.zip -d data/raw/afdb/ && echo "  ✓ AFib extracted"
            rm /tmp/afdb.zip
        else
            echo "  ✗ Failed to download. Continuing anyway..."
        fi
    fi
    
    if [ "$bidmc_ok" -ne 0 ]; then
        echo "  Downloading BIDMC Dataset..."
        wget -q "https://physionet.org/content/bidmc/get-zip/1.0.0/" -O /tmp/bidmc.zip || true
        if [ -f "/tmp/bidmc.zip" ]; then
            unzip -q /tmp/bidmc.zip -d data/raw/bidmc/ && echo "  ✓ BIDMC extracted"
            rm /tmp/bidmc.zip
        else
            echo "  ✗ Failed to download. Continuing anyway..."
        fi
    fi
else
    echo "  ✓ All datasets found!"
fi

# Start Docker Compose
echo ""
echo "🐳 Starting Docker services..."
echo "   (This may take a few minutes on first run)"
echo ""

docker-compose up --build

echo ""
echo "================================================"
echo "✓ Services started!"
echo "================================================"
echo ""
echo "Dashboard: http://localhost:3000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop."
