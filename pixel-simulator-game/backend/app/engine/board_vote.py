"""Pluggable board-vote resolution. Authored majority for this ship.

BOARD_VOTE_RESOLVER=authored (default). Unknown names fall back to authored.
safe_resolve() catches a non-authored resolver failure and retries authored
once. If authored cannot pick a valid winner, use the first available option.
"""

from __future__ import annotations

import logging
import os
from collections import Counter
from typing import Any

from app.engine.protocols import BoardVote, BoardVoteResolver, DebateContext

logger = logging.getLogger(__name__)

DEFAULT_RESOLVER = "authored"
VOTERS = ("chair", "ceo", "cfo", "gc")
VOTER_NAMES = {
    "ceo": "CEO",
    "cfo": "CFO",
    "gc": "General Counsel",
    "chair": "Independent Chair",
}


def _option_ids(ctx: DebateContext) -> list[str]:
    return [str(o.get("id")) for o in ctx.get("options", []) if o.get("id")]


def _label(options: list[dict[str, Any]], option_id: str) -> str:
    for option in options:
        if option.get("id") == option_id:
            return str(option.get("label", option_id))
    return option_id


class AuthoredBoardVote:
    def resolve(self, ctx: DebateContext) -> BoardVote:
        available = _option_ids(ctx)
        raw = (ctx.get("beat") or {}).get("boardVote") or {}
        authored = dict(raw.get("ballots") or {})
        ballots = {
            voter: authored[voter]
            for voter in raw.get("voters", list(VOTERS))
            if voter in authored and authored[voter] in available
        }
        if not available:
            return {"ballots": {}, "winningOptionId": ""}
        if not ballots:
            return {"ballots": {}, "winningOptionId": available[0]}

        counts = Counter(ballots.values())
        top = counts.most_common()
        best_n = top[0][1]
        tied = [opt for opt, n in top if n == best_n]
        result: BoardVote = {"ballots": ballots, "winningOptionId": tied[0]}
        if len(tied) > 1:
            chair_pick = ballots.get("chair")
            if chair_pick in tied:
                result["winningOptionId"] = chair_pick
                result["tieBrokenBy"] = "chair"
            else:
                result["winningOptionId"] = available[0]
                result.pop("tieBrokenBy", None)
        return result


_RESOLVERS: dict[str, type] = {"authored": AuthoredBoardVote}


def create_board_vote_resolver(name: str | None = None) -> BoardVoteResolver:
    key = (name or os.getenv("BOARD_VOTE_RESOLVER", DEFAULT_RESOLVER)).strip().lower()
    cls = _RESOLVERS.get(key)
    if cls is None:
        logger.warning(
            "unknown BOARD_VOTE_RESOLVER=%r; falling back to %r", key, DEFAULT_RESOLVER
        )
        cls = _RESOLVERS[DEFAULT_RESOLVER]
    return cls()


def safe_resolve(resolver: BoardVoteResolver, ctx: DebateContext) -> BoardVote:
    available = _option_ids(ctx)
    fallback_id = available[0] if available else ""

    def _valid(vote: BoardVote) -> bool:
        return bool(vote.get("winningOptionId")) and vote["winningOptionId"] in available

    try:
        vote = resolver.resolve(ctx)
        if _valid(vote):
            return vote
        logger.warning("board vote resolver returned invalid winner %r", vote)
    except Exception:
        logger.warning("board vote resolver failed", exc_info=True)

    if not isinstance(resolver, AuthoredBoardVote):
        authored = AuthoredBoardVote().resolve(ctx)
        if _valid(authored):
            return authored
    return {"ballots": {}, "winningOptionId": fallback_id}


def public_board_vote(
    vote: BoardVote,
    options: list[dict[str, Any]],
    motion_id: str,
    motion_label: str,
) -> dict[str, Any]:
    ballots = vote.get("ballots") or {}
    winner = vote.get("winningOptionId", "")
    payload: dict[str, Any] = {
        "motionId": motion_id,
        "motionLabel": motion_label,
        "votes": [
            {
                "speakerId": voter,
                "name": VOTER_NAMES.get(voter, voter),
                "optionId": option_id,
                "label": _label(options, option_id),
            }
            for voter, option_id in ballots.items()
        ],
        "winningOptionId": winner,
        "winningLabel": _label(options, winner),
    }
    if vote.get("tieBrokenBy"):
        payload["tieBrokenBy"] = vote["tieBrokenBy"]
    return payload
