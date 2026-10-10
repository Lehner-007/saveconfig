## 0.8.4

- Alle zehn Hilfesprachen verwenden eine aktuelle, platzsparende Kopie des Programmbilds.
- DEB liefert dasselbe aktuelle Motiv für Hilfe und Desktop-Symbol.

## 0.8.3

- Neues saveconfig-Bild als Symbol für Menü- und Desktop-Starter im DEB.

# 0.8.2

- Hilfe einheitlich über Hilfe → Hilfe und F1 erreichbar; Hinweis in DE/EN.

# 0.8.1

- Programmlogo in deutscher und englischer Hilfe eingebettet; Hilfeseiten bleiben eigenständig nutzbar.

# 0.8.0

- Profile: Zielart, erwarteter Mountpunkt und Freigabe für eingehängte Netzlaufwerke.
- Netzwerkziel wird vor mkdir gegen Linux-Mountidentität geprüft; /mnt/omv-server benötigt explizite Netzwerkdeklaration.
- CLI berichtet Tagesstand-Wiederverwendung ausdrücklich.
- Reale OMV-Abnahme und Paketinstallation weiterhin offen.

# 0.7.5 – 06.10.2026

- Codex-Verzeichnisse aus Scanliste und Sicherung ausgeschlossen; gilt auch für Profile, CLI und Auswahl aller Bereiche.

# 0.7.4 – 06.10.2026

- Cache-Anzeigefilter und Cache-Zeilen entfernt. Platzfehler zeigt Bedarf und freien Speicher; Tagesstand-Ergänzung berechnet aktuelle Größen ohne Cache.

# 0.7.3 – 06.10.2026

- Cache-Bereiche von Auswahl, Profilübernahme und Sicherung ausgeschlossen; bekannte Cache-Unterordner werden auch innerhalb ausgewählter Programme ausgelassen.

# 0.7.2 – 06.10.2026

- SMB-Server/SSH-Alias und Freigabe im Profil hinterlegen, offline bearbeiten und beim Profilwechsel laden.

# 0.7.1 – 06.10.2026

- SMB-Servereintrag omv löst die HostName-Adresse des SSH-Alias lesend auf; fehlender Alias wird verständlich gemeldet.

# 0.7.0 – 06.10.2026

- SMB-/OMV-Ziel über Desktop-GVfs verbinden, mit System-Anmeldedialog, Abbruch und Verbindungszeitlimit.
- SMB-Ziele vor Sicherungsbeginn auf Einbindung prüfen; kein lokaler Ersatzordner.

# 0.6.4 – 06.10.2026

- Verzeichnis-xattrs erfasst und geprüft; ältere Manifeste bleiben lesbar.
- Geschützte Bereinigungspfade ergeben unvollständigen Status statt Erfolg.
- Hinweis vor Tagesstand-Wiederverwendung; aktuelle Versionsdokumentation korrigiert.

# 0.6.3 – 06.10.2026

- Schließen des Fortschrittsfensters löst Abbruch aus und entfernt das Fenster sofort; laufende Arbeiten bleiben bis zum sicheren Ende gesperrt.

# 0.6.2 – 06.10.2026

- Abbruch auch während Lesen und Validieren großer Manifeste berücksichtigt; Fortschritt zeigt die Manifestprüfung an.

# 0.6.1 – 06.10.2026

- Manifestgrenze auf 512 MiB korrigiert, damit große eigene Sicherungen lesbar bleiben; Größenfehler getrennt von Strukturfehlern gemeldet.

# 0.6.0 – 06.10.2026

- Manifestprüfung begrenzt und gegen ungültige Datensätze gehärtet; zusätzliche Dateien gemeldet.
- Vorhandene Tagesstände vor Wiederverwendung geprüft, Wiederverwendung ausdrücklich angezeigt.
- Restore-Vorschau mit schreibfreier Integritätsprüfung.
- Erweiterte Dateiattribute kopiert und geprüft; aktuelle Größe bei neuen Sicherungen geprüft.
- Verständliche Startmeldung bei beschädigtem Katalog, ohne Originaldaten zu verändern.
- Größenlimits für Importe und ausschließlich lokale, passive Sprachhilfe.
- Paketstarter ohne Bytecode; remove/purge mit eigenständiger, geschützter Bereinigung.

# 0.5.0

- Über-Fenster gemäß Dialogvorlage: Info/Mitwirkende oben, Lizenzlink im Text, keine zusätzlichen Aktionsbuttons.

- Aktives Profil mit eigener Theme-Fläche und Symbol hervorgehoben.
- Hilfe → Info für tatsächlich verwendete Abhängigkeiten.
- Versionsprüfung bei jedem Start, Status und geprüfter DEB-Download.
- GitHub-Quellen intern festgelegt; Sprache und Hilfe aktualisiert.

# Änderungen

## 0.4.0 – 04.10.2026

Tagesstand um noch nicht gesicherte ausgewählte Bereiche ergänzen, bestehende Bereiche erhalten. Ergänzungen vor Veröffentlichung vollständig prüfen; Abbruch und Fehler bewahren den bisherigen Stand. Vier feste Fortschrittszeilen. Protokollanzeige unter Hilfe mit Aktualisieren und Textexport ergänzt.

## 0.3.3 – 04.10.2026

Je Sicherungsziel nur einen Tagesordner dd.mm.yyyy anlegen. Wiederholte Sicherung am selben Tag meldet den vorhandenen Ordner und erhält ihn unverändert. Alte Sicherungsordner weiterhin lesbar.

## 0.3.2 – 04.10.2026

Profilverwaltung unter Datei mit Profilliste links, Name, Quelle und Ziel rechts. Änderungen erst bei Speichern/Übernehmen übernehmen. Aktives Profil dauerhaft im Hauptfenster anzeigen; gespeicherte Auswahl beim Neustart wiederherstellen.

## 0.3.1 – 04.10.2026

Über-Bild auf höchstens 128 × 128 verkleinert. Fortschrittsausgabe hält drei Textzeilen bereit; längere Ausgaben sind scrollbar, ohne das Fenster zu vergrößern. Datumsanzeige der Sicherungsliste auf dd.mm.yyyy vereinheitlicht.

## 0.3.0 – 04.10.2026

Gemeinsame Darstellung für bestehende GTK-3-Funktionen: Profile und Einstellungen unter Datei mit sichtbaren Trennlinien, Sprache bei Sprachpaketen, zentriertes Fortschrittsfenster, wechselnde Zeilenfarben und getrennte Protokollsitzungen. Gespeicherten Fensterzustand bei fehlenden Monitoren erreichbar wiederherstellen. Optionalen Pflichtbereich für manuelle und automatische Versionsprüfungen ergänzt; deshalb MINOR. Vorhandene Profile, Sicherungsauswahl, Klassifizierung, lesende Restore-Vorschau und Sicherungsformate erhalten. Keine zusätzlichen optionalen Exportfunktionen oder Demos.

## 0.2.2 – 03.10.2026

Wasserzeichen vom Statusbereich in die Ergebnisausgabe verschoben. Bearbeitetes Profil im Fenstertitel und oberhalb der Ausgabe, einschließlich Hinweis auf ungespeicherte Änderungen.

## 0.2.1 – 03.10.2026

Einstellungen zu einem Dialog zusammengeführt. Cinnamon-Pfade korrekt klassifiziert; reine Anzeigefilter für Programme, Desktop, Caches, Unbekannte und Altdateien. Standardfilter gespeichert, Klassifizierung per Kontextmenü dauerhaft im Katalog. Datenbankmigration erhält vorhandene Daten. Versionsnummer ausdrücklich gemäß Änderungsauftrag.

## 0.2.0 – 03.10.2026

Speicherbare, importierbare und exportierbare VM/PC-Profile, gegliederter Einstellungsdialog und Über-Dialog nach Checkweb-Aufbau mit Projektbild. Quellwechsel erfordert erneuten Scan.

## 0.1.0 – 03.10.2026

Erster Entwicklungsstand: GTK 3, SQLite-Katalog, Scan, Dateisicherung, Manifest, Paketinventar, Integritätsprüfung und lesende Restore-Vorschau. Deutsch/Englisch und Offline-Hilfe. Wiederherstellung ohne Schreibfunktion in Phase 1.
