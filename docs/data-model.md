# Datenmodell und SQLite-Persistenz (WP-02)

## Verantwortlichkeiten

- `domain/models.py`: unveränderliche Dataclasses ohne Windows-API- oder SQLite-Abhängigkeit.
- `persistence/database.py`: SQLite-Verbindung, Foreign-Key-Aktivierung und Schema-Versionierung über `PRAGMA user_version`.
- `persistence/repositories.py`: CRUD für DevNodes, Windows-Metadaten und App-Beobachtungen.

Die Windows-Erkennung wird nicht in diese Schicht eingebaut. WP-03 liefert später `DeviceRecord`-Instanzen an das Repository.

## Identitätsmodell

Ein `DeviceRecord` repräsentiert genau einen PnP-DevNode bzw. ein Interface. `instance_id` ist der Primärschlüssel des Datensatzes. Container-ID, Seriennummer, Parent, Location Paths und Hardware-IDs werden separat abgelegt. Es gibt bewusst keine automatische Zusammenführung nach Anzeigename, VID/PID oder Container-ID. Dadurch bleiben Composite-Geräte und mehrere Interfaces nachvollziehbar.

Hardware-IDs sind in einer eigenen Tabelle mit stabiler Reihenfolge abgelegt. Das vermeidet das Vermischen eines einzelnen Strings mit mehreren Windows-IDs und ermöglicht spätere Erweiterungen.

## Windows-Metadaten und App-Beobachtungen

`windows_metadata` speichert einzelne Windows-Properties inklusive Property-Key, Quelle, Werttyp und Erfassungszeitpunkt.

`observations` speichert ausschließlich Beobachtungen der Anwendung: Zeitpunkt, Status, Quelle und optionales Detail. Diese Daten werden nicht als Windows-Metadatum interpretiert.

Am Gerätedatensatz werden die daraus abgeleiteten Zeitpunkte getrennt gehalten:

- `first_observed_at`
- `last_connected_observed_at`
- `last_disconnected_observed_at`

Alle Zeitstempel müssen zeitzonenbewusst sein und werden als UTC-ISO-8601 mit `Z` persistiert. Naive Datetimes werden abgewiesen. Eine spätere Anzeige kann lokal formatieren, ohne die gespeicherte Zeit zu verändern.

Bei verspätet eintreffenden Beobachtungen werden die früheste Erstbeobachtung und die jeweils spätesten Connected-/Disconnected-Zeitpunkte bewahrt. Der aktuelle Status wird nur durch die zeitlich neueste Beobachtung bestimmt. `unknown` überschreibt den aktuellen Status, löscht aber keine bekannten Connected-/Disconnected-Zeitpunkte.

## Löschen und Datenintegrität

`DeviceRepository.delete()` löscht ausschließlich den Datensatz dieser Anwendung. Foreign-Key-Cascades entfernen nur die dazugehörigen lokalen Hardware-ID-, Metadaten- und Beobachtungszeilen. Es gibt keinen Windows-Geräte- oder Treiberzugriff.

## Schema und Migrationen

Das initiale Schema verwendet SQLite `user_version = 1`. Die Migration wird in einer expliziten Transaktion ausgeführt. Datenbankdateien mit einer höheren, nicht unterstützten Schema-Version werden abgewiesen, statt stillschweigend verändert zu werden.

## Verwendung

```python
from datetime import datetime, timezone

from jkeebs_hardware_manager.domain.models import DeviceRecord, DeviceObservation
from jkeebs_hardware_manager.persistence.database import Database
from jkeebs_hardware_manager.persistence.repositories import DeviceRepository, ObservationRepository

with Database("hardware-manager.sqlite3") as database:
    devices = DeviceRepository(database.connection)
    observations = ObservationRepository(database.connection)

    device = DeviceRecord(
        instance_id=r"USB\\VID_046A&PID_C33C\\DEVICE",
        name="Example Keyboard",
        vid="046A",
        pid="C33C",
        status="connected",
    )
    devices.upsert(device)
    observations.record(DeviceObservation(
        instance_id=device.instance_id,
        observed_at=datetime.now(timezone.utc),
        status="connected",
    ))
```

## Tests

`tests/test_persistence.py` nutzt ausschließlich eine In-Memory-SQLite-Datenbank. Die Tests benötigen keine angeschlossene Hardware und decken leere Datenbank, Roundtrip, fehlende Properties, getrennte Interfaces, Metadatenquelle, UTC-Konvertierung, Status-/Zeitverlauf, verspätete Beobachtungen und das Löschen lokaler Historie ab.

Die Tests müssen in der Entwicklungsumgebung mit `python -m pip install -e ".[dev]"` und `python -m pytest` ausgeführt werden. Ein erfolgreicher Lauf wird erst nach tatsächlicher Ausführung behauptet.
