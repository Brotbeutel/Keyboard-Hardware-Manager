# Implementer-Auftrag: J-Keebs Hardware Manager

## Rolle und Arbeitsweise

Du bist Implementer für das Projekt **J-Keebs Hardware Manager**. Setze die Roadmap in kleinen, nachvollziehbaren Arbeitspaketen um. Lies zuerst `README.md`, `ROADMAP.md` und `AGENTS.md` vollständig und halte dich daran.

Arbeite nicht nur konzeptionell: Untersuche das vorhandene Repository, implementiere die nächste sinnvolle Einheit, ergänze Tests und Dokumentation und berichte am Ende konkret über Änderungen, Testresultate und offene Punkte. Wenn das Repository noch leer ist, lege eine passende Grundstruktur an.

## Produktziel

Entwickle eine lokale Windows-Desktopanwendung, die angeschlossene und früher angeschlossene Hardwaregeräte übersichtlich auflistet. Der Schwerpunkt liegt auf Tastaturen und Keyboard-Projekten. Das Programm soll den Umweg über den Windows-Geräte-Manager vermeiden, wenn VID/PID, Hersteller, Gerätename oder die zuletzt beobachtete Verbindung eines Geräts benötigt werden.

Arbeitstitel und Produktname: **J-Keebs Hardware Manager**.

## Kernanforderungen

### Geräteerkennung

- Aktuell vorhandene Geräte aus Windows Plug-and-Play (PnP) ermitteln.
- Historisch bekannte bzw. nicht mehr angeschlossene Geräte berücksichtigen, soweit Windows diese Informationen noch bereitstellt.
- Nicht ausschließlich `hid.enumerate()` verwenden: Das würde viele abgezogene Geräte und Nicht-HID-Geräte nicht abdecken.
- Tastaturen als primäre Kategorie behandeln.
- Zusätzlich mindestens USB-Geräte und optional alle geeigneten PnP-Geräte anzeigen.
- Geräte möglichst zuverlässig anhand einer stabilen Identität zusammenführen. `Instance ID` ist ein wichtiger Schlüssel, aber seine Stabilität und Eindeutigkeit ist je nach Gerät/Anschlussart zu berücksichtigen.
- Geräte mit mehreren HID-/USB-/Composite-Interfaces nicht blind als mehrere physische Tastaturen darstellen. Wenn eine sichere Gruppierung nicht möglich ist, Interfaces transparent darstellen und in Details erklären.

### Daten je Gerät

Zeige alle verfügbaren Felder, mindestens:

- Anzeigename / Gerätename
- Hersteller
- Gerätetyp bzw. Geräteklasse
- Vendor ID (VID)
- Product ID (PID)
- kombinierte Schreibweise `VID:PID` (z. B. `046A:C33C`)
- Geräteinstanz-ID (Instance ID)
- Hardware-IDs
- Status: verbunden oder getrennt
- zuletzt beobachteter Anschluss-/Verbindungszeitpunkt
- Quelle und Genauigkeit des Zeitstempels

Zusätzliche Felder, sofern Windows sie liefert:

- Seriennummer
- Container-ID
- Parent-/übergeordnetes Gerät
- Bus-/Enumerator-Information
- HID Usage Page und Usage
- Location Path
- Treiberanbieter und Treiberversion

Fehlende Werte müssen als „Nicht verfügbar“ bzw. „Unbekannt“ dargestellt werden, nicht erfunden oder aus VID/PID-Namen geraten werden.

### Zeitstempel und Historie

Windows stellt nicht für jedes Gerät einen universell verlässlichen „zuletzt angeschlossen“-Zeitstempel bereit. Daher:

1. Ermittle vorhandene Windows-Zeitinformationen und dokumentiere deren konkrete Quelle und Aussagekraft.
2. Baue eine eigene lokale SQLite-Ereignishistorie auf.
3. Erfasse bei jedem Scan neu erkannte Geräte und Statusänderungen.
4. Speichere Zeitpunkte in UTC und stelle sie lokal formatiert dar.
5. Unterscheide sichtbar zwischen:
   - Windows-seitig ermitteltem Zeitpunkt (mit Quellenangabe),
   - erstmals von der Anwendung beobachtet,
   - zuletzt von der Anwendung als verbunden beobachtet,
   - zuletzt von der Anwendung als getrennt beobachtet.
6. Behaupte nicht, einen exakten historischen Anschlusszeitpunkt zu kennen, wenn nur der erste Scanzeitpunkt oder ein ungenauer Windows-Metadatenwert verfügbar ist.
7. Ein Scanintervall kann kurze An-/Absteckvorgänge verpassen. Dokumentiere das und biete einen manuellen Aktualisieren-Button.

Die Anwendung muss auch ohne Administratorrechte möglichst viele Daten lesen können. Wenn einzelne Windows-Informationen erhöhte Rechte benötigen, zeige einen verständlichen Hinweis und fahre mit den verfügbaren Daten fort.

### Oberfläche

Erstelle eine native bzw. gut integrierte Windows-Desktop-GUI im Stil von Windows 2000, inspiriert von:

`https://brotbeutel.github.io/j-keebs/contact.html`

Gestaltungsmerkmale:

- klassische blaugraue Titelleiste
- graue Fenster- und Panel-Flächen
- klassische 3D-Buttons und Eingabefelder
- kompakte Systemschrift
- weiße Tabellenfläche mit klaren Spaltenköpfen
- schmale Statusleiste am unteren Rand
- zurückhaltendes J-Keebs-Branding
- klare Informationshierarchie statt unnötiger Dekoration

Die Referenz ist eine Designinspiration. Kopiere keine Website-Inhalte oder fremde Assets. Wenn die Seite nicht erreichbar ist, orientiere dich an der beschriebenen Windows-2000-Ästhetik und dokumentiere die Abweichung.

### Hauptansicht

- Suchfeld für Name, Hersteller, VID, PID und Instance ID.
- Filter für `Tastaturen`, `USB-Geräte`, `Alle Geräte`.
- Statusfilter `Alle`, `Verbunden`, `Getrennt`.
- Sortierbare Tabelle.
- Sinnvolle Standardspalten: Name, Hersteller, VID, PID, Typ, Status, zuletzt gesehen.
- Aktualisieren-Button.
- Mehrfachauswahl.
- Einträge aus der eigenen Anwendungshistorie löschen.
- CSV-Export der aktuellen Auswahl bzw. gefilterten Liste.
- Doppelklick auf ein Gerät öffnet Details.
- Rechtsklick-Menü mit mindestens: Details anzeigen, VID:PID kopieren, Hardware-ID/Instance ID kopieren, Eintrag löschen.

### Gerätedetails

Eine Detailansicht soll alle verfügbaren technischen Daten zeigen. Kopieraktionen müssen für VID:PID, VID, PID, Instance ID und Hardware-IDs angeboten werden. Unbekannte oder nicht verfügbare Werte müssen eindeutig gekennzeichnet werden.

### Löschen – wichtige Abgrenzung

„Eintrag löschen“ bedeutet ausschließlich, den Datensatz bzw. die lokale Historie in der Anwendung zu entfernen.

- Niemals Windows-Geräteinstanzen deinstallieren.
- Niemals Treiber entfernen.
- Niemals Registry-Geräteschlüssel löschen.
- Vor dem Löschen bestätigen lassen.
- Bei Mehrfachlöschung Anzahl und Auswirkung klar nennen.
- Optional später: „Ausblenden/ignorieren“ als nicht-destruktive Alternative prüfen.

## Technische Leitplanken

- Zielplattform: Windows 10/11, sofern die eingesetzten APIs und Bibliotheken dies unterstützen.
- Sprache: Python.
- Datenhaltung: SQLite in einem benutzerspezifischen lokalen Datenverzeichnis.
- Portable Betriebsart soll möglich sein; Datenbankpfad und Verhalten müssen dokumentiert sein.
- Geräteerkennung über geeignete Windows-PnP-/SetupAPI-/PowerShell-/WMI-Schnittstellen oder eine gut begründete Bibliothek. Bevorzuge robuste, dokumentierte Schnittstellen und vermeide fragile Registry-Heuristiken als alleinige Datenquelle.
- HID-spezifische Zusatzinformationen dürfen ergänzend über `hidapi` gesammelt werden.
- Trenne mindestens Geräteerkennung, Datenmodell/Repository, Historie, GUI und Export.
- Keine Netzwerkverbindung und keine Telemetrie.
- Keine Administratorrechte standardmäßig verlangen.
- Abhängigkeiten begrenzen und in `pyproject.toml` oder einer nachvollziehbaren Dependency-Datei festhalten.
- Keine Shell-Kommandos mit ungeprüften externen Eingaben zusammensetzen.
- Fehler einzelner Geräte dürfen nicht den gesamten Scan abbrechen.

## Vorgeschlagene Architektur

Passe die Architektur bei begründetem Bedarf an und dokumentiere Abweichungen.

```text
src/
  jkeebs_hardware_manager/
    __init__.py
    app.py
    config.py
    domain/
      models.py
    discovery/
      base.py
      windows_pnp.py
      hid.py
    persistence/
      database.py
      repositories.py
      migrations.py
    history/
      tracker.py
    services/
      device_service.py
      export_service.py
    ui/
      main_window.py
      device_details.py
      styles.py
    resources/
tests/
  unit/
  integration/
docs/
  architecture.md
  windows-data-sources.md
```

## Qualität und Tests

- Schreibe Unit-Tests für VID/PID-Parsing, Geräteidentität, Statusänderungen, Zeitstempelquellen, Filter, Suche und CSV-Export.
- Windows-spezifische Integrationstests müssen klar markiert sein und auf Nicht-Windows-Systemen übersprungen werden.
- Nutze Fixture-/Mock-Daten, damit Tests keine echten Geräte benötigen.
- Teste leere Datenbank, fehlende Felder, doppelte Interfaces, Scanfehler und Geräte, die zwischen zwei Scans verschwinden.
- Führe die vorhandene Testsuite und statische Prüfungen aus.
- Keine Tests als erfolgreich melden, wenn sie nicht tatsächlich ausgeführt wurden.

## Umsetzungsreihenfolge

Halte dich an `ROADMAP.md`. Arbeite jeweils nur am nächsten sinnvollen Arbeitspaket, sofern der Projektverantwortliche nicht ausdrücklich mehrere Pakete freigibt.

Für jedes Arbeitspaket:

1. Ist-Zustand und relevante Dateien prüfen.
2. Akzeptanzkriterien aus der Roadmap ableiten.
3. Implementieren.
4. Tests ergänzen und ausführen.
5. README/Architekturdokumentation bei Bedarf aktualisieren.
6. Änderungen knapp und präzise zusammenfassen.
7. Offene Entscheidungen und Risiken benennen.
8. Einen Commit-Vorschlag mit aussagekräftiger Nachricht nennen, aber nicht eigenmächtig committen oder pushen.

## Abschlussbericht

Am Ende jeder Arbeitseinheit berichten:

- Was wurde umgesetzt?
- Welche Dateien wurden geändert/neu erstellt?
- Welche Tests wurden ausgeführt und mit welchem Ergebnis?
- Was funktioniert noch nicht bzw. wurde nicht geprüft?
- Welche Einschränkungen bestehen bei Windows-Geräteerkennung und Zeitstempeln?
- Was ist das nächste Roadmap-Arbeitspaket?

Beginne jetzt mit der Repository-Inspektion und anschließend mit dem nächsten offenen Roadmap-Arbeitspaket. Erfinde keine vorhandenen Dateien, Testergebnisse oder Windows-Fähigkeiten.
