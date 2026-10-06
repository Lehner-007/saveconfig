SEITE
ID: index
META
SPRACHE: en
STATUS: pruefung
VERSION: 2.0
ERSTELLT: 03.10.2026
GEAENDERT: 06.10.2026
TITEL
saveconfig – Help
INHALT
![saveconfig](../../resources/saveconfig.png)

Open help with F1 or from Help → Help.

saveconfig stores original configuration files. SQLite is a catalog only.

Choose a home directory and a separate backup destination. Use File → Scan configurations. The scan only reads source files. Known configurations are selected; unknown areas, application data and system configuration require deliberate selection. Cache, temporary and Codex data are excluded from the catalog and backups, including nested cache directories. Click the Back up column to toggle an entry. Click column headers to sort. Confirm new paths under Catalog to save them permanently.

File → Back up selected creates a separate snapshot with home/, system/, manifest.json, saveconfig.db and packages.json. Sensitive data is copied without encryption; protect the backup medium. Symbolic links are preserved and never followed. Sockets and special files are skipped with a warning. Close applications first where possible: SQLite and profile files are copied as files without application-specific consistency guarantees.

Package inventory refers to the running computer even when scanning an alternative home. Missing package tools appear as null in the inventory. No packages are installed.

Show backups: double-click to see areas. Verify backup checks types, sizes, permissions, SHA-256, the database and the package inventory. Results are saved separately in verification.json. Verification describes a point in time and is not permanent tamper protection. Cancelled or failed snapshots are not complete.

Restoration is preview-only in this phase. Original files from home/ can be copied manually into a prepared home. Back up existing data first and check permissions and link targets. Do not restore all of system/etc. Install the appropriate programs first.

Operations run in the background. File → Cancel stops safely. A disconnected destination may leave an incomplete snapshot; check the error and verify afterwards.

Settings: ~/.config/saveconfig/settings.json. Catalog: ~/.local/share/saveconfig/saveconfig.db. Logs: ~/.local/state/saveconfig/logs/. Use start.sh --state-home /path/to/test-state for isolated development. Scans write management data only, never source configuration.

DE/EN and help work offline. File → Settings → Language switches immediately. Import complete JSON language packs. Download sources are configured internally. Eight additional language and help packs are supplied through the fixed GitHub source; choose a language deliberately to download it. Existing own languages are retained.

Program: 0.8.2; Author: Josef; License: GPLv3. GTK 3 and Python 3 are required.

Profiles: Save VM and PC in the Profiles menu with separate home paths, backup destinations and selections. Import and export JSON profiles; existing names and files are protected. Loading clears previous scan results. PC data must be locally accessible or mounted. File → Settings provides language and paths in a grouped dialog. Cancel discards changes, Apply saves them.

Display and classification: Programs and unknown areas are initially visible. System/Desktop and backup/old files are available through the view filters. Cache and Codex data are excluded from scans and backups. Switches above the table change visibility only, never backup selection. Save default visibility in the unified Settings dialog. Right-click a row to persist its classification in the catalog. Ignore only hides entries and never deletes data. Cinnamon and cinnamon-monitors.xml are known desktop configurations. Names ending in ~, .bak, .backup, .old and .orig are detected as old files.
Consistent appearance: File → Profiles opens the profile manager with the list on the left and name, source and backup destination on the right. New and Delete manage the list; Save stores changes, Apply activates the selected profile. Cancel discards changes. The active profile appears in the main window and title. Under File, Profiles appears, followed by a visible separator, Settings, another separator and Quit. Source, destination and default display appear at the top of Settings, followed by version checks and the combined language and language-pack section. Save settings applies validated values; Cancel discards changes.

Software checks run at every startup; additional checks while running are optional. Download sources are configured internally. Choose days, weeks or months; a month means 30 days. Manual and automatic checks run in the background and never install updates. Backups, German/English and local language imports continue to work without a configured source.

Scanning, backup and verification display a centered window with the current area and Cancel. It closes after work actually ends. Cancel is disabled for language and version requests that cannot be safely interrupted. Closing during a cancellable operation asks for confirmation and waits for it to stop safely.

Tables use alternating row backgrounds; selection and filters are preserved. Window size, position and maximized state are stored separately and checked against reachable monitors. Visible separators mark new log sessions; previous entries are preserved. Log dates use DD.MM.YYYY HH:MM:SS.

Each backup destination receives one daily folder named dd.mm.yyyy. Further selected areas not yet included are added to this backup. Previously backed-up areas are skipped. Cancellation or failure retains the previous daily backup. Different computers or home directories require separate destinations. Help → Log shows previous and current sessions with separators; Refresh reloads entries, Save log exports the visible text. Progress reserves four lines and scrolls longer text.

The active profile is highlighted with an icon and a separate coloured panel. Unsaved changes remain visibly marked. Help → Info shows used tools, availability, versions and APT packages. Software is checked at every startup; additional checks while running are optional. Settings shows software status or a failed check. Download update is enabled only for a newer version with valid DEB metadata. It saves the package in Downloads and verifies SHA-256, package name, version and architecture. Cancel removes incomplete files; installation remains manual. GitHub sources are fixed internally.

A download is offered only when a newer release provides valid package metadata. Failed version checks do not affect backups or offline help.

Profiles for mounted network filesystems specify destination type, expected mount point and exact mount source. Missing or mismatched mounts are rejected before creating files. /mnt/omv-server requires this network declaration. Desktop SMB through GVfs retains its own mount protection. Actual OMV operation has not yet been accepted.

SMB / OMV … beside the backup destination connects an available share. Server name, SSH alias (such as omv) and share are stored in the profile and can be prepared offline. The alias supplies only HostName; SSH keys and users do not authenticate SMB. Credentials are requested by the system dialog and never stored by saveconfig. gvfs-backends and gvfs-fuse are required. The OMV server is still offline; verify a real connection when it becomes available.

ENDE
