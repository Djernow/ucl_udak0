#!/bin/bash
# UDAKO Champions League - TrueNAS SCALE Deployment Script
# Deploy application files to the dataset and verify container setup

set -e

DATASET_PATH="/mnt/immich/Jarno_app/udako"
DATA_PATH="$DATASET_PATH/data"
DOWNLOADS_PATH="$DATASET_PATH/downloads"

# Get script directory to find files relative to where script runs
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "======================================================"
echo "UDAKO CL - Deployment Script"
echo "======================================================"
echo "Script directory: $SCRIPT_DIR"
echo "Target dataset: $DATASET_PATH"
echo ""

# Verify all required files exist locally
echo "🔍 Checking required files..."
REQUIRED_FILES=(
    "website.html"
    "index.html"
    "manifest.json"
    "service-worker.js"
    "app.py"
    "requirements.txt"
    "Dockerfile.backend"
    "docker-compose.yaml"
    "httpd.conf"
    "httpd-proxy.conf"
)

for FILE in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$SCRIPT_DIR/$FILE" ]; then
        echo "❌ Missing file: $FILE"
        exit 1
    fi
    echo "   ✓ Found $FILE"
done
echo ""

# Check if dataset exists
if [ ! -d "$DATASET_PATH" ]; then
    echo "❌ Dataset not found at $DATASET_PATH"
    echo "   Create it in TrueNAS first: Datasets → Immich → Jarno_app → udako"
    exit 1
fi

echo "✓ Dataset exists at $DATASET_PATH"

# Create data directory if not exists
mkdir -p "$DATA_PATH"
chmod 755 "$DATA_PATH"
echo "✓ Data directory ready at $DATA_PATH"
echo ""

# Create downloads directory for mobile builds
mkdir -p "$DOWNLOADS_PATH"
chmod 755 "$DOWNLOADS_PATH"
echo "✓ Downloads directory ready at $DOWNLOADS_PATH"
echo ""

# Copy application files
echo "📋 Copying application files to $DATASET_PATH..."
cp -v "$SCRIPT_DIR/website.html" "$DATASET_PATH/"
cp -v "$SCRIPT_DIR/index.html" "$DATASET_PATH/"
cp -v "$SCRIPT_DIR/manifest.json" "$DATASET_PATH/"
cp -v "$SCRIPT_DIR/service-worker.js" "$DATASET_PATH/"
cp -v "$SCRIPT_DIR/app.py" "$DATASET_PATH/"
cp -v "$SCRIPT_DIR/requirements.txt" "$DATASET_PATH/"
cp -v "$SCRIPT_DIR/Dockerfile.backend" "$DATASET_PATH/"
cp -v "$SCRIPT_DIR/docker-compose.yaml" "$DATASET_PATH/"
cp -v "$SCRIPT_DIR/httpd.conf" "$DATASET_PATH/"
cp -v "$SCRIPT_DIR/httpd-proxy.conf" "$DATASET_PATH/"

# Copy mobile builds if present
if [ -d "$SCRIPT_DIR/downloads" ]; then
    echo "📦 Copying mobile builds from $SCRIPT_DIR/downloads..."
    cp -v "$SCRIPT_DIR/downloads"/* "$DOWNLOADS_PATH/" 2>/dev/null || true
fi

# Set correct permissions
echo ""
echo "🔒 Setting file permissions..."
chmod 644 "$DATASET_PATH/website.html"
chmod 644 "$DATASET_PATH/index.html"
chmod 644 "$DATASET_PATH/manifest.json"
chmod 644 "$DATASET_PATH/service-worker.js"
chmod 644 "$DATASET_PATH/app.py"
chmod 644 "$DATASET_PATH/requirements.txt"
chmod 644 "$DATASET_PATH/Dockerfile.backend"
chmod 644 "$DATASET_PATH/docker-compose.yaml"
chmod 644 "$DATASET_PATH/httpd.conf"
chmod 644 "$DATASET_PATH/httpd-proxy.conf"

if [ -d "$DOWNLOADS_PATH" ]; then
    chmod -R 644 "$DOWNLOADS_PATH"/* 2>/dev/null || true
fi

# Verify all files were deployed
echo ""
echo "✅ Verifying deployment..."
for FILE in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$DATASET_PATH/$FILE" ]; then
        echo "❌ Deployment failed: $FILE not found in $DATASET_PATH"
        exit 1
    fi
    echo "   ✓ $FILE"
done
echo "✅ All deployment files copied successfully!"
echo ""
echo "📁 Deployment Summary:"
ls -lh "$DATASET_PATH/" | grep -E "\.(html|json|js|py|txt|yaml|conf)$"
echo ""
echo "📊 Data directory:"
ls -lh "$DATA_PATH/" 2>/dev/null || echo "   (empty, will be created on first run)"
echo ""
echo "======================================================"
echo "NEXT STEPS:"
echo "======================================================"
echo ""
echo "1. In TrueNAS SCALE, go to: Apps → Installed Applications"
echo ""
echo "2. If no UDAKO app exists yet:"
echo "   - Click 'Launch Docker Image'"
echo "   - Select 'Custom Docker Compose YAML'"
echo "   - Paste contents of $DATASET_PATH/docker-compose.yaml"
echo "   - Set environment:"
echo "     • SECRET_KEY: (change to secure random string)"
echo "   - Save and launch"
echo ""
echo "3. If UDAKO app already exists:"
echo "   - Update the Docker Compose YAML with new version"
echo "   - Redeploy the application"
echo ""
echo "4. Access the application:"
echo "   - HTTP: http://127.0.0.1:50995/"
echo "   - HTTPS: https://udako.libertronics.org/"
echo ""
echo "5. Default admin credentials:"
echo "   - Username: admin"
echo "   - Password: admin123"
echo "   - ⚠️  Change password immediately on first login!"
echo ""
echo "======================================================"
echo "TROUBLESHOOTING:"
echo "======================================================"
echo ""
echo "Check Flask backend logs:"
echo "  docker logs udako-backend 2>&1 | tail -50"
echo ""
echo "Verify files deployed:"
echo "  ls -la $DATASET_PATH/"
echo ""
echo "Check database:"
echo "  ls -lh $DATA_PATH/udako.db"
echo ""
echo "Test API health:"
echo "  curl http://127.0.0.1:5000/api/health"
echo ""
echo "======================================================"
