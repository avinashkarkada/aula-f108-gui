#!/bin/sh
# Builds dist/aula-f108_<version>_all.deb. Only needs dpkg-deb.
set -e

here=$(cd "$(dirname "$0")/.." && pwd)
id=io.github.avinashkarkada.AulaF108
version=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$here/aula_f108/__init__.py")

root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT

pkg=$root/usr/lib/python3/dist-packages/aula_f108
mkdir -p "$pkg/gui" "$root/DEBIAN" "$root/usr/bin" \
         "$root/usr/share/applications" \
         "$root/usr/share/icons/hicolor/scalable/apps" \
         "$root/usr/lib/udev/rules.d" "$root/usr/share/doc/aula-f108"

cp "$here"/aula_f108/*.py "$pkg/"
cp "$here"/aula_f108/gui/*.py "$pkg/gui/"

cat > "$root/usr/bin/aula-f108" <<'SH'
#!/bin/sh
exec python3 -m aula_f108 "$@"
SH
chmod 755 "$root/usr/bin/aula-f108"

# same launcher as install.sh uses, but pointing at the installed command
sed -e 's|^Exec=.*|Exec=aula-f108|' -e '/^Path=/d' \
    "$here/data/$id.desktop.in" > "$root/usr/share/applications/$id.desktop"
cp "$here/data/$id.svg" "$root/usr/share/icons/hicolor/scalable/apps/"
cp "$here/udev/72-aula-f108.rules" "$root/usr/lib/udev/rules.d/"
cp "$here/LICENSE" "$root/usr/share/doc/aula-f108/copyright"

cat > "$root/DEBIAN/control" <<CONTROL
Package: aula-f108
Version: $version
Architecture: all
Section: utils
Priority: optional
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0 (>= 4.10), gir1.2-adw-1 (>= 1.4), python3-pil
Maintainer: Avinash Karkada Ashok <avinashkarkada@users.noreply.github.com>
Homepage: https://github.com/avinashkarkada/aula-f108-gui
Description: Configure the Aula F108 Pro keyboard
 Lighting effects, per-key colours, key remapping and clock sync for the
 Aula F108 Pro. Comes with a GTK app and a command line tool. The keyboard
 has to be connected with the USB cable while settings are changed.
CONTROL

# Pick up the udev rule without a reboot. Access that is being taken away
# only goes once the keyboard is plugged in again, udev doesn't revoke it
# from nodes that already exist.
cat > "$root/DEBIAN/postinst" <<'SH'
#!/bin/sh
set -e
if command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload || true
    udevadm trigger --action=add --subsystem-match=usb --subsystem-match=hidraw || true
fi
SH
cat > "$root/DEBIAN/postrm" <<'SH'
#!/bin/sh
set -e
if command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload || true
fi
SH
chmod 755 "$root/DEBIAN/postinst" "$root/DEBIAN/postrm"
find "$root" -type d -exec chmod 755 {} +
find "$root/usr" -type f ! -path "*/bin/*" -exec chmod 644 {} +

mkdir -p "$here/dist"
out=$here/dist/aula-f108_${version}_all.deb
dpkg-deb --root-owner-group --build "$root" "$out" >/dev/null
echo "$out"
