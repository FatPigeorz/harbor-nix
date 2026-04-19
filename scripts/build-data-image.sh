#!/bin/bash
# Build a data image for a Nix closure.
#
# The data image contains only the closure's /nix/store dependencies,
# exposed as a Docker volume. Other containers mount it via --volumes-from.
#
# Usage:
#   ./scripts/build-data-image.sh <closure-path> <image-name>
#
# Examples:
#   ./scripts/build-data-image.sh $(nix build .#runtime --no-link --print-out-paths) agentix/runtime
#   ./scripts/build-data-image.sh $(nix build .#claude-code --no-link --print-out-paths) agentix/claude-code
#   ./scripts/build-data-image.sh $(nix build .#swebench --no-link --print-out-paths) agentix/swebench

set -euo pipefail

CLOSURE_PATH="${1:?Usage: $0 <closure-path> <image-name>}"
IMAGE_NAME="${2:?Usage: $0 <closure-path> <image-name>}"

echo "Building data image for: $CLOSURE_PATH"
echo "Image name: $IMAGE_NAME"

# Get all store paths in the closure
STORE_PATHS=$(nix-store -qR "$CLOSURE_PATH")
NUM_PATHS=$(echo "$STORE_PATHS" | wc -l)
TOTAL_SIZE=$(du -sh $STORE_PATHS 2>/dev/null | tail -1 | cut -f1)

echo "Closure has $NUM_PATHS store paths"

# Export closure as a tar stream and build image
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

# Create Dockerfile
cat > "$TMPDIR/Dockerfile" << 'EOF'
FROM scratch
COPY nix/store /nix/store
VOLUME /nix/store
EOF

# Copy store paths
mkdir -p "$TMPDIR/nix/store"
for path in $STORE_PATHS; do
    cp -a "$path" "$TMPDIR/nix/store/"
done

echo "Building image..."
docker build -t "$IMAGE_NAME" "$TMPDIR"

echo ""
echo "Done: $IMAGE_NAME"
echo "  Paths: $NUM_PATHS"
echo ""
echo "Usage:"
echo "  # Create data container"
echo "  docker create --name ${IMAGE_NAME##*/} $IMAGE_NAME"
echo ""
echo "  # Use in sandbox"
echo "  docker run --volumes-from ${IMAGE_NAME##*/}:ro ... any-image"
