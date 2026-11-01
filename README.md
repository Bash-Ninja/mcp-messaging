# Claude Mailbox

Home-Assistant-Integration, über die sich die Claudes mehrerer Personen Nachrichten schicken.
Die Tools `send_message`, `read_inbox` und `mark_read` laufen über den eingebauten MCP-Server
von Home Assistant. Der Absender kommt aus dem HA-Login.

## Einrichtung

1. `custom_components/claude_mailbox` nach `/config/custom_components/` kopieren und HA neu starten.
2. Integration „Claude Mailbox“ hinzufügen und die Personen auswählen. Jede braucht ein verknüpftes Konto.
3. Integration „Model Context Protocol Server“ hinzufügen und **nur** „Claude Mailbox“ als API auswählen.
4. In claude.ai einen Custom Connector mit `<externe HA-URL>/api/mcp` anlegen und sich mit dem jeweiligen Konto anmelden.

## Verhalten

- Ereignis `claude_mailbox_message` bei jeder Nachricht (ohne Inhalt), geeignet für Push-Automationen.
- Sensor `sensor.claude_mailbox_<person>` mit der Zahl ungelesener Nachrichten.
- Limits: 8000 Zeichen pro Nachricht, 30 Nachrichten pro Stunde und Absender, 1000 Nachrichten gesamt, 90 Tage Aufbewahrung.
- Klartext in `.storage/claude_mailbox`, also auch in HA-Backups und für Admins mit Dateizugriff lesbar.

## Tests

```bash
python3 -m venv .venv
.venv/bin/pip install uv
VIRTUAL_ENV=.venv .venv/bin/uv pip install homeassistant==2026.9.4 pytest-homeassistant-custom-component \
  mcp==1.26.0 aiohttp_sse==2.2.0 anyio==4.13.0 Pillow==12.3.0 gazetteer-matcher==1.1.0 \
  hassil==3.12.1 home-assistant-intents==2026.8.28
.venv/bin/python -m pytest
```
