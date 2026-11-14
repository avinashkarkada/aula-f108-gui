#!/bin/sh
# Adds the app to the desktop menu for the current user. It keeps running
# from this folder, so don't move the checkout afterwards (or run this again).
set -e

id=io.github.avinashkarkada.AulaF108
here=$(cd "$(dirname "$0")" && pwd)
data=${XDG_DATA_HOME:-$HOME/.local/share}

if [ "$1" = "--remove" ]; then
    rm -f "$data/applications/$id.desktop" \
          "$data/icons/hicolor/scalable/apps/$id.svg"
    echo "removed"
    exit 0
fi

mkdir -p "$data/applications" "$data/icons/hicolor/scalable/apps"
sed "s|@DIR@|$here|" "$here/data/$id.desktop.in" > "$data/applications/$id.desktop"
cp "$here/data/$id.svg" "$data/icons/hicolor/scalable/apps/"

update-desktop-database "$data/applications" 2>/dev/null || true
gtk-update-icon-cache -q "$data/icons/hicolor" 2>/dev/null || true

echo "installed, look for 'Aula F108 Pro' in the app menu"
