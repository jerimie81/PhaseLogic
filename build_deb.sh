#!/bin/bash
# Build smooth-bee_<version>_all.deb
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION=$(python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from smooth_bee import __version__; print(__version__)")
PKG="smooth-bee_${VERSION}_all"
STAGING="/tmp/${PKG}"
PY_DIST="/usr/lib/python3/dist-packages"

echo "==> Building ${PKG}.deb"

# Clean staging
rm -rf "$STAGING"

# --- DEBIAN metadata ---
mkdir -p "$STAGING/DEBIAN"
sed "s/^Version: .*/Version: ${VERSION}/" "$SCRIPT_DIR/debian/control" > "$STAGING/DEBIAN/control"
cp "$SCRIPT_DIR/debian/postinst" "$STAGING/DEBIAN/postinst"
cp "$SCRIPT_DIR/debian/prerm"    "$STAGING/DEBIAN/prerm"
chmod 0755 "$STAGING/DEBIAN/postinst" "$STAGING/DEBIAN/prerm"

# --- Python package ---
mkdir -p "$STAGING${PY_DIST}"
cp -r "$SCRIPT_DIR/smooth_bee" "$STAGING${PY_DIST}/smooth_bee"
# Remove __pycache__ and .pyc artifacts
find "$STAGING${PY_DIST}/smooth_bee" -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "$STAGING${PY_DIST}/smooth_bee" -name '*.pyc' -delete 2>/dev/null || true

# --- Prompt templates ---
mkdir -p "$STAGING/usr/share/smooth-bee/prompts"
cp "$SCRIPT_DIR/prompts/"*.j2 "$STAGING/usr/share/smooth-bee/prompts/"

# --- Default system config ---
mkdir -p "$STAGING/etc/smooth-bee"
cp "$SCRIPT_DIR/config.toml" "$STAGING/etc/smooth-bee/config.toml"

# --- CLI entry point ---
mkdir -p "$STAGING/usr/bin"
cat > "$STAGING/usr/bin/smooth-bee" << 'PYEOF'
#!/usr/bin/python3
from smooth_bee.cli import main
main()
PYEOF
chmod 0755 "$STAGING/usr/bin/smooth-bee"

# --- Changelog (Debian policy requires this) ---
mkdir -p "$STAGING/usr/share/doc/smooth-bee"
cat > /tmp/smooth-bee-changelog << 'EOF'
smooth-bee (0.1.0) unstable; urgency=low

  * Initial release.

 -- Jerimie Palmer <jerimiepalmer81@gmail.com>  Wed, 30 Apr 2026 00:00:00 +0000
EOF
gzip -9 -n -c /tmp/smooth-bee-changelog > "$STAGING/usr/share/doc/smooth-bee/changelog.Debian.gz"
rm /tmp/smooth-bee-changelog

# --- md5sums ---
(cd "$STAGING" && find usr etc -type f | sort | xargs md5sum > DEBIAN/md5sums)

# --- Build ---
dpkg-deb --root-owner-group --build "$STAGING" "$SCRIPT_DIR/${PKG}.deb"
rm -rf "$STAGING"

echo ""
echo "==> Built: $SCRIPT_DIR/${PKG}.deb"
echo ""
echo "Install with:"
echo "  sudo dpkg -i $SCRIPT_DIR/${PKG}.deb"
echo "  sudo apt-get install -f   # resolve any missing deps"
