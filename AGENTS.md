# AGENTS.md – Arbeitsregeln für J-Keebs Hardware Manager

Diese Datei gilt für alle KI-Agenten, Coding-Assistenten und automatisierten Implementer, die an diesem Repository arbeiten.

## 1. Erst verstehen, dann ändern

- Lies `README.md`, `ROADMAP.md` und `IMPLEMENTER_PROMPT.md`, bevor du Änderungen vornimmst.
- Prüfe den tatsächlichen Repository-Zustand. Erfinde keine Dateien, Funktionen, Testergebnisse oder bereits getroffenen Entscheidungen.
- Orientiere dich an bestehenden Konventionen und vermeide unnötige Umstrukturierungen.
- Arbeite standardmäßig am nächsten offenen Roadmap-Arbeitspaket.

## 2. Produkt- und Sicherheitsgrenzen

- Die Anwendung ist ein lokaler Geräte-Informationsbrowser.
- Keine Geräte deinstallieren, keine Treiber entfernen, keine Registry-Geräteschlüssel löschen und keine Firmware verändern.
- „Löschen“ bezieht sich ausschließlich auf lokale App-Datensätze.
- Keine Netzwerkkommunikation, Telemetrie oder Cloud-Synchronisierung hinzufügen, sofern dies nicht ausdrücklich beschlossen wird.
- Keine Administratorrechte standardmäßig voraussetzen.
- Bei unzureichenden Berechtigungen best effort arbeiten und verständliche Hinweise anzeigen.

## 3. Datenintegrität und Zeitstempel

- Windows-Metadaten und eigene App-Beobachtungen strikt unterscheiden.
- Zeitstempel in der Datenbank in UTC speichern; lokal nur für die Anzeige formatieren.
- Zu jedem Zeitwert Quelle und Bedeutung festhalten.
- Niemals den Zeitpunkt des ersten App-Scans als exakten physischen Anschlusszeitpunkt bezeichnen.
- Unbekannte Werte bleiben unbekannt; keine VID/PID- oder Herstellerdaten erraten.
- Geräte nicht allein anhand des Anzeigenamens zusammenführen.
- Composite-Geräte und Interfaces nicht ohne belastbare Identitätsmerkmale deduplizieren.

## 4. Architektur und Codequalität

- Geräteerkennung, Domänenmodell, Datenhaltung, Historienlogik, GUI und Export logisch trennen.
- Windows-spezifische APIs hinter klaren Adaptern kapseln.
- Fehler einzelner Geräte dürfen nicht den gesamten Scan beenden.
- Abhängigkeiten begrenzen und begründen.
- Keine unnötigen globalen Zustände.
- Typannotationen und aussagekräftige Namen verwenden.
- Kommentare erklären das Warum, nicht bloß offensichtliche Syntax.
- Keine großen Frameworks einführen, wenn eine kleinere Lösung genügt.

## 5. GUI und Design

- Windows-2000-inspirierte J-Keebs-Ästhetik beibehalten.
- Informationsdichte und Lesbarkeit haben Vorrang vor Dekoration.
- VID:PID muss in der Hauptliste schnell auffindbar und kopierbar sein.
- Tastaturen müssen als primärer Anwendungsfall leicht filterbar sein.
- Löschen muss eindeutig, bestätigt und nicht mit Windows-Deinstallation verwechselbar sein.
- Tastaturbedienbarkeit und verständliche Fokuszustände berücksichtigen.

## 6. Tests

- Für neue Logik passende Tests ergänzen.
- Windows-spezifische Tests klar markieren und auf anderen Plattformen kontrolliert überspringen.
- Hardwareabhängige Tests durch Fixtures und Mocks ergänzen.
- Mindestens Randfälle für fehlende Felder, doppelte Interfaces, Gerätewechsel, leere Datenbank und Scanfehler berücksichtigen.
- Tests tatsächlich ausführen und nur reale Ergebnisse berichten.
- Keine bestehenden Tests entfernen oder abschwächen, nur um einen grünen Lauf zu erhalten.

## 7. Änderungen und Git

- Kleine, thematisch zusammenhängende Änderungen bevorzugen.
- Keine Nutzeränderungen überschreiben oder zurücksetzen.
- Keine Commits oder Pushes ohne ausdrückliche Freigabe.
- Keine Branches wechseln oder mergen, ohne den Auftrag und den Repository-Zustand zu prüfen.
- Keine Secrets, persönlichen Gerätekennungen oder unnötigen Rohdaten in Fixtures/Logs committen.

## 8. Dokumentation

- Architekturentscheidungen und Windows-Datenquellen dokumentieren.
- Neue Konfigurationsoptionen in README ergänzen.
- Bekannte Grenzen und nicht getestete Bereiche ausdrücklich nennen.
- Roadmap-Status nur aktualisieren, wenn die Akzeptanzkriterien tatsächlich erfüllt sind.

## 9. Abschluss jeder Arbeitseinheit

Berichte knapp und konkret:

1. Umgesetzte Änderungen
2. Geänderte/neu erstellte Dateien
3. Ausgeführte Tests samt Ergebnis
4. Nicht getestete Bereiche und bekannte Einschränkungen
5. Nächstes offenes Arbeitspaket
6. Vorschlag für eine Commit-Nachricht (ohne eigenmächtig zu committen)
