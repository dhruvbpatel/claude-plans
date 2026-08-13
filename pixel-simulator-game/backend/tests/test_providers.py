"""Phase 5 provider tests: factory selection, gateway stream + fallback, swarm stub.

No real network — the gateway is exercised through httpx.MockTransport.
Async streams are drained with asyncio.run (no pytest-asyncio dependency).
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.engine.protocols import DebateContext, DebateDelta
from app.providers.deterministic import DeterministicDebate
from app.providers.factory import create_debate_provider
from app.providers.gateway import GatewayDebate, build_messages, _parse_line
from app.providers.swarm import SwarmDebate


def collect(provider, ctx: DebateContext) -> list[DebateDelta]:
    async def _drain():
        return [delta async for delta in provider.stream(ctx)]

    return asyncio.run(_drain())


@pytest.fixture()
def ctx(scenario) -> DebateContext:
    beat = scenario["beats"][0]
    return {
        "state": {"beatIndex": 0, "kpis": dict(scenario["kpis"])},
        "beat": beat,
        "options": beat["options"],
        "npcs": list(scenario["npcs"]),
    }


@pytest.fixture()
def no_gateway_env(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DEBATE_DELAY_MS", "0")


@pytest.fixture()
def gateway_env(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://gateway.test/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DEBATE_DELAY_MS", "0")


def sse_body(*contents: str) -> bytes:
    """OpenAI-compatible chat-completions SSE stream from content chunks."""
    lines = [
        "data: " + json.dumps({"choices": [{"delta": {"content": c}}]}) + "\n\n"
        for c in contents
    ]
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


def mock_transport(*contents: str, status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            content=sse_body(*contents) if status == 200 else b"error",
            headers={"content-type": "text/event-stream"},
        )

    return httpx.MockTransport(handler)


# -- factory -----------------------------------------------------------------


def test_factory_defaults_to_deterministic(monkeypatch):
    monkeypatch.delenv("DEBATE_PROVIDER", raising=False)
    assert isinstance(create_debate_provider(), DeterministicDebate)


@pytest.mark.parametrize(
    ("name", "cls"),
    [
        ("deterministic", DeterministicDebate),
        ("gateway", GatewayDebate),
        ("swarm", SwarmDebate),
    ],
)
def test_factory_env_selection(monkeypatch, name, cls):
    monkeypatch.setenv("DEBATE_PROVIDER", name)
    assert isinstance(create_debate_provider(), cls)


def test_factory_explicit_name_overrides_env(monkeypatch):
    monkeypatch.setenv("DEBATE_PROVIDER", "deterministic")
    assert isinstance(create_debate_provider("swarm"), SwarmDebate)


def test_factory_unknown_falls_back_to_deterministic(monkeypatch):
    monkeypatch.setenv("DEBATE_PROVIDER", "gpt-in-the-sky")
    assert isinstance(create_debate_provider(), DeterministicDebate)


def test_factory_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("DEBATE_PROVIDER", " Gateway ")
    assert isinstance(create_debate_provider(), GatewayDebate)


# -- gateway: happy path -------------------------------------------------------


def test_gateway_streams_parsed_lines(gateway_env, ctx):
    provider = GatewayDebate(
        fallback=DeterministicDebate(delay_ms=0),
        transport=mock_transport(
            "ceo: We reject",
            " your premise.\nanalyst: The sum",
            " of the parts disagrees.\n",
        ),
    )
    deltas = collect(provider, ctx)
    assert deltas == [
        {"speakerId": "ceo", "text": "We reject your premise."},
        {"speakerId": "analyst", "text": "The sum of the parts disagrees.", "done": True},
    ]


def test_gateway_last_line_without_trailing_newline(gateway_env, ctx):
    provider = GatewayDebate(
        fallback=DeterministicDebate(delay_ms=0),
        transport=mock_transport("gc: Careful with disclosure."),
    )
    deltas = collect(provider, ctx)
    assert deltas == [
        {"speakerId": "gc", "text": "Careful with disclosure.", "done": True}
    ]


def test_gateway_request_uses_env_model_and_auth(gateway_env, monkeypatch, ctx):
    monkeypatch.setenv("GATEWAY_MODEL", "test-model-x")
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["payload"] = json.loads(request.content)
        return httpx.Response(200, content=sse_body("ceo: Fine.\n"))

    provider = GatewayDebate(
        fallback=DeterministicDebate(delay_ms=0),
        transport=httpx.MockTransport(handler),
    )
    collect(provider, ctx)
    assert seen["url"] == "https://gateway.test/v1/chat/completions"
    assert seen["auth"] == "Bearer test-key"
    assert seen["payload"]["model"] == "test-model-x"
    assert seen["payload"]["stream"] is True


# -- gateway: prompt safety ----------------------------------------------------


def test_prompt_contains_pros_cons_but_never_deltas(ctx):
    messages = build_messages(ctx)
    serialized = json.dumps(messages, ensure_ascii=False)
    assert "delta" not in serialized.lower()
    option = ctx["options"][0]
    assert option["pros"][0] in serialized
    assert option["cons"][0] in serialized
    # No KPI names or raw numbers from the deltas dict leak into the prompt.
    for kpi, value in option["deltas"].items():
        assert kpi not in serialized
        assert f": {value}" not in serialized
    assert ctx["beat"]["situation"] in serialized


def test_parse_line_maps_unknown_speaker_to_default():
    npcs = {"ceo", "analyst"}
    assert _parse_line("ceo: Hello.", npcs, "analyst") == {
        "speakerId": "ceo",
        "text": "Hello.",
    }
    assert _parse_line("Board Chair: Order, please.", npcs, "analyst") == {
        "speakerId": "analyst",
        "text": "Order, please.",
    }
    assert _parse_line("no colon at all", npcs, "analyst") == {
        "speakerId": "analyst",
        "text": "no colon at all",
    }
    assert _parse_line("   ", npcs, "analyst") is None


# -- gateway: fallback ---------------------------------------------------------


def deterministic_reference(ctx) -> list[DebateDelta]:
    return collect(DeterministicDebate(delay_ms=0), ctx)


def test_gateway_falls_back_when_unconfigured(no_gateway_env, ctx):
    provider = GatewayDebate(fallback=DeterministicDebate(delay_ms=0))
    assert collect(provider, ctx) == deterministic_reference(ctx)


def test_gateway_falls_back_on_connect_error(gateway_env, ctx):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    provider = GatewayDebate(
        fallback=DeterministicDebate(delay_ms=0),
        transport=httpx.MockTransport(handler),
    )
    assert collect(provider, ctx) == deterministic_reference(ctx)


def test_gateway_falls_back_on_timeout(gateway_env, ctx):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timed out", request=request)

    provider = GatewayDebate(
        fallback=DeterministicDebate(delay_ms=0),
        transport=httpx.MockTransport(handler),
    )
    assert collect(provider, ctx) == deterministic_reference(ctx)


def test_gateway_falls_back_on_http_error(gateway_env, ctx):
    provider = GatewayDebate(
        fallback=DeterministicDebate(delay_ms=0),
        transport=mock_transport(status=500),
    )
    assert collect(provider, ctx) == deterministic_reference(ctx)


def test_gateway_falls_back_on_empty_stream(gateway_env, ctx):
    provider = GatewayDebate(
        fallback=DeterministicDebate(delay_ms=0),
        transport=mock_transport(),  # [DONE] with no content chunks
    )
    assert collect(provider, ctx) == deterministic_reference(ctx)


def test_gateway_never_stalls_mid_beat(gateway_env, ctx):
    """Stream dies mid-debate -> already-streamed lines stay, fallback finishes the beat."""

    def event(content: str) -> bytes:
        chunk = {"choices": [{"delta": {"content": content}}]}
        return f"data: {json.dumps(chunk)}\n\n".encode()

    def handler(request: httpx.Request) -> httpx.Response:
        async def broken_stream():
            yield event("ceo: We hear you.\n")
            yield event("analyst: But the numbers—\n")
            raise httpx.ReadError("stream broke", request=request)

        return httpx.Response(
            200,
            content=broken_stream(),
            headers={"content-type": "text/event-stream"},
        )

    provider = GatewayDebate(
        fallback=DeterministicDebate(delay_ms=0),
        transport=httpx.MockTransport(handler),
    )
    deltas = collect(provider, ctx)
    # The line streamed before the break survives...
    assert deltas[0] == {"speakerId": "ceo", "text": "We hear you."}
    # ...and the deterministic fallback completes the debate afterwards.
    assert deltas[1:] == deterministic_reference(ctx)


# -- swarm stub ------------------------------------------------------------


def test_swarm_stub_stream_shape(ctx):
    deltas = collect(SwarmDebate(delay_ms=0), ctx)
    assert deltas, "swarm stub must emit a plausible fake debate"
    npcs = set(ctx["npcs"])
    for delta in deltas:
        assert set(delta) <= {"speakerId", "text", "done"}
        assert delta["speakerId"] in npcs
        assert delta["text"].strip()
    assert deltas[-1]["done"] is True
    assert all("done" not in d for d in deltas[:-1])
    # Multi-agent: more than one distinct speaker.
    assert len({d["speakerId"] for d in deltas}) > 1


def test_swarm_stub_reflects_beat_context(ctx):
    deltas = collect(SwarmDebate(delay_ms=0), ctx)
    text = " ".join(d["text"] for d in deltas)
    first_label = ctx["options"][0]["label"]
    assert first_label in text
    assert str(len(ctx["options"])) in text
