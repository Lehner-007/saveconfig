# saveconfig

GTK-3-Programm für Linux Mint zum Katalogisieren, Sichern und Prüfen von Konfigurationen. Autor: Josef. Lizenz: GPL-3.0-only (siehe LICENSE).

Start: `./start.sh`. Python 3, requests, PyGObject und GTK 3 sind erforderlich (Mint-Pakete python3-requests, python3-gi, gir1.2-gtk-3.0). Keine automatische Installation. Version: zentrale Quelle `saveconfig/__init__.py`; `./start.sh --version`.

Für Entwicklung ohne persönliche Verwaltungsdaten: `./start.sh --state-home "$PWD/work/state"`. Quellen standardmäßig Path.home(); ein alternatives Home ist in der Oberfläche oder mit `--home` wählbar. DE/EN inklusive lokaler Hilfe; acht Zusatzsprachen mit Hilfe liegen getrennt unter github/sprachpakete und können in den Einstellungen nachgeladen werden.

Erste Phase: lesender Scan, bekannter und lernbarer Katalog, bewusste Auswahl, Originaldateisicherung, Manifest, Datenbankkopie, Paketinventar und SHA-256-Prüfung. Restore ist ausschließlich eine Vorschau. Keine Installation von Programmen oder Rückschreibung nach /etc.

Bekannte sensible Bereiche sind gekennzeichnet. Unbekannte Pfade werden vorsorglich als potenziell sensibel behandelt; Daten, Caches und unbekannte Pfade sind abgewählt. Backupordner erhalten Modus 0700. Originalrechte bleiben erhalten. Symlinks werden unverändert gespeichert, niemals dereferenziert. Spezialdateien werden ausgelassen und gemeldet. Schließen Sie Quellanwendungen für konsistente Profile; normale Datenbankdateien werden nicht anwendungsspezifisch gesichert.

Paketinventar beschreibt das laufende System, nicht eine Installation hinter einem alternativen Home. Fehlende Inventarwerkzeuge ergeben null im entsprechenden Feld.

Ein Stand enthält `home/`, gegebenenfalls `system/etc/`, `manifest.json`, `saveconfig.db` und `packages.json`. Prüfungen schreiben `verification.json`. Keine Geheimniswerte werden protokolliert. Integritätsprüfung ist keine Signatur oder Verschlüsselung.

Tests: `python3 -m unittest discover -s tests -v` (isolierte Daten unter work/). Version: siehe `./start.sh --version`.

GitHub-Vorbereitung: `./erstellegithub.sh` erzeugt ausschließlich einen getrennten, geprüften Quellstand unter dist/. Kein Git-Repository, Remote, Commit, Push oder Upload wird dabei angelegt oder ausgeführt. Nicht mehr benötigte Quellstände werden nach Prüfung entfernt. Prüft offensichtliche Geheimnismuster, keine Garantie vollständiger Geheimnisfreiheit.

Nach Benutzerfreigabe: `./erstelledeb.sh` baut ein DEB unter dist/ inklusive Prüfsumme. Das Paket benötigt GTK 3, kein Tkinter. Installation erfolgt bewusst durch den Anwender. Für Installation später `apt install ./saveconfig_<Version>_all.deb` verwenden.

Quellen und DEB werden unter https://github.com/Lehner-007/saveconfig veröffentlicht. Zusatzübersetzungen sind maschinell erstellt; die Muttersprachlerprüfung steht aus.

Profile für VM/PC: Datei → Profile → Profil speichern/laden/importieren/exportieren. Gespeichert werden Quell-Home, Ziel und ausgewählte Bereiche unter ~/.config/saveconfig/profiles/. Kein SSH-Zugriff: PC-Daten müssen lokal erreichbar/gemountet sein. Beim Laden werden Scan-Ergebnisse geleert. Vor einer Sicherung ist ein Scan derselben Quelle erforderlich. Globale Sprache und Fenstergröße bleiben getrennt.

Datei → Einstellungen ist ein einziger Menüeinstieg mit Sprache, Sprachpaketen, Pfaden und Standardanzeige. Sichtbarkeitsfilter verändern weder Auswahl noch Scan-Daten. Cinnamon, Cache und Altdateien bleiben erfasst; unbekannte Konfigurationen bleiben sichtbar. Manuelle Klassifizierung per Rechtsklick bleibt in SQLite erhalten. Schemaerweiterung ohne Löschen vorhandener Kataloge.

Das bearbeitete Profil erscheint oberhalb der Ausgabe und im Fenstertitel; abweichende Pfade oder Auswahlen werden als ungespeicherte Änderungen gekennzeichnet. Ohne gespeichertes Profil wird „Ungespeichertes Profil“ angezeigt. Das Wasserzeichen liegt in der Ergebnisausgabe und blockiert keine Eingaben.

Gemeinsamer Stand 0.4.0: Profile und Einstellungen unter Datei mit sichtbaren Trennlinien; Sprache bei Sprachpaketen. Bestehende Arbeiten verwenden ein zentriertes Fortschrittsfenster mit aktuellem Bereich und sicherem Abbruch. Tabellen haben abwechselnde Zeilenfarben. Die vorhandene Fenstergrößenspeicherung berücksichtigt jetzt Position, maximierten Zustand und fehlende Monitore. Protokollsitzungen werden sichtbar getrennt. Die Versionsprüfung wird bei jedem Start aufgerufen; zusätzliche Prüfungen sind optional und Monate entsprechen 30 Tagen. GitHub-Quellen bleiben mangels bestätigtem Repository zunächst intern leer; Adressfelder werden nicht angezeigt. Keine zusätzlichen Ergebnisexportformate oder Demos. GTK 3 bleibt erhalten.

## Gemeinsame Darstellung in 0.5.0

Das aktive Profil steht auf einer eigenen hervorgehobenen Fläche mit Symbol; geänderte Werte bleiben als ungespeichert markiert. Hilfe → Info zeigt verwendete Abhängigkeiten. Die Softwareversion wird bei jedem Start geprüft. Einstellungen zeigt den Status und einen geprüften DEB-Download für neuere Versionen. Projektquellen sind intern festgelegt. SHA-256, Paketname, Version und Architektur werden vor Bereitstellung geprüft; keine automatische Installation. Vier stabile Fortschrittszeilen, Menütrenner, Protokollsitzungen, Fensterzustand und Tagesstand-Ergänzungen bleiben erhalten.

Die Update- und Sprachquellen sind noch nicht veröffentlicht und daher intern unkonfiguriert. Der Status weist darauf hin; Download bleibt deaktiviert. DE/EN und eigene lokale Pakete funktionieren offline.

## Prüfbericht – 06.10.2026 (0.6.0)

Manifeste werden vor jeder Verwendung auf Struktur, Pfade und Größenlimit (512 MiB) geprüft. Zusätzliche Dateien im Sicherungsordner werden als Fehler gemeldet, niemals gelöscht. Auch unveränderte Tagesstände werden erneut geprüft. Bereits gesicherte Bereiche werden am selben Tag nicht überschrieben; für geänderte Inhalte ein anderes Sicherungsziel wählen. Neue ausgewählte Bereiche können weiterhin ergänzt werden.

Reguläre Dateien und Verzeichnisse erhalten erweiterte Attribute; die Prüfung vergleicht diese bei neuen Sicherungen. Nicht kopierbare Attribute führen zu einem Fehler statt zu einer erfolgreichen Sicherungsmeldung. Benutzer-/Gruppenbesitz und Hardlink-Beziehungen werden nicht rekonstruiert. ACL-Attribute werden nur soweit vom Dateisystem und Benutzer unterstützt kopiert; eine vollständige Systemwiederherstellung wird nicht zugesichert. Die Platzprüfung ermittelt für neue Sicherungen die aktuelle Dateigröße statt ausschließlich den Scanwert zu verwenden.

Restore bleibt eine schreibfreie Vorschau mit Integritätsstatus. Beschädigte Verwaltungsdaten werden beim Start verständlich gemeldet und unverändert erhalten; mit --state-home kann eine getrennte Verwaltung verwendet werden. Profile und importierte Sprachpakete sind auf 2 MB begrenzt. Importierte Hilfe erlaubt ausschließlich einfache lokale HTML-Inhalte ohne Skripte, CSS oder externe Ressourcen.

Paketierung: Installationsstarter verwenden Python -B. Benötigte Bauwerkzeuge sind dpkg-deb (dpkg), Python 3 und die dokumentierten Python-/GTK-Pakete. remove/purge bearbeiten programmgesteuerte Starter und vorgemerkte Verwaltungsordner auch nach Entfernung der Programmdateien. Persönliche Starter, verlinkte Eltern und externe Sicherungen bleiben erhalten; Upgrades lösen keine Bereinigung aus. Eine echte APT-Installation/Deinstallation steht weiterhin aus.

Nicht automatisiert: Mount-Identitätsprüfung für getrennte OMV-/PC-Quellen, konsistente Sicherung laufender Quellanwendungen, echte Wiederherstellung und Aufbewahrungsregeln. Vor der Sicherung gemountete Quellen und Ziele sowie die ausgewählten Bereiche kontrollieren. Es werden keine Benutzersicherungen automatisch gelöscht.

Stand 0.6.4: Verzeichnisattribute werden bei neuen Sicherungen erfasst und geprüft. Ältere Manifeste ohne diese Angaben bestätigen keine Verzeichnisattribute. Geschützte Restpfade führen zu einer unvollständigen Bereinigungsmeldung. Vor Wiederverwendung eines Tagesstands wird auf unveränderte vorhandene Bereiche hingewiesen.

## SMB / OMV (0.7.0)

SMB / OMV: Neben dem Sicherungsziel „SMB / OMV …“ öffnen, Servername oder IP und Freigabename eingeben. Zugangsdaten werden im Systemdialog abgefragt; saveconfig speichert kein Passwort. Ein erreichbarer Server sowie gvfs-backends und gvfs-fuse sind erforderlich. Erst nach erfolgreicher Verbindung wird das Ziel übernommen. Bei getrennter Verbindung wird kein lokaler Ersatzordner erstellt. OMV ist derzeit noch nicht im Netz; eine echte Verbindung ist ungeprüft. Metadatenerhalt und Tagesstand-Ergänzungen hängen von den Fähigkeiten des entfernten Dateisystems ab; fehlende Unterstützung wird nicht als erfolgreiche Sicherung behandelt.

Die gvfs-fuse-Einbindung liegt unter /run/user/<UID>/gvfs. Es werden keine System-Mounts, fstab-Einträge oder Pakete automatisch eingerichtet. Server und Freigabe werden gespeichert; Profile behalten wie bisher das ausgewählte Ziel. Nach Anmeldung/Neustart die Freigabe erneut verbinden.

SMB-Servereintrag `omv` verwendet die HostName-Adresse aus dem SSH-Alias `omv`. Die SSH-Konfiguration wird nur gelesen; keine SSH-Verbindung hergestellt und keine Schlüssel für SMB verwendet. Der Alias ist auf diesem Rechner noch nicht eingerichtet. Serveradresse und SMB-Freigabe können später ergänzt werden.

Server/SSH-Alias und SMB-Freigabe sind in Datei → Profile pro Profil editierbar. `omv` kann dort bereits offline hinterlegt werden. Profilwechsel lädt die passenden Werte; Profilimport und -export nehmen sie mit. Zugangsdaten werden nicht im Profil gespeichert. Verbinden erfolgt über SMB / OMV neben dem Sicherungsziel.

Cache-Daten werden seit 0.7.3 nicht gesichert, auch nicht über Alles auswählen, Profile oder CLI. Ausgeschlossen sind als Cache klassifizierte Bereiche sowie Pfadbestandteile .cache, cache, caches, cache2, Code Cache und GPUCache. Bereits vorhandene Sicherungsdateien werden nicht entfernt.

Codex-Verzeichnisse (.codex, Codex/codex, codex-app, codex-runtimes) werden seit 0.7.5 nicht angezeigt oder gesichert. Bestehende Tagesstände bleiben unverändert und können weiterhin Codex-Daten enthalten.


## Netzlaufwerk-Schutz (0.8.0)

In Datei → Profile für ein klassisch eingehängtes SMB-/NFS-Ziel „Eingehängtes Netzlaufwerk“ wählen. Erwarteten Mountpunkt (z. B. `/mnt/omv-server`) und die exakte Mountquelle (z. B. `//server/backup` oder `server:/export`) hinterlegen. Vor Anlegen des Sicherungsziels müssen Mountpunkt, Quelle und Netzwerkdateisystem mit `/proc/self/mountinfo` übereinstimmen. Fehlende oder falsche Mounts werden abgewiesen. Lokale Ziele bleiben erlaubt; der bekannte Pfad `/mnt/omv-server` verlangt auch bei alten Profilen eine ausdrückliche Netzwerkdeklaration. Desktop-SMB über GVfs behält seinen bestehenden eigenen Mountschutz. Alte Profile erhalten lokale Standardwerte; vorhandene Profile wurden nicht geändert.

CLI: `backup --target-kind network --mount-point /mnt/omv-server --mount-source //server/backup --destination /mnt/omv-server/saveconfig --path "~/.config/filezilla"`. JSON nennt `reused`, `existing_areas_unchanged` und `backup_date`. Wiederverwendung prüft den alten Stand, übernimmt aber keine Änderungen bereits enthaltener Bereiche.

Der echte OMV-Server ist weiterhin offline. Verbindungen, xattrs, Sperren, atomare Tagesstanderweiterung und Netzverlust sind noch nicht real getestet. Der Mountcheck vor Beginn ist keine Garantie für einen während der Sicherung dauerhaft verfügbaren Server. Gleichnamige Cache-/Codex-Ordner bleiben gemäß Auftrag ausgeschlossen. Keine Lockerung dieser Ausschlüsse.
