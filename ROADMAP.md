# Roadmap – J-Keebs Hardware Manager

## Produktvision

Ein kleines, lokales Windows-Werkzeug, das Hardwaregeräte – insbesondere Tastaturen – samt VID/PID und Gerätehistorie schnell auffindbar macht. Es soll den umständlichen Weg durch den Windows-Geräte-Manager ersetzen, ohne selbst Windows-Geräte oder Treiber zu verändern.

## Leitprinzipien

- **Historie statt Momentaufnahme:** Aktuelle und früher erkannte Geräte gehören in eine gemeinsame Übersicht.
- **Ehrliche Zeitangaben:** Ein geschätzter oder erstmals beobachteter Zeitpunkt darf nicht als exakter Anschlusszeitpunkt ausgegeben werden.
- **Lokal und privat:** Geräteinformationen bleiben lokal; keine Telemetrie.
- **Sicheres Löschen:** Nur die eigene App-Datenbank wird verändert.
- **Keyboard-first:** Tastaturen sind der wichtigste Filter und Anwendungsfall.
- **Retro-UI mit Nutzwert:** Windows-2000-Look, aber gute Lesbarkeit und effiziente Bedienung.

## Meilensteine

### WP-01 – Projektgrundlage und technische Machbarkeit

**Ziel:** Repository, Laufzeit und Windows-Datenquellen klären.

Aufgaben:
- Repository und vorhandene Dateien untersuchen.
- Python-Version und Ziel-Windows-Version festlegen.
- PnP-Datenquellen evaluieren (z. B. Windows CIM/PnP, SetupAPI oder PowerShell als kontrollierter Adapter).
- Prüfen, welche Daten ohne Administratorrechte lesbar sind.
- Kleine repräsentative Geräte-Snapshots dokumentieren.

Akzeptanz:
- Architekturentscheidung mit Begründung liegt vor.
- Datenquellen und Grenzen sind in `docs/windows-data-sources.md` beschrieben.
- Keine fragilen Annahmen über universelle Windows-Zeitstempel.

### WP-02 – Datenmodell und SQLite

**Ziel:** Geräte und Beobachtungsereignisse lokal speichern.

Aufgaben:
- Domänenmodell für Geräte und Beobachtungen.
- SQLite-Schema und Migrationen.
- UTC-Zeitstempel.
- Repository-Schicht und Tests.

Akzeptanz:
- Geräte können angelegt, aktualisiert, abgefragt und aus der App-Historie gelöscht werden.
- Wiederholte Scans erzeugen keine unkontrollierten Duplikate.
- Zeitstempelquelle und Zeitstempeltyp bleiben erhalten.

### WP-03 – Windows-PnP-Erkennung

**Ziel:** Aktuelle und historisch bekannte Geräte erkennen.

Aufgaben:
- PnP-Discovery-Adapter.
- VID/PID und Hardware-IDs auslesen.
- Tastaturen, USB-Geräte und allgemeine PnP-Geräte kategorisieren.
- Verbunden/Getrennt-Status bestimmen.
- Fehler einzelner Geräte isolieren.
- Composite-Geräte und mehrere Interfaces untersuchen.

Akzeptanz:
- Aktuelle Tastaturen werden erkannt.
- Abgezogene, in Windows noch bekannte Geräte werden soweit möglich angezeigt.
- Nicht verfügbare Felder bleiben leer/„Nicht verfügbar“.
- Erkennung funktioniert möglichst ohne Adminrechte.

### WP-04 – Historien-Tracker

**Ziel:** Eigene, ab dem ersten Programmlauf verlässliche Beobachtungshistorie aufbauen.

Aufgaben:
- Manuelle Aktualisierung und Scanservice.
- Neue Geräte und Statuswechsel protokollieren.
- Erstmalig beobachtet, zuletzt verbunden beobachtet und zuletzt getrennt beobachtet getrennt führen.
- Optional konfigurierbares Scanintervall prüfen.

Akzeptanz:
- Statusänderungen erzeugen nachvollziehbare Ereignisse.
- Die Oberfläche unterscheidet Windows-Metadaten von App-Beobachtungen.
- Grenzen durch verpasste kurze Verbindungen sind dokumentiert.

### WP-05 – GUI-Grundgerüst im Win2k-Stil

**Ziel:** Hauptfenster und Navigation gestalten.

Aufgaben:
- UI-Toolkit auswählen und begründen.
- Windows-2000-inspirierte Fenster-, Panel-, Button- und Tabellenoptik.
- J-Keebs-Farb- und Typografie-Anleihen dezent integrieren.
- Statusleiste.

Akzeptanz:
- Hauptfenster ist auf üblichen Desktop-Auflösungen nutzbar.
- Tabellenkopf, Filter, Suche und Statusleiste sind klar erkennbar.
- Kein modernes Karten-/Dashboard-Design, das den Retro-Charakter verwässert.

### WP-06 – Geräteübersicht und Interaktionen

**Ziel:** Geräte schnell finden und verwalten.

Aufgaben:
- Sortierbare Tabelle.
- Suche über Name, Hersteller, VID, PID und IDs.
- Filter Tastaturen / USB / Alle.
- Filter Verbunden / Getrennt.
- Doppelklick-Details.
- Kontextmenü.
- Kopieraktionen.
- Mehrfachauswahl und sichere Löschbestätigung.

Akzeptanz:
- VID:PID ist ohne Detaildialog sichtbar und kopierbar.
- Filter und Suche lassen sich kombinieren.
- Löschen entfernt nur App-Daten.
- Mehrfachlöschung zeigt Anzahl und Konsequenz vor der Bestätigung.

### WP-07 – Details und CSV-Export

**Ziel:** Technische Informationen und externe Weiterverarbeitung ermöglichen.

Aufgaben:
- Detailansicht mit allen verfügbaren Feldern.
- Kennzeichnung fehlender Daten und Quellen.
- CSV-Export der gefilterten Liste und/oder Auswahl.
- Sinnvolle UTF-8-Kodierung und Excel-Kompatibilität prüfen.

Akzeptanz:
- Alle Kernfelder sind in Details einsehbar.
- CSV enthält stabile Spaltennamen und korrekt formatierte VID/PID-Werte.
- Export überschreibt keine Datei ohne Rückfrage.

### WP-08 – Stabilität, Packaging und Dokumentation

**Ziel:** Alltagstaugliche portable Anwendung.

Aufgaben:
- Fehlerbehandlung und Logging ohne unnötige personenbezogene Inhalte.
- Tests auf sauberer Windows-Umgebung.
- Portable EXE prüfen (z. B. PyInstaller), falls sinnvoll.
- Datenbankpfad, Backup und Reset dokumentieren.
- README und Bedienhinweise finalisieren.

Akzeptanz:
- Start ohne Entwicklungsumgebung ist getestet, sofern EXE-Build umgesetzt wird.
- Daten bleiben bei App-Updates erhalten.
- Bekannte Einschränkungen sind dokumentiert.
- Keine Adminpflicht ohne zwingenden technischen Grund.

## Definition of Done für jedes Arbeitspaket

- Akzeptanzkriterien erfüllt oder Abweichungen ausdrücklich dokumentiert.
- Tests ergänzt und tatsächlich ausgeführt.
- Keine unbeabsichtigten Änderungen an Windows-Geräten/Treibern.
- README bzw. technische Dokumentation aktualisiert.
- Abschlussbericht mit Dateien, Tests, offenen Punkten und nächstem Schritt.

## Risiken und offene Entscheidungen

| Thema | Risiko / Frage | Umgang |
|---|---|---|
| Windows-Zeitstempel | Kein universeller, zuverlässiger Last-connected-Wert | Quelle und Genauigkeit pro Zeitwert speichern; eigene Historie |
| Geräteidentität | Instance IDs können sich durch Port/Verbindung ändern | Instance ID, Container-ID, Seriennummer und Hardware-IDs getrennt speichern |
| Composite-Geräte | Ein Gerät kann mehrere HID-/USB-Interfaces melden | Gruppierung nur bei belastbaren Merkmalen |
| Historische Geräte | Windows kann Einträge entfernen oder Informationen begrenzen | App-Historie unabhängig davon führen |
| Rechte | Manche Details können erhöhte Rechte erfordern | Best effort, verständliche Hinweise |
| Polling | Kurze Verbindungen zwischen Scans können fehlen | Manuelles Aktualisieren; Polling als optionales Feature |
| Packaging | Windows-Sicherheitssoftware kann unbekannte EXE melden | reproduzierbarer Build und klare Herkunft der Artefakte |

## Nicht-Ziele für die erste Version

- Geräte deinstallieren oder Treiber verwalten.
- Registry-Cleaner-Funktionen.
- Firmware flashen oder Tastaturen konfigurieren.
- Cloud-Synchronisierung oder Telemetrie.
- Garantierte Erkennung jedes jemals angeschlossenen USB-Geräts.
