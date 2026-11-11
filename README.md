# J-Keebs Hardware Manager

Ein lokaler Windows-Gerätebrowser mit Schwerpunkt auf Tastaturen. Er zeigt aktuell verbundene und – soweit Windows bzw. die eigene Historie sie kennt – früher verbundene Geräte samt Vendor ID (VID), Product ID (PID), Hersteller, Status und Zeitinformationen.

**Projektstatus:** WP-03 – plattformunabhängige PnP-Mappinglogik und Windows-SetupAPI/CfgMgr32-Adapter implementiert. Der echte Windows-Hardwaretest steht noch aus; GUI und Historienintegration folgen.

## Warum?

Wer regelmäßig Tastaturen, Controller oder andere USB-Geräte testet, muss für VID/PID und Geräteinformationen oft durch den Windows-Geräte-Manager navigieren. Der J-Keebs Hardware Manager soll diese Informationen in einer kompakten, durchsuchbaren Liste bereitstellen.

## Geplante Funktionen

- Aktuelle und historisch bekannte PnP-/USB-Geräte
- Schwerpunktfilter für Tastaturen
- Filter für Tastaturen, USB-Geräte und alle unterstützten Geräte
- Filter für verbunden/getrennt
- Suche und Sortierung
- Gerätename, Hersteller, VID, PID, Gerätetyp und technische IDs
- Letzte Beobachtung mit Herkunft und Genauigkeit
- Lokale SQLite-Historie
- Detailansicht und Kopieraktionen
- Einträge einzeln oder mehrfach aus der App-Historie löschen
- CSV-Export
- Windows-2000-inspirierte Oberfläche nach dem visuellen Vorbild der J-Keebs-Kontaktseite

## Zeitangaben richtig verstehen

Windows stellt nicht für jedes Gerät einen verlässlichen, universellen Zeitpunkt bereit, zu dem es zuletzt physisch angeschlossen wurde. Deshalb soll die Anwendung Zeitinformationen unterscheiden:

- **Windows-Metadatum:** Von Windows gelieferter Wert; Quelle und Aussagekraft werden angegeben.
- **Erstmals von der App beobachtet:** Zeitpunkt des ersten erfolgreichen Scans, bei dem die App das Gerät gesehen hat.
- **Zuletzt als verbunden beobachtet:** Letzter Scan, bei dem das Gerät als vorhanden erkannt wurde.
- **Zuletzt als getrennt beobachtet:** Letzter Scan, bei dem ein vorher bekanntes Gerät als nicht vorhanden erkannt wurde.

Die eigene Historie beginnt erst, wenn die Anwendung erstmals läuft. Kurze Verbindungen zwischen zwei Scans können bei einer reinen Scanstrategie unentdeckt bleiben.

## Sicherheit und Datenschutz

- Geräteinformationen werden lokal verarbeitet und gespeichert.
- Keine Telemetrie und keine Cloud-Synchronisierung.
- Die Löschfunktion entfernt ausschließlich Einträge aus der Anwendungsdatenbank.
- Das Programm deinstalliert keine Windows-Geräte und entfernt keine Treiber.
- Die Anwendung soll ohne Administratorrechte funktionieren, soweit Windows dies zulässt.

## Voraussetzungen

Ziel ist Windows 10/11 x64. Für den aktuellen, plattformunabhängigen Python-Kern gilt CPython 3.12 oder neuer. GUI- und native Windows-Abhängigkeiten können diese Anforderung später noch konkretisieren.

## Entwicklung

### Python-Kern (WP-02)

Voraussetzung: CPython 3.12 oder neuer. Der aktuelle Kern verwendet nur die Python-Standardbibliothek; für Entwicklungstests kommt pytest hinzu.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
```

Die SQLite-Datenbank wird über `Database(path)` geöffnet. Für Tests kann `Database(":memory:")` verwendet werden. Das Datenmodell und die Persistenzschicht sind unabhängig von Windows-APIs.

**Validiert:** 12 Tests erfolgreich unter Windows mit CPython 3.14.0 und pytest 9.2.0 (`12 passed in 0.31s`, 11.11.2026).

Die konkrete Installations- und Startanleitung folgt mit der Anwendung. Für die WP-01-Machbarkeitsprüfung liegt ein read-only Snapshot-Skript vor. In einer normalen, nicht erhöhten PowerShell-Sitzung im Repository-Ordner ausführen:


```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\collect-pnp-snapshot.ps1
```

Das Skript erzeugt `pnp-snapshot.json`. Vor dem Teilen bitte Namen und Hardware-IDs prüfen. Es ändert keine Geräte- oder Treibereinstellungen und exportiert keine rohen Instance IDs oder Seriennummern.

## Dokumentation

- `ROADMAP.md` – Meilensteine und Akzeptanzkriterien
- `AGENTS.md` – Regeln für KI-Agenten und Implementer
- `IMPLEMENTER_PROMPT.md` – ausführlicher Implementierungsauftrag
- `docs/windows-data-sources.md` – WP-01-Datenquellen, Architekturentscheidung und Validierungsstatus
- `docs/data-model.md` – Domänenmodell, SQLite-Schema und Repository-Verwendung
- `docs/pnp-discovery.md` – SetupAPI/CfgMgr32-Adapter, Statusmodell und Tests
- `pyproject.toml` – Paketmetadaten und Entwicklungsabhängigkeiten
- `scripts/collect-pnp-snapshot.ps1` – read-only PnP-Snapshot für Windows

## Designreferenz

Die Oberfläche orientiert sich an der Windows-2000-Ästhetik und an der J-Keebs-Kontaktseite:

https://brotbeutel.github.io/j-keebs/contact.html

Die Referenz dient als Inspiration für klassische Titelleisten, graue Flächen, 3D-Controls, kompakte Systemschrift und Statusleisten. Es werden keine fremden Website-Inhalte oder Assets ungeprüft übernommen.

## Bekannte Grenzen

- Historische Geräteinformationen hängen davon ab, was Windows noch kennt und was die App selbst bereits protokolliert hat.
- Geräte können mehrere Interfaces besitzen.
- VID/PID sind USB-Kennungen und nicht für jedes PnP-Gerät verfügbar.
- Hersteller- und Produktstrings können fehlen oder generisch sein.
- Ein „zuletzt angeschlossen“-Zeitpunkt kann nur dann exakt sein, wenn eine belastbare Ereignisquelle dies hergibt.
- Echte Windows-10/11-Snapshots, Property-Berechtigungstests und der SetupAPI-Integrationstest müssen noch auf dem Zielrechner ausgeführt werden.
- Der erste Discovery-Adapter liest klassische `SPDRP_*`-Eigenschaften. HID Usage Page/Usage sowie Treiberanbieter/-version sind noch nicht implementiert.

## Lizenz

Noch festzulegen.
