"""OpenAI-compatible Copilot gateway debate provider (Phase 5).

Streams in-character debate dialogue from a chat-completions endpoint
(``OPENAI_BASE_URL`` + ``OPENAI_API_KEY`` — e.g. the GitHub Copilot gateway).

Hard rules:

- The LLM produces **dialogue flavor only**. The prompt contains the beat
  situation, NPC personas, and each option's label/pros/cons — never KPI
  deltas — and nothing the model says feeds back into scoring.
  ``ScoringEngine.apply`` remains the only KPI path.
- Any failure (missing config, connect/read timeout, HTTP error, empty or
  unusable stream) falls back to ``DeterministicDebate`` mid-beat so the game
  never stalls. Every fallback is logged with the cause.

The model is instructed to emit one dialogue line per newline in the form
``speaker_id: text``; the stream parser reassembles token chunks into lines
and maps each onto the ``DebateDelta`` shape the frontend already consumes.

Env:

    OPENAI_BASE_URL    chat-completions base URL (required to use gateway)
    OPENAI_API_KEY     bearer token (required to use gateway)
    GATEWAY_MODEL      model name (default: gpt-4o-mini)
    GATEWAY_TIMEOUT_S  request timeout in seconds (default: 20; connect: 5)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, AsyncIterator

import httpx

from app.engine.protocols import DebateContext, DebateDelta
from app.providers.deterministic import DeterministicDebate

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT_S = 20.0
CONNECT_TIMEOUT_S = 5.0

# Dialogue flavor for the prompt; scoring never sees any of this.
PERSONAS = {
    "ceo": "Meridian's CEO — defensive of the long-term plan, resents outside pressure",
    "cfo": "the CFO — numbers-first, wary of anything that strains the balance sheet",
    "gc": "the General Counsel — cautious, flags legal and disclosure risk",
    "chair": "the Independent Board Chair — measured, protects board legitimacy",
    "analyst": "your analyst — sharp, argues the activist upside case",
    "partner": "your activist-fund partner — aggressive, wants leverage and speed",
}


class GatewayError(RuntimeError):
    """Gateway misconfigured or produced no usable dialogue."""


def build_messages(ctx: DebateContext) -> list[dict[str, str]]:
    """Chat messages from beat context: situation + personas + option pros/cons.

    Deliberately excludes option ``deltas`` (and everything else numeric from
    the engine) — the LLM must never see or influence KPI math.
    """
    beat = ctx.get("beat", {})
    npcs = list(ctx.get("npcs", [])) or list(PERSONAS)

    roster = "\n".join(
        f"- {npc}: {PERSONAS.get(npc, 'a Meridian insider')}" for npc in npcs
    )
    option_lines = []
    for option in ctx.get("options", []):
        label = option.get("label", option.get("id", "?"))
        pros = "; ".join(option.get("pros", []))
        cons = "; ".join(option.get("cons", []))
        option_lines.append(f'- "{label}" — for: {pros} | against: {cons}')

    system = (
        "You write short in-character debate dialogue for an activist-investor "
        "strategy game set at the fictitious company Meridian Dynamics.\n"
        "Rules:\n"
        f"- Output ONLY dialogue lines, one per line, formatted exactly as "
        f"'speaker_id: text'. Valid speaker_ids: {', '.join(npcs)}.\n"
        "- 6 to 10 lines total. Keep each line under 30 words.\n"
        "- Argue the qualitative trade-offs of the options from each persona's "
        "point of view. Do not pick a winner — the player decides.\n"
        "- NEVER mention numeric scores, stat changes, or game mechanics. "
        "Dialogue flavor only.\n"
        "- No markdown, no stage directions, no blank lines."
    )
    user = (
        f"Scene: {beat.get('title', 'Debate')}\n"
        f"Situation: {beat.get('situation', '')}\n"
        f"Debate topic: {beat.get('debateTopic', '')}\n"
        f"Cast:\n{roster}\n"
        f"Options on the table:\n" + "\n".join(option_lines)
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


class GatewayDebate:
    """Streams LLM debate dialogue; falls back to :class:`DeterministicDebate`.

    ``transport`` lets tests inject an ``httpx.MockTransport`` (no network);
    ``fallback`` lets tests inject a zero-delay deterministic provider.
    """

    def __init__(
        self,
        fallback: DeterministicDebate | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._fallback = fallback or DeterministicDebate()
        self._transport = transport

    async def stream(self, ctx: DebateContext) -> AsyncIterator[DebateDelta]:
        try:
            previous: DebateDelta | None = None
            async for delta in self._gateway_lines(ctx):
                if previous is not None:
                    yield previous
                previous = delta
            if previous is None:
                raise GatewayError("gateway stream produced no dialogue lines")
            previous["done"] = True
            yield previous
            return
        except Exception as exc:  # noqa: BLE001 — any failure must not stall the beat
            logger.warning(
                "GatewayDebate failed (%s: %s); falling back to DeterministicDebate",
                type(exc).__name__,
                exc,
            )
        async for delta in self._fallback.stream(ctx):
            yield delta

    # -- gateway internals ------------------------------------------------

    async def _gateway_lines(self, ctx: DebateContext) -> AsyncIterator[DebateDelta]:
        """Reassemble streamed token chunks into per-line DebateDeltas."""
        npcs = set(ctx.get("npcs", [])) or set(PERSONAS)
        default_speaker = ctx.get("beat", {}).get("npcId") or "analyst"

        buffer = ""
        async for content in self._iter_content(ctx):
            buffer += content
            while "\n" in buffer:
                raw, buffer = buffer.split("\n", 1)
                delta = _parse_line(raw, npcs, default_speaker)
                if delta:
                    yield delta
        delta = _parse_line(buffer, npcs, default_speaker)
        if delta:
            yield delta

    async def _iter_content(self, ctx: DebateContext) -> AsyncIterator[str]:
        """Raw content chunks from the chat-completions SSE stream."""
        base_url = os.getenv("OPENAI_BASE_URL", "").rstrip("/")
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not base_url or not api_key:
            raise GatewayError("OPENAI_BASE_URL / OPENAI_API_KEY not configured")

        timeout_s = float(os.getenv("GATEWAY_TIMEOUT_S", str(DEFAULT_TIMEOUT_S)))
        timeout = httpx.Timeout(timeout_s, connect=min(CONNECT_TIMEOUT_S, timeout_s))
        payload: dict[str, Any] = {
            "model": os.getenv("GATEWAY_MODEL", DEFAULT_MODEL),
            "messages": build_messages(ctx),
            "stream": True,
            "temperature": 0.8,
            "max_tokens": 600,
        }

        async with httpx.AsyncClient(
            base_url=base_url, timeout=timeout, transport=self._transport
        ) as client:
            async with client.stream(
                "POST",
                "/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if not data or data == "[DONE]":
                        continue
                    chunk = json.loads(data)
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    content = (choices[0].get("delta") or {}).get("content")
                    if content:
                        yield content


def _parse_line(raw: str, npcs: set[str], default_speaker: str) -> DebateDelta | None:
    """``'ceo: We reject that.'`` -> ``{"speakerId": "ceo", "text": "We reject that."}``.

    Unknown or missing speakers are attributed to ``default_speaker`` so the
    frontend always gets a valid NPC id for the speech bubble.
    """
    line = raw.strip().lstrip("-").strip().strip("*").strip()
    if not line:
        return None
    speaker, sep, text = line.partition(":")
    if sep:
        speaker_id = speaker.strip().strip("*").lower()
        text = text.strip()
        if speaker_id in npcs and text:
            return {"speakerId": speaker_id, "text": text}
        if text:
            return {"speakerId": default_speaker, "text": text}
        return None
    return {"speakerId": default_speaker, "text": line}
