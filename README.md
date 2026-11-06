# J-Keebs Hardware Manager

Ein lokaler Windows-Gerätebrowser mit Schwerpunkt auf Tastaturen. Er zeigt aktuell verbundene und – soweit Windows bzw. die eigene Historie sie kennt – früher verbundene Geräte samt Vendor ID (VID), Product ID (PID), Hersteller, Status und Zeitinformationen.

**Projektstatus:** Planung / Implementierung – Funktionen und Plattformunterstützung müssen anhand der Roadmap validiert werden.

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

Die endgültigen Voraussetzungen hängen von den in WP-01 ausgewählten Windows-Schnittstellen und dem GUI-Toolkit ab. Ziel ist Windows 10/11 und eine unterstützte Python-Version. Verbindliche Versionsangaben werden ergänzt, sobald sie getestet sind.

## Entwicklung

Die konkrete Installations- und Startanleitung wird ergänzt, sobald Projektstruktur und Abhängigkeiten feststehen. Bis dahin gilt:

1. Repository klonen.
2. Virtuelle Umgebung erstellen.
3. Abhängigkeiten aus der festgelegten Projektdatei installieren.
4. Anwendung über den dokumentierten Entry Point starten.
5. Tests mit dem dokumentierten Testkommando ausführen.

Beispiel für eine virtuelle Umgebung:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## Dokumentation

- `ROADMAP.md` – Meilensteine und Akzeptanzkriterien
- `AGENTS.md` – Regeln für KI-Agenten und Implementer
- `IMPLEMENTER_PROMPT.md` – ausführlicher Implementierungsauftrag

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

## Lizenz

Noch festzulegen.
