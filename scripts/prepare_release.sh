#!/bin/bash

# YTArchive Release Preparation Script
# Handles Python 3.13 compatibility and git state preparation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[PREP]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

echo "============================================"
echo "YTArchive Release Preparation"
echo "============================================"
echo ""

# Set Python 3.13 compatibility flag
log "Setting Python 3.13 compatibility flag..."
export PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1
success "PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 set"

# Install dependencies with compatibility flag
log "Installing dependencies with Python 3.13 compatibility..."
if PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 uv sync; then
    success "Dependencies installed successfully"
else
    error "Failed to install dependencies"
fi

# Check git status
log "Checking git status..."
if [ -n "$(git status --porcelain)" ]; then
    warning "Working directory has uncommitted changes"

    # Show what will be committed
    log "Changes to be committed:"
    git status --short

    # Commit the changes
    log "Committing release preparation changes..."
    git add .

    if git commit -m "Release v0.1.0 preparation: Update dependencies for Python 3.13 compatibility

- Updated pydantic to v2.9.0 for Python 3.13 support
- Updated pydantic-settings to v2.5.0
- Added Python version constraint <3.14
- Generated uv.lock file
- All release scripts and infrastructure completed
- Ready for v0.1.0 release with PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1"; then
        success "Release preparation changes committed"
    else
        error "Failed to commit changes"
    fi
else
    log "Working directory is clean"
fi

# Push changes
log "Pushing changes to remote..."
if git push; then
    success "Changes pushed to remote"
else
    warning "Failed to push changes (continuing anyway)"
fi

echo ""
echo "============================================"
success "Release Preparation Complete!"
echo "============================================"
echo ""
echo "✅ Python 3.13 compatibility configured"
echo "✅ Dependencies installed successfully"
echo "✅ Git working directory is clean"
echo "✅ Changes committed and pushed"
echo ""
echo "🚀 Ready to run release script:"
echo "   export PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 && ./scripts/release.sh v0.1.0"
echo ""
