# Windows-PnP-Datenquellen und Architekturentscheidung

Stand: 2026-11-06  
Arbeitspaket: WP-01 – Projektgrundlage und technische Machbarkeit

## 1. Repository-Ist-Zustand

Der Standardbranch `main` enthält zum Prüfzeitpunkt ausschließlich:

- `README.md`
- `ROADMAP.md`
- `AGENTS.md`
- `IMPLEMENTER_PROMPT.md`

Es existieren noch kein Python-Paket, keine Abhängigkeitsdefinition, keine Tests, keine CI-Konfiguration und keine Anwendung. Die Roadmap ist daher weiterhin bei WP-01. Es wurden keine Commits, Branchwechsel oder Merges vorgenommen.

## 2. Zielplattform und Laufzeit

**Zielplattform:** Windows 10 und Windows 11, 64-Bit.

**Vorgeschlagene Python-Basis:** CPython 3.12 oder neuer; als erste Implementierungsbasis Python 3.12/3.13. Die endgültige Mindestversion wird erst mit dem gewählten GUI-Toolkit und einem Windows-Testlauf festgeschrieben. Python 3.14 wird nicht allein deshalb vorausgesetzt, weil es aktuell verfügbar ist: Für native Windows-Bindings und Packaging zählt die nachgewiesene Kompatibilität aller Abhängigkeiten.

Die Windows-Entwicklungsumgebung von Microsoft dokumentiert derzeit Python 3.14 als stabile Laufzeit. Das ist ein Hinweis auf die aktuelle Verfügbarkeit, aber kein Beleg dafür, dass alle später ausgewählten GUI- und Windows-Abhängigkeiten bereits kompatibel sind.

## 3. Bewertete Datenquellen

### 3.1 Windows SetupAPI – bevorzugte Discovery-Basis

Empfohlen wird eine direkte, gekapselte Nutzung der Windows SetupAPI über `ctypes` oder ein kleines, begründetes Binding.

Zentraler Einstieg:

- `SetupDiGetClassDevsW(NULL, NULL, NULL, DIGCF_ALLCLASSES)`: liefert Geräteeinträge über alle Setup-Klassen und schließt nicht vorhandene, aber Windows noch bekannte Geräte ein.
- Mit `DIGCF_PRESENT` wird auf aktuell vorhandene Geräte eingeschränkt.
- `SetupDiEnumDeviceInfo`: iteriert die Geräteinformationselemente.
- `SetupDiGetDeviceInstanceIdW`: ermittelt die Geräteinstanz-ID.
- `SetupDiGetDevicePropertyW`: liest Eigenschaften des einheitlichen Windows-Geräteeigenschaftenmodells.
- `SetupDiDestroyDeviceInfoList`: gibt den Geräteinformationssatz frei.

Damit können zwei Snapshots erstellt oder logisch unterschieden werden: alle noch registrierten/bekannten Geräte und die aktuell vorhandenen Geräte. Das Flag `DIGCF_PRESENT` ist der dokumentierte Presence-Filter.

Wichtige Eigenschaften für die Anwendung:

- Friendly Name / Device Description
- Manufacturer
- Class / Class GUID
- Instance ID
- Hardware IDs
- Compatible IDs
- Container ID
- Parent
- Location Paths
- Enumerator / Bus-bezogene Angaben
- Treiberanbieter und Treiberversion, soweit verfügbar

Ein einzelner fehlender oder nicht lesbarer Property-Wert darf den gesamten Scan nicht abbrechen. Das Handle des Geräteinformationssatzes muss auch bei Ausnahmen zuverlässig freigegeben werden.

### 3.2 Configuration Manager (CfgMgr32) – ergänzende Status-/Property-API

Die Configuration-Manager-API ist eine geeignete Ergänzung für DevNode-Status und Geräteeigenschaften:

- `CM_Get_DevNode_Status` liefert Statusflags und – falls vorhanden – einen Problemcode für einen DevNode.
- `CM_Get_DevNode_Property` kann Werte des einheitlichen Geräteeigenschaftenmodells auslesen.

Die API sollte hinter demselben Windows-PnP-Adapter liegen. Sie ist kein Anlass, Geräteidentitäten aus rohen Registry-Pfaden abzuleiten.

### 3.3 PowerShell PnpDevice – Diagnose und frühe Machbarkeitsprüfung

Das Windows-PowerShell-Modul `PnpDevice` bietet:

- `Get-PnpDevice`: grundlegende PnP-Daten, einschließlich Geräte, die nicht mit `-PresentOnly` auf aktuell vorhandene Geräte begrenzt werden.
- `Get-PnpDeviceProperty`: detailliertere Eigenschaften.

PowerShell eignet sich für manuelle Diagnose, reproduzierbare Referenz-Snapshots und einen frühen Prototyp. Für den späteren dauerhaften GUI-Scan ist ein direkter API-Adapter vorzuziehen: kein zusätzlicher Prozessstart je Aktualisierung, weniger Serialisierungs-/Parsing-Overhead und bessere Fehlerkontrolle pro Property/Gerät.

Ein PowerShell-Fallback ist nicht Teil dieser Entscheidung und müsste separat begründet und sicher implementiert werden. Niemals ungeprüfte Eingaben in PowerShell-Befehle interpolieren.

### 3.4 HIDAPI – nur ergänzend

`hidapi` kann HID-Interfaces und HID-spezifische Angaben wie Usage Page und Usage ergänzen. Es ist ausdrücklich nicht die alleinige Discovery-Quelle: Es deckt keine vollständige PnP-Gerätehistorie und keine beliebigen Nicht-HID-USB-Geräte ab.

## 4. Status und historische Geräte

Empfohlene Abgrenzung:

- **Windows kennt das Gerät:** Ein Geräteeintrag ist über die PnP-Geräteinformationen auffindbar.
- **Aktuell vorhanden:** Gerät ist in einer Presence-Abfrage enthalten bzw. sein DevNode-Status bestätigt die Präsenz.
- **Nicht vorhanden / historischer PnP-Eintrag:** Eintrag ist ohne `DIGCF_PRESENT` vorhanden, fehlt aber im Presence-Snapshot. In der UI vorsichtig als „Getrennt“ kennzeichnen, sofern die Statusauswertung dies bestätigt; andernfalls „Status unbekannt“.
- **Aus App-Sicht historisch:** Gerät wurde zuvor in der lokalen SQLite-Datenbank beobachtet. Diese Historie bleibt von Windows' Gerätebestand unabhängig.

„Nicht im Presence-Snapshot“ darf nicht automatisch als sicher physisch abgezogen interpretiert werden: Status-/Property-Fehler, Gerätekonfiguration und virtuelle Geräte können Sonderfälle erzeugen.

## 5. Geräteidentität und Composite-Geräte

Kein einzelnes Feld ist in allen Fällen ein universeller physischer Geräte-Schlüssel.

Vorgeschlagene Speicherung:

1. Geräteinstanz-ID als Schlüssel des PnP-DevNode-Datensatzes.
2. Container-ID separat speichern, wenn verfügbar. Windows verwendet Container-IDs, um DevNodes zu gruppieren, die zu einer Instanz eines physischen Geräts gehören können.
3. Seriennummer, Hardware-IDs, Parent und Location Paths separat speichern.
4. Interfaces/DevNodes zunächst transparent als einzelne technische Einträge behandeln.
5. Eine physische Gruppierung nur vornehmen, wenn Container-ID oder andere belastbare Beziehungen dies stützen. Anzeigename oder VID/PID allein reichen nicht.
6. Bei fehlender Container-ID keine künstliche Gruppierung erzwingen.

Eine Container-ID ist ein hilfreiches Gruppierungsmerkmal, aber nicht automatisch ein Beweis dafür, dass jedes zusammengefasste Interface im UI nur eine einzige „Tastaturfunktion“ darstellt.

## 6. VID/PID und Klassifizierung

VID/PID werden nur aus tatsächlich vorhandenen USB-Hardware- oder kompatiblen Kennungen geparst. Erwartete Muster wie `VID_XXXX` und `PID_XXXX` müssen unabhängig und fehlertolerant ausgewertet werden. Werte werden als vierstellige Hexadezimalstrings normalisiert. Nicht-USB-Geräte können keine VID/PID besitzen; dann bleiben die Felder unbekannt.

Tastaturklassifizierung sollte mehrere Hinweise kombinieren:

- PnP-Setup-Klasse bzw. Class GUID (Keyboard-Klasse)
- HID-Usage-Informationen, soweit verfügbar
- USB-/HID-Interface-IDs und Parent-/Container-Beziehungen zur Erklärung zusammengesetzter Geräte

Der erste Implementierungsschritt soll rohe Klassendaten erhalten und die Kategorie daraus ableiten, statt die Rohdaten zu verwerfen.

## 7. Zeitstempel: keine universelle Last-connected-Aussage

Die hier geprüften PnP-Discovery-Schnittstellen stellen keinen universellen, zuverlässigen physischen „zuletzt angeschlossen“-Zeitpunkt für jedes Gerät bereit.

Daher:

- Windows-Zeitwerte nur übernehmen, wenn die konkrete Property und deren Semantik dokumentiert sind.
- Windows-Metadaten mit Property-Key, Herkunft und Genauigkeit speichern.
- Eigene Zeitpunkte getrennt in UTC protokollieren: erstmalig beobachtet, zuletzt verbunden beobachtet, zuletzt getrennt beobachtet.
- Keine Dateisystem-Zeit, Registry-Zeit oder Installationszeit ohne fachlich belegte Semantik als Anschlusszeitpunkt umdeuten.
- Reine Scan-Historie kann kurze Verbindungen zwischen zwei Scans verpassen.

## 8. Berechtigungen

Die grundlegenden PnP-Abfragen sind für eine normale Desktop-Anwendung vorgesehen und sollen ohne Elevation getestet werden. Einzelne Properties oder Geräteklassen können dennoch mit Zugriffsfehlern oder fehlenden Werten antworten. Die Anwendung soll:

- ohne Administratorrechte starten;
- fehlende Properties als nicht verfügbar behandeln;
- Fehler pro Gerät/Property protokollieren, ohne unnötige Gerätekennungen in Logs zu schreiben;
- klar zwischen „nicht vorhanden“, „nicht unterstützt“, „Zugriff verweigert“ und „unbekannt“ unterscheiden, soweit die API dies ermöglicht.

Aus der bloßen Dokumentation einzelner APIs kann nicht abgeleitet werden, dass jede Property jedes Geräts in jeder Windows-Konfiguration unprivilegiert lesbar ist. Das muss in WP-03 auf realen Windows-10/11-Systemen geprüft werden.

## 9. Architekturentscheidung

Für die erste Implementierung wird folgende Richtung empfohlen:

- **Discovery:** SetupAPI über einen Windows-spezifischen Adapter; CfgMgr32 nur dort ergänzen, wo Status/Properties damit zuverlässiger oder einfacher ermittelt werden.
- **Prototyping/Diagnose:** PowerShell `Get-PnpDevice` als Referenz und Vergleich, nicht als primärer GUI-Backendprozess.
- **Zusatzdaten:** HIDAPI optional und strikt ergänzend.
- **Domäne:** PnP-DevNode und physische Geräte-/Containergruppierung unterscheiden.
- **Historie:** SQLite speichert App-Beobachtungen unabhängig vom aktuellen Windows-PnP-Snapshot.
- **GUI:** Toolkit-Auswahl bleibt WP-05 vorbehalten; WP-01 legt dies nicht vorzeitig fest.
- **Plattform:** Windows 10/11 x64; Python-Mindestversion bleibt bis zur Dependency-/GUI-Prüfung eine vorläufige Entscheidung.

### Begründung

SetupAPI dokumentiert explizit die Enumeration aller installierten Geräte sowie den optionalen Filter auf derzeit vorhandene Geräte. Das passt direkter zur Kombination aus aktuellen und von Windows noch bekannten Geräten als eine reine HIDAPI-Abfrage. CfgMgr32 liefert gezielte Status- und Property-Funktionen. PowerShell ist gut für Diagnose und frühe Snapshots, aber nicht zwingend als Laufzeitabhängigkeit einer Desktop-App.

## 10. Repräsentative Snapshots – Status

**Noch nicht erhoben.** Das aktuelle Arbeitsumfeld dieses WP-01-Durchlaufs stellt kein Windows-10/11-Gerät mit realer PnP-Geräteliste bereit. Deshalb werden hier keine erfundenen Beispielgeräte oder vermeintlich gemessenen Ergebnisse hinterlegt.

Für WP-03 sind mindestens folgende anonymisierte Fälle als Fixtures bzw. lokale Test-Snapshots zu erfassen:

- angeschlossene USB-Tastatur mit VID/PID;
- abgezogene Tastatur, die Windows noch kennt;
- Composite-Tastatur mit mehreren HID-Interfaces;
- USB-Gerät ohne auslesbare VID/PID;
- Gerät mit unvollständigen Properties bzw. Zugriffsfehler;
- nicht-USB-PnP-Gerät.

Vor dem Commit sind persönliche Seriennummern, vollständige Instance IDs und andere unnötige lokale Identifikatoren aus Beispieldaten zu entfernen oder zu anonymisieren.

## 11. Grenzen und offene Validierung

- Keine Windows-10/11-Laufzeitmessung oder reale Hardwareenumeration in diesem Arbeitspaket.
- Keine gemessenen Berechtigungsresultate für einzelne Properties.
- Noch keine Entscheidung über GUI-Toolkit oder finale Python-Mindestversion.
- Noch keine getestete PnP-zu-physischem-Gerät-Gruppierungslogik.
- SetupAPI-Aufrufkonventionen, Strukturen, Puffergrößen, Property-Datentypen und Handle-Lifetime müssen in WP-03 mit Windows-Integrationstests validiert werden.

## Quellen

Alle Quellen sind Microsoft Learn:

1. [SetupDiGetClassDevsW](https://learn.microsoft.com/en-us/windows/win32/api/setupapi/nf-setupapi-setupdigetclassdevsw) – Enumeration aller installierten Geräte und `DIGCF_PRESENT`.
2. [SetupDiGetDeviceInstanceId](https://learn.microsoft.com/en-us/windows/win32/api/setupapi/nf-setupapi-setupdigetdeviceinstanceida) – Abruf der Geräteinstanz-ID.
3. [SetupDiGetDevicePropertyW](https://learn.microsoft.com/en-us/windows/win32/api/setupapi/nf-setupapi-setupdigetdevicepropertyw) – Abruf von Geräteeigenschaften und mögliche Fehler wie `ERROR_ACCESS_DENIED`.
4. [Accessing Device Instance Properties](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/determining-which-properties-are-set-for-a-device-instance) – einheitliches Geräteeigenschaftenmodell und SetupAPI/CfgMgr32.
5. [Accessing Device Properties](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/accessing-device-properties) – APIs statt direktem Registry-Zugriff.
6. [CM_Get_DevNode_Status](https://learn.microsoft.com/en-us/windows/win32/api/cfgmgr32/nf-cfgmgr32-cm_get_devnode_status) – DevNode-Status und Problemcode.
7. [DEVPKEY_Device_HardwareIds](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/devpkey-device-hardwareids) – Hardware-ID-Eigenschaft.
8. [DEVPKEY_Device_ContainerId](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/devpkey-device-containerid) – Gruppierung von DevNodes eines Gerätecontainers.
9. [Get-PnpDevice](https://learn.microsoft.com/en-us/powershell/module/pnpdevice/get-pnpdevice) – PowerShell-PnP-Diagnose, einschließlich `-PresentOnly`.
10. [Python-Entwicklungsumgebung unter Windows](https://learn.microsoft.com/en-us/windows/dev-environment/python) – aktuell dokumentierte Python-Laufzeit.

---
WP-01 liefert eine Architekturentscheidung und eine dokumentierte Machbarkeitsbewertung. Die vollständige Akzeptanz ist erst nach echten Windows-Snapshots und Berechtigungstests abgeschlossen; diese Validierung gehört in WP-03 und darf nicht als bereits erledigt ausgegeben werden.
