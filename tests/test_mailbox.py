"""End-to-end tests through the real Home Assistant MCP server."""

import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.auth.const import GROUP_ID_USER
from homeassistant.components.person import DOMAIN as PERSON_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.claude_mailbox.const import (
    CONF_PARTICIPANTS,
    DOMAIN,
    EVENT_MESSAGE,
    MAX_SENT_PER_HOUR,
)
from custom_components.claude_mailbox.store import MailboxStore

CLIENT_ID = "https://claude.example/"


class Client:
    """Minimal MCP client for one Home Assistant account."""

    def __init__(self, http, token: str) -> None:
        """Initialize the client."""
        self._http = http
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }

    async def request(self, method: str, params: dict | None = None, path="/api/mcp"):
        """Send a JSON-RPC request and return the response."""
        response = await self._http.post(
            path,
            headers=self._headers,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        )
        return response.status, await response.json() if response.status == 200 else None

    async def tools(self) -> dict:
        """Return the offered tools by name."""
        status, data = await self.request("tools/list")
        assert status == 200
        return {tool["name"]: tool for tool in data["result"]["tools"]}

    async def call(self, name: str, **arguments) -> tuple[bool, dict | str]:
        """Call a tool, returning whether it failed and its result."""
        _, data = await self.request(
            "tools/call", {"name": name, "arguments": arguments}
        )
        result = data["result"]
        text = result["content"][0]["text"]
        if result.get("isError"):
            return True, text
        return False, json.loads(text)


@pytest.fixture
async def setup(hass: HomeAssistant, hass_client_no_auth):
    """Set up persons, accounts, the mailbox and the real MCP server."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "http", {})
    # The first account becomes the owner, the others stay regular users.
    await hass.auth.async_create_user("Owner")
    clients = {}
    persons = []
    for name in ("Alice", "Bob", "Carol"):
        user = await hass.auth.async_create_user(name, group_ids=[GROUP_ID_USER])
        assert not user.is_admin
        refresh = await hass.auth.async_create_refresh_token(user, CLIENT_ID)
        token = hass.auth.async_create_access_token(refresh)
        clients[name] = token
        persons.append({"id": name.lower(), "name": name, "user_id": user.id})
    assert await async_setup_component(hass, PERSON_DOMAIN, {PERSON_DOMAIN: persons})
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PARTICIPANTS: ["person.alice", "person.bob"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        "mcp_server", context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"llm_hass_api": [DOMAIN]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    http = await hass_client_no_auth()
    return {name: Client(http, token) for name, token in clients.items()}


async def test_only_participants_get_tools(setup) -> None:
    """Non-admin participants see the mailbox, other accounts see nothing."""
    assert set(await setup["Alice"].tools()) == {
        "send_message",
        "read_inbox",
        "mark_read",
    }
    assert await setup["Carol"].tools() == {}


async def test_tool_schema_lists_recipients(setup) -> None:
    """The recipient list contains the other participants only."""
    tools = await setup["Alice"].tools()
    assert tools["send_message"]["inputSchema"]["properties"]["to"]["enum"] == ["Bob"]


async def test_message_round_trip(hass: HomeAssistant, setup) -> None:
    """A message arrives with the authenticated sender and can be marked read."""
    events = async_capture_events(hass, EVENT_MESSAGE)
    failed, sent = await setup["Alice"].call("send_message", to="Bob", body="Hallo")
    assert not failed
    await hass.async_block_till_done()

    assert hass.states.get("sensor.claude_mailbox_bob").state == "1"
    assert hass.states.get("sensor.claude_mailbox_alice").state == "0"
    assert events[0].data["sender"] == "person.alice"
    assert events[0].data["recipient"] == "person.bob"
    assert "body" not in events[0].data

    failed, inbox = await setup["Bob"].call("read_inbox")
    assert not failed
    message = inbox["messages"][0]
    assert (message["from"], message["body"]) == ("Alice", "Hallo")
    assert "untrusted" in inbox["note"]

    failed, result = await setup["Bob"].call("mark_read", message_ids=[sent["message_id"]])
    assert not failed and result["marked_read"] == 1
    await hass.async_block_till_done()
    assert hass.states.get("sensor.claude_mailbox_bob").state == "0"

    _, inbox = await setup["Bob"].call("read_inbox")
    assert inbox["messages"] == []


async def test_sender_cannot_be_forged(setup) -> None:
    """Extra arguments cannot set the sender."""
    failed, _ = await setup["Alice"].call(
        "send_message", to="Bob", body="x", sender="person.bob"
    )
    assert failed
    _, inbox = await setup["Bob"].call("read_inbox")
    assert inbox["messages"] == []


async def test_missing_arguments_are_explained(setup) -> None:
    """Missing required arguments produce a readable error."""
    failed, error = await setup["Alice"].call("send_message", to="Bob")
    assert failed
    assert "required key not provided" in error
    assert "body" in error


async def test_inbox_is_private(setup) -> None:
    """Nobody else can read or mark the messages of a participant."""
    _, sent = await setup["Alice"].call("send_message", to="Bob", body="geheim")

    _, inbox = await setup["Alice"].call("read_inbox", unread_only=False)
    assert inbox["messages"] == []

    _, result = await setup["Alice"].call("mark_read", message_ids=[sent["message_id"]])
    assert result["marked_read"] == 0

    failed, _ = await setup["Carol"].call("read_inbox")
    assert failed


async def test_cannot_send_to_self_or_outsider(setup) -> None:
    """Only other participants can be recipients."""
    assert (await setup["Alice"].call("send_message", to="Alice", body="x"))[0]
    assert (await setup["Alice"].call("send_message", to="Carol", body="x"))[0]


async def test_reply_to_must_be_visible(setup) -> None:
    """A reply can only reference a message of the sender."""
    _, sent = await setup["Alice"].call("send_message", to="Bob", body="x")
    assert not (
        await setup["Bob"].call(
            "send_message", to="Alice", body="y", reply_to=sent["message_id"]
        )
    )[0]
    assert (await setup["Bob"].call("send_message", to="Alice", body="y", reply_to="nope"))[0]


async def test_rate_limit(setup) -> None:
    """A runaway agent is stopped."""
    for _ in range(MAX_SENT_PER_HOUR):
        assert not (await setup["Alice"].call("send_message", to="Bob", body="x"))[0]
    assert (await setup["Alice"].call("send_message", to="Bob", body="x"))[0]


async def test_rejects_missing_token(hass: HomeAssistant, setup, hass_client_no_auth) -> None:
    """Requests without an account are refused."""
    http = await hass_client_no_auth()
    response = await http.post(
        "/api/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    )
    assert response.status == 401


async def test_non_admin_reach_to_assist(setup) -> None:
    """Document that a non-admin account can also open the Assist endpoint."""
    status, _ = await setup["Bob"].request("tools/list", path="/api/mcp/assist")
    assert status == 200


async def test_config_flow_requires_linked_users(hass: HomeAssistant, setup) -> None:
    """Options reject persons without an account and too few participants."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    hass.states.async_set("person.nouser", "home", {"friendly_name": "Ohne Konto"})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_PARTICIPANTS: ["person.alice", "person.nouser"]}
    )
    assert result["errors"] == {"base": "person_without_user"}
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_PARTICIPANTS: ["person.alice"]}
    )
    assert result["errors"] == {"base": "too_few_participants"}


async def test_messages_survive_restart_and_expire(hass: HomeAssistant, hass_storage) -> None:
    """Messages are persisted and old ones are dropped on load."""
    store = MailboxStore(hass)
    await store.async_load()
    store.async_add("person.alice", "person.bob", "neu")
    await store._store.async_save({"messages": store._messages})

    reloaded = MailboxStore(hass)
    await reloaded.async_load()
    assert reloaded.async_unread_count("person.bob") == 1
    assert hass_storage[DOMAIN]["data"]["messages"][0]["body"] == "neu"

    future = dt_util.utcnow() + timedelta(days=91)
    with patch("custom_components.claude_mailbox.store.dt_util.utcnow", return_value=future):
        expired = MailboxStore(hass)
        await expired.async_load()
    assert expired.async_unread_count("person.bob") == 0
