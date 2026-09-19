#!/bin/bash

# V-Control Global Shortcut Installer

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -f "$REPO_ROOT/.venv/bin/v-control-overlay" ]; then
    CMD="$REPO_ROOT/.venv/bin/v-control-overlay"
else
    CMD="v-control-overlay"
fi

SHORTCUT="Shift+F2"

# 1. Install icons
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
mkdir -p "$ICON_DIR"
if [ -f "$REPO_ROOT/data/icons/v-control.svg" ]; then
    cp "$REPO_ROOT/data/icons/v-control.svg" "$ICON_DIR/v-control-overlay.svg"
    cp "$REPO_ROOT/data/icons/v-control.svg" "$ICON_DIR/com.vcontrol.overlay.svg"
fi

# 2. Create a Desktop Entry for the overlay (required by KDE and useful for others)
DESKTOP_FILE="$HOME/.local/share/applications/v-control-overlay.desktop"
mkdir -p "$HOME/.local/share/applications/"
cat << DESKEOF > "$DESKTOP_FILE"
[Desktop Entry]
Type=Application
Name=V-Control Overlay
Comment=V-Control Floating Overlay Dashboard
Exec=$CMD
Icon=v-control-overlay
Terminal=false
NoDisplay=true
StartupWMClass=com.vcontrol.overlay
Categories=Utility;System;
DESKEOF

update-desktop-database "$HOME/.local/share/applications/" &> /dev/null
command -v kbuildsycoca6 &> /dev/null && kbuildsycoca6 &> /dev/null
command -v kbuildsycoca5 &> /dev/null && kbuildsycoca5 &> /dev/null

# 3. KDE Plasma
if command -v kwriteconfig6 &> /dev/null || command -v kwriteconfig5 &> /dev/null; then
    echo "[INFO] KDE Plasma detected."
    KWC="kwriteconfig5"
    KRC="kreadconfig5"
    if command -v kwriteconfig6 &> /dev/null; then
        KWC="kwriteconfig6"
        KRC="kreadconfig6"
    fi
    
    $KWC --file kglobalshortcutsrc --group "v-control-overlay.desktop" --key "_k_friendly_name" "V-Control Overlay"
    $KWC --file kglobalshortcutsrc --group "v-control-overlay.desktop" --key "_launch" "$SHORTCUT,none,Launch V-Control Overlay"
    
    # Reload KDE global shortcuts
    qdbus org.kde.kglobalaccel /kglobalaccel org.kde.KGlobalAccel.reconfigure &> /dev/null || \
    qdbus-qt5 org.kde.kglobalaccel /kglobalaccel org.kde.KGlobalAccel.reconfigure &> /dev/null || \
    qdbus6 org.kde.kglobalaccel /kglobalaccel org.kde.KGlobalAccel.reconfigure &> /dev/null
    
    # Add KWin Rule to hide from Taskbar, Pager and Alt-Tab Switcher
    KWIN_RC="$HOME/.config/kwinrulesrc"
    COUNT=$($KRC --file "$KWIN_RC" --group General --key count 2>/dev/null || echo 0)
    if [ "$COUNT" = "" ]; then COUNT=0; fi
    FOUND=0
    for i in $(seq 1 $COUNT); do
        DESC=$($KRC --file "$KWIN_RC" --group "$i" --key Description 2>/dev/null || $KRC --file "$KWIN_RC" --group "$i" --key description 2>/dev/null)
        if [[ "$DESC" == "V-Control Overlay Skip Taskbar" ]]; then
            FOUND=$i
            break
        fi
    done
    if [ $FOUND -eq 0 ]; then
        NEW_IDX=$((COUNT + 1))
        $KWC --file "$KWIN_RC" --group General --key count $NEW_IDX
        IDX=$NEW_IDX
    else
        IDX=$FOUND
    fi
    $KWC --file "$KWIN_RC" --group "$IDX" --key Description "V-Control Overlay Skip Taskbar"
    $KWC --file "$KWIN_RC" --group "$IDX" --key title "V-Control Overlay"
    $KWC --file "$KWIN_RC" --group "$IDX" --key titlematch 2
    $KWC --file "$KWIN_RC" --group "$IDX" --key types 4294967295
    $KWC --file "$KWIN_RC" --group "$IDX" --key skiptaskbar true
    $KWC --file "$KWIN_RC" --group "$IDX" --key skiptaskbarrule 2
    $KWC --file "$KWIN_RC" --group "$IDX" --key skippager true
    $KWC --file "$KWIN_RC" --group "$IDX" --key skippagerrule 2
    $KWC --file "$KWIN_RC" --group "$IDX" --key skipswitcher true
    $KWC --file "$KWIN_RC" --group "$IDX" --key skipswitcherrule 2
    $KWC --file "$KWIN_RC" --group "$IDX" --key above true
    $KWC --file "$KWIN_RC" --group "$IDX" --key aboverule 2
    
    qdbus org.kde.KWin /KWin org.kde.KWin.reconfigure &> /dev/null || \
    qdbus6 org.kde.KWin /KWin org.kde.KWin.reconfigure &> /dev/null

    echo "[OK] KDE shortcut and window rules applied!"

# 4. GNOME
elif command -v gsettings &> /dev/null && gsettings get org.gnome.desktop.interface toolkit-accessibility &> /dev/null; then
    echo "[INFO] GNOME detected."
    KEY_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom_vcontrol/"
    
    gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$KEY_PATH name "V-Control Overlay"
    gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$KEY_PATH command "$CMD"
    gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$KEY_PATH binding "<Shift>F2"
    
    CURRENT_LIST=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings)
    if [[ "$CURRENT_LIST" != *"$KEY_PATH"* ]]; then
        if [ "$CURRENT_LIST" = "@as []" ]; then
            NEW_LIST="['$KEY_PATH']"
        else
            NEW_LIST=$(echo "$CURRENT_LIST" | sed "s/]$/, '$KEY_PATH']/")
        fi
        gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "$NEW_LIST"
    fi
    echo "[OK] GNOME shortcut added!"

else
    echo "[WARNING] Desktop environment not recognized automatically."
    echo "Please configure the shortcut 'Shift+F2' to run '$CMD' manually in your settings."
fi
