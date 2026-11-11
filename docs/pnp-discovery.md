# Windows-PnP-Erkennung (WP-03)

## Architektur

`discovery/setupapi.py` kapselt die Windows-APIs. `WindowsPnpDiscovery` mappt die Ergebnisse auf die plattformunabhängigen Domänenmodelle aus WP-02. Das Modul importiert unter Nicht-Windows-Systemen, die native Backend-Instanz kann dort aber nicht erstellt werden. Für Tests wird ein Backend injiziert, das denselben kleinen Vertrag (`scan() -> RawPnpScan`) erfüllt.

Es gibt keine automatische Persistierung und keinen Historien-Tracker. Das bleibt WP-04 vorbehalten.

## Enumeration und Presence

Der Backend-Scan erstellt zwei SetupAPI-Geräteinformationssätze:

1. `DIGCF_ALLCLASSES`: alle Windows noch bekannten installierten DevNodes.
2. `DIGCF_ALLCLASSES | DIGCF_PRESENT`: separate Menge der aktuell vorhandenen DevNodes.

Die Geräteinstanz-ID verbindet die beiden Momentaufnahmen. Ist die Presence-Abfrage vollständig, wird ein Eintrag aus der ersten Menge, der in der zweiten fehlt, als `disconnected` gemappt. Ist die Presence-Abfrage unvollständig, werden nicht zuordenbare Einträge vorsichtig als `unknown` behandelt. Ein Treffer in der Presence-Menge ist `connected`.

Die SetupAPI-Geräteinformationssätze werden in einem `finally`-Block mit `SetupDiDestroyDeviceInfoList` freigegeben.

## Ausgelesene Eigenschaften

Der erste Adapter nutzt dokumentierte `SPDRP_*`-Eigenschaften über `SetupDiGetDeviceRegistryPropertyW`:

- Gerätebeschreibung und Friendly Name
- Hardware-IDs und Compatible IDs (jeweils als Liste)
- Geräteklasse und Class GUID
- Hersteller
- Enumerator
- Location Paths
- Base Container ID

CfgMgr32 ergänzt:

- Parent-DevNode über `CM_Get_Parent` und `CM_Get_Device_IDW`
- Statusflags und Problemcode über `CM_Get_DevNode_Status`

Jeder gelesene Windows-Wert wird als `WindowsMetadata` mit Property-Key, Quelle, Registry-Datentyp und UTC-Erfassungszeitpunkt im Ergebnis mitgegeben. Das Ergebnis kann in WP-04 separat persistiert werden.

Seriennummer, Treiberanbieter/-version sowie HID Usage Page/Usage sind noch nicht Teil des ersten Adapters. Eine Seriennummer wird ausdrücklich nicht aus dem letzten Segment der Instance ID abgeleitet.

## VID/PID und Kategorien

VID/PID werden nur übernommen, wenn **dieselbe Hardware- oder Compatible-ID mit `USB\\` beginnt und beide vierstelligen Hex-Werte enthält**. HID- und PCI-Kennungen werden nicht fälschlich als USB-VID/PID ausgegeben.

Die Kategorie wird zusätzlich zur unveränderten Windows-Geräteklasse abgeleitet:

- `keyboard`: Windows-Klasse Keyboard bzw. bekannte Keyboard-Class-GUID
- `hid`: Windows-Klasse HIDClass oder HID-Enumerator/Instance-ID
- `usb`: Windows-Klasse USB, USB-Enumerator oder USB-Instance-ID
- `other`: übrige PnP-Geräte

Diese grobe Klassifikation ist kein Ersatz für HID Usage Page/Usage. Eine HID-Tastatur kann daher vorerst in der HID-Kategorie liegen, wenn Windows sie nicht als Keyboard-DevNode ausweist.

## Fehlerverhalten und Sicherheit

- Fehler beim Lesen einzelner Properties werden als `DiscoveryError` gesammelt; andere Eigenschaften und Geräte werden weiter verarbeitet.
- Mappingfehler eines einzelnen DevNodes brechen den Scan nicht ab.
- Fehler der globalen Presence-Enumeration führen für nicht zuordenbare Geräte zu `unknown`, nicht zu einer falschen Trennungsbehauptung.
- Die Implementierung führt ausschließlich SetupAPI-/CfgMgr32-Leseoperationen aus. Sie ändert keine Geräte, Treiber, Registry-Schlüssel oder Firmware.
- Administratorrechte werden nicht angefordert.
- Fehlertexte enthalten keine automatischen Rohdatenexports. Ein aufrufender Logger sollte Instance IDs nicht standardmäßig protokollieren.

## Tests und noch ausstehende Validierung

`tests/test_discovery.py` enthält plattformunabhängige Tests für ID-Parsing, Mapping, Statuszuordnung, Composite-/Interface-Trennung, Fehlerisolation und Kategorien. Ein zusätzlicher Test mit Marker `windows_integration` ruft die echte SetupAPI auf Windows auf und prüft die Enumeration ohne explizite Elevation.

Die echte Windows-Integration, Berechtigungen und Geräte-Snapshots müssen auf dem Windows-Rechner des Projektverantwortlichen ausgeführt werden. Es wurde in der Implementierungsumgebung kein realer PnP-Hardwarebestand ausgelesen. Der WP-01-Snapshot liegt nicht im Repository und wurde daher nicht ausgewertet.

## Quellen

- [SetupDiGetClassDevsW](https://learn.microsoft.com/en-us/windows/win32/api/setupapi/nf-setupapi-setupdigetclassdevsw) – alle installierten Geräte und Presence-Filter.
- [SetupDiGetDeviceRegistryPropertyW](https://learn.microsoft.com/en-us/windows/win32/api/setupapi/nf-setupapi-setupdigetdeviceregistrypropertyw) – Registry-backed Device-Properties und Datentypen.
- [CM_Get_Parent](https://learn.microsoft.com/en-us/windows/win32/api/cfgmgr32/nf-cfgmgr32-cm_get_parent) – Parent-DevNode.
- [CM_Get_Device_IDW](https://learn.microsoft.com/en-us/windows/win32/api/cfgmgr32/nf-cfgmgr32-cm_get_device_idw) – Device Instance ID eines DevNodes.
- [CM_Get_DevNode_Status](https://learn.microsoft.com/en-us/windows/win32/api/cfgmgr32/nf-cfgmgr32-cm_get_devnode_status) – Statusflags und Problemcode.
