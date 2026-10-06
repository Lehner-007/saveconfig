SEITE
ID: index
META
SPRACHE: de
STATUS: pruefung
VERSION: 2.0
ERSTELLT: 03.10.2026
GEAENDERT: 06.10.2026
TITEL
saveconfig – Hilfe
INHALT
![saveconfig](../../resources/saveconfig.png)

Die Hilfe kann jederzeit mit F1 oder über Hilfe → Hilfe geöffnet werden.

saveconfig sichert Konfigurationen als Originaldateien. SQLite dient nur als Katalog.

Wählen Sie das Home-Verzeichnis und ein getrenntes Sicherungsziel. Starten Sie „Datei → Konfigurationen suchen“. Der Scan liest die Quellen ausschließlich. Bekannte Konfigurationen sind ausgewählt; unbekannte Bereiche, Programmdaten und Systemkonfigurationen erfordern eine bewusste Auswahl. Cache-, temporäre und Codex-Daten sind aus Katalog und Sicherungen ausgeschlossen, auch in Unterordnern. Ein Klick in die Spalte „Sichern“ ändert die Auswahl. Tabellen lassen sich über die Spaltenköpfe sortieren. Neue Pfade können unter „Katalog“ nach Bestätigung gespeichert werden.

„Datei → Ausgewählte sichern“ erstellt einen eigenen Stand mit home/, system/, manifest.json, saveconfig.db und packages.json. Sensible Daten werden unverschlüsselt kopiert; schützen Sie das Sicherungsmedium. Symlinks bleiben Links und werden nicht verfolgt. Sockets und andere Spezialdateien werden mit Warnung ausgelassen. Laufende Anwendungen möglichst vorher schließen: normale SQLite- und Profildateien werden als Dateien kopiert, ohne eine anwendungsspezifische Konsistenzgarantie.

Die Paketliste beschreibt den aktuell laufenden Rechner, auch bei einem alternativen Home. Fehlende Paketwerkzeuge werden im Inventar als null gekennzeichnet. Es werden keine Pakete installiert.

Sicherungen anzeigen: Doppelklick zeigt die Bereiche. „Sicherung prüfen“ kontrolliert Dateitypen, Größen, Rechte, SHA-256, Datenbank und Paketliste. Das Prüfergebnis steht separat in verification.json. Es ist eine Zeitpunktprüfung, kein dauerhafter Schutz gegen Manipulation. Abgebrochene oder fehlerhafte Stände gelten nicht als vollständig.

Wiederherstellung ist in dieser Phase nur eine Vorschau. Manuell können Originaldateien aus home/ in ein vorbereitetes Home kopiert werden. Bestehende Daten vorher separat sichern; Rechte und Linkziele kontrollieren. system/etc nicht vollständig zurückspielen. Programme zuerst passend installieren.

Aktionen laufen im Hintergrund. „Datei → Abbrechen“ stoppt kontrolliert. Bei getrenntem Ziel kann ein Stand unvollständig bleiben; die Fehlermeldung beachten und anschließend prüfen.

Einstellungen: ~/.config/saveconfig/settings.json. Katalog: ~/.local/share/saveconfig/saveconfig.db. Logs: ~/.local/state/saveconfig/logs/. Für isolierte Entwicklung start.sh --state-home /pfad/zum/testzustand verwenden. Scan schreibt ausschließlich Verwaltungsdaten, keine Quellkonfigurationen.

DE/EN und Hilfe sind offline enthalten. Datei → Einstellungen → Sprache wechselt sofort. Eigene vollständige JSON-Pakete lassen sich importieren. Nachladen verwendet die fest hinterlegte GitHub-Quelle; acht zusätzliche Sprach- und Hilfepakete werden über die fest hinterlegte GitHub-Quelle nach bewusster Auswahl nachgeladen. Eigene Sprachen bleiben erhalten.

Programm: 0.8.2; Autor: Josef; Lizenz: GPLv3. GTK 3 und Python 3 sind erforderlich.

Profile: Speichern Sie VM und PC unter Datei → Profile mit getrennten Home-Pfaden, Sicherungszielen und Auswahlen. Profile lassen sich als JSON importieren und exportieren; vorhandene Namen und Dateien werden geschützt. Beim Laden werden alte Scan-Ergebnisse entfernt. PC-Daten müssen lokal erreichbar oder gemountet sein. Unter Datei → Einstellungen finden Sie Sprache und Pfade in einem gegliederten Dialog. Abbrechen verwirft Änderungen, Einstellungen speichern übernimmt sie.

Anzeige und Klassifizierung: Programme und unbekannte Bereiche sind zunächst sichtbar. System/Desktop und Backup-/Altdateien sind über die Anzeigefilter erreichbar. Cache- und Codex-Daten sind von Scan und Sicherung ausgeschlossen. Die Schalter oberhalb der Tabelle ändern ausschließlich die Sichtbarkeit, nicht die Sicherungsauswahl. Die Standardanzeige speichern Sie im gemeinsamen Einstellungsdialog. Rechtsklick auf eine Zeile erlaubt eine dauerhafte Klassifizierung im Katalog. Ignorieren blendet nur aus und löscht keine Daten. Cinnamon und cinnamon-monitors.xml sind bekannte Desktop-Konfigurationen. Dateien mit ~, .bak, .backup, .old und .orig werden als Altdateien erkannt.
Gemeinsame Darstellung: Datei → Profile öffnet die Profilverwaltung mit der Liste links sowie Name, Quelle und Sicherungsziel rechts. Neu und Löschen verwalten die Liste; Speichern speichert Änderungen, Übernehmen aktiviert das ausgewählte Profil. Abbrechen verwirft Änderungen. Das aktive Profil steht im Hauptfenster und Fenstertitel. Im Menü steht Profile, danach eine sichtbare Trennlinie, Einstellungen, eine weitere Trennlinie und Beenden. Quelle, Sicherungsziel und Standardanzeige stehen oben im Einstellungsdialog. Danach folgen Versionsprüfungen und der gemeinsame Bereich für Sprache und Sprachpakete. Einstellungen speichern übernimmt geprüfte Werte; Abbrechen verwirft Änderungen.

Ein Download wird nur angeboten, wenn eine neuere Veröffentlichung gültige Paketdaten enthält. Fehlgeschlagene Versionsprüfungen beeinträchtigen Sicherungen und Offline-Hilfe nicht.

Laufende Suche, Sicherung oder Prüfung zeigt ein zentriertes Fenster mit dem aktuellen Bereich und Abbrechen. Nach dem tatsächlichen Ende schließt es automatisch. Bei nicht sicher abbrechbaren Sprach- und Versionsabrufen ist Abbrechen deaktiviert. Beim Schließen während einer abbrechbaren Aktion wird nach Bestätigung bis zum sicheren Ende gewartet.

Die Tabellen verwenden wechselnde Zeilenhintergründe; Auswahl und Filter bleiben erhalten. Fenstergröße, Position und maximierter Zustand werden getrennt gespeichert und gegen die erreichbaren Monitore geprüft. Neue Protokollsitzungen werden mit sichtbaren Linien getrennt, ältere Einträge bleiben erhalten. Datumsangaben im Protokoll verwenden DD.MM.YYYY HH:MM:SS.

Pro Sicherungsziel wird ein Tagesordner dd.mm.yyyy angelegt. Weitere ausgewählte Bereiche, die noch nicht enthalten sind, ergänzen diesen Stand. Bereits gesicherte Bereiche werden übersprungen. Bei Abbruch oder Fehler bleibt der bisherige Tagesstand erhalten. Quellen verschiedener Rechner oder Home-Verzeichnisse benötigen getrennte Ziele. Hilfe → Protokoll zeigt frühere und aktuelle Sitzungen mit Trennlinien; Aktualisieren lädt neue Einträge, Protokoll speichern exportiert die sichtbare Ausgabe. Das Fortschrittsfenster reserviert vier Zeilen und scrollt längere Texte.

Das aktive Profil wird im Hauptfenster mit Symbol und einer farblich abgesetzten Fläche hervorgehoben. Ungespeicherte Änderungen bleiben sichtbar gekennzeichnet. Hilfe → Info zeigt tatsächlich verwendete Werkzeuge mit Verfügbarkeit, Version und APT-Paket. Die Softwareversion wird bei jedem Start geprüft; eine zusätzliche Prüfung im laufenden Betrieb ist optional. Einstellungen zeigt Software aktuell, Update verfügbar oder eine fehlgeschlagene Prüfung. Update herunterladen ist nur bei neuerer Version und gültigen DEB-Metadaten aktiv. Das Paket wird im persönlichen Downloadordner gespeichert und auf SHA-256, Paketname, Version und Architektur geprüft. Abbruch entfernt Teil-Dateien. Die Installation erfolgt durch den Anwender. Die GitHub-Quellen sind intern vorgegeben.

Ein Download wird nur angeboten, wenn eine neuere Veröffentlichung gültige Paketdaten enthält. Fehlgeschlagene Versionsprüfungen beeinträchtigen Sicherungen und Offline-Hilfe nicht.

Profile für eingehängte Netzlaufwerke enthalten Zielart, erwarteten Mountpunkt und die genaue Freigabe. Ein fehlender oder falscher Mount wird vor dem Anlegen von Dateien abgewiesen. /mnt/omv-server benötigt diese Netzwerkdeklaration. Desktop-SMB über GVfs verwendet den eigenen Mountschutz. Der echte OMV-Betrieb ist noch nicht abgenommen.

SMB / OMV … neben dem Sicherungsziel verbindet eine verfügbare Freigabe. Servername, SSH-Alias (z. B. omv) und Freigabe werden im Profil gespeichert und können offline vorbereitet werden. Der Alias liefert nur den HostName; SSH-Schlüssel und SSH-Benutzer melden nicht bei SMB an. Zugangsdaten werden vom Systemdialog abgefragt und von saveconfig nicht gespeichert. Erforderlich sind gvfs-backends und gvfs-fuse. Der OMV-Server ist noch offline; eine echte Verbindung muss nach Verfügbarkeit geprüft werden.

ENDE
