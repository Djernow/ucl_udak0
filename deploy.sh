#!/bin/bash
# UDAKO CL Deployment Script
# Pulls/copies files to TrueNAS dataset and restarts Docker container

set -e

# ============================================================
# Configuration — Edit these values
# ============================================================
DATASET_PATH="/mnt/immich/Jarno_app/udako"
CONTAINER_NAME="static-site-1"  # Change if your container name differs
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ============================================================
# Colors for output
# ============================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================
# Helper functions
# ============================================================
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================================
# Pre-flight checks
# ============================================================
log_info "Running pre-flight checks..."

if [ ! -d "$REPO_DIR" ]; then
  log_error "Repository directory not found: $REPO_DIR"
  exit 1
fi

if [ ! -f "$REPO_DIR/manifest.json" ]; then
  log_error "manifest.json not found in repo. Make sure you're in the correct directory."
  exit 1
fi

if [ ! -d "$DATASET_PATH" ]; then
  log_error "Dataset path does not exist: $DATASET_PATH"
  log_info "Create it first: mkdir -p $DATASET_PATH"
  exit 1
fi

log_info "✓ Pre-flight checks passed"

# ============================================================
# Copy files to dataset
# ============================================================
log_info "Copying files to $DATASET_PATH..."

FILES_TO_COPY=(
  "website.html"
  "manifest.json"
  "service-worker.js"
)

for file in "${FILES_TO_COPY[@]}"; do
  if [ -f "$REPO_DIR/$file" ]; then
    cp "$REPO_DIR/$file" "$DATASET_PATH/$file"
    log_info "✓ Copied $file"
  else
    log_warn "File not found: $file (skipping)"
  fi
done

# Copy as index.html if not already present
if [ ! -f "$DATASET_PATH/index.html" ]; then
  cp "$REPO_DIR/website.html" "$DATASET_PATH/index.html"
  log_info "✓ Created index.html symlink"
fi

# ============================================================
# Set permissions
# ============================================================
log_info "Setting permissions on $DATASET_PATH..."

sudo chown -R root:root "$DATASET_PATH"
sudo chmod -R 755 "$DATASET_PATH"
sudo chmod 644 "$DATASET_PATH"/*.{json,js,html} 2>/dev/null || true

log_info "✓ Permissions set"

# ============================================================
# Create .htaccess if not present
# ============================================================
if [ ! -f "$DATASET_PATH/.htaccess" ]; then
  log_info "Creating .htaccess for default index..."
  echo "DirectoryIndex index.html" | sudo tee "$DATASET_PATH/.htaccess" > /dev/null
  sudo chmod 644 "$DATASET_PATH/.htaccess"
  log_info "✓ .htaccess created"
else
  log_info "✓ .htaccess already exists"
fi

# ============================================================
# Verify files in container
# ============================================================
log_info "Verifying files in container..."

if command -v docker &> /dev/null; then
  if docker ps --filter "name=$CONTAINER_NAME" --format '{{.Names}}' | grep -q "$CONTAINER_NAME"; then
    log_info "Checking container filesystem..."
    docker exec "$CONTAINER_NAME" ls -lh /usr/local/apache2/htdocs/ || log_warn "Could not verify container files"
  else
    log_warn "Container '$CONTAINER_NAME' not running. Skipping container verification."
    log_info "Start the container with: docker start $CONTAINER_NAME"
  fi
else
  log_warn "Docker not found. Skipping container check."
fi

# ============================================================
# Summary
# ============================================================
log_info "✅ Deployment complete!"
log_info ""
log_info "Summary:"
log_info "  Files copied to: $DATASET_PATH"
log_info "  Access URL: https://udako.libertronics.org"
log_info ""
log_info "Next steps:"
log_info "  1. Ensure container is running: docker start $CONTAINER_NAME"
log_info "  2. Test in browser: https://udako.libertronics.org"
log_info "  3. On Android: Open Chrome → Install app from prompt"
log_info ""
log_info "Troubleshooting:"
log_info "  - Check container logs: docker logs $CONTAINER_NAME"
log_info "  - Verify permissions: ls -la $DATASET_PATH"
log_info "  - Test directly: curl -i http://127.0.0.1:50995/"
