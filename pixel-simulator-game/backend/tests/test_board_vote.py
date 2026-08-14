"""Authored board-vote resolver: majority, ties, gates, factory fallback."""

from __future__ import annotations

from app.engine.board_vote import (
    AuthoredBoardVote,
    create_board_vote_resolver,
    public_board_vote,
    safe_resolve,
)


def _ctx(ballots: dict[str, str], options: list[dict], motion_id: str = "4a") -> dict:
    return {
        "motionId": motion_id,
        "options": options,
        "beat": {
            "id": "beat-4",
            "zoneId": "boardroom",
            "boardVote": {
                "voters": ["chair", "ceo", "cfo", "gc"],
                "ballots": ballots,
            },
        },
    }


OPTS = [
    {"id": "4a", "label": "Demand two board seats"},
    {"id": "4b", "label": "Demand a formal strategic review"},
    {"id": "4c", "label": "Demand both seats and a review"},
]


def test_majority_3_1():
    vote = AuthoredBoardVote().resolve(
        _ctx({"chair": "4b", "ceo": "4b", "cfo": "4a", "gc": "4b"}, OPTS)
    )
    assert vote["winningOptionId"] == "4b"
    assert vote["ballots"] == {"chair": "4b", "ceo": "4b", "cfo": "4a", "gc": "4b"}
    assert not vote.get("tieBrokenBy")


def test_tie_2_2_chair_breaks():
    vote = AuthoredBoardVote().resolve(
        _ctx({"chair": "4b", "ceo": "4b", "cfo": "4a", "gc": "4a"}, OPTS)
    )
    assert vote["winningOptionId"] == "4b"
    assert vote["tieBrokenBy"] == "chair"


def test_tie_1_1_1_1_chair_breaks():
    opts = OPTS + [{"id": "4d", "label": "Pass"}]
    vote = AuthoredBoardVote().resolve(
        _ctx({"chair": "4a", "ceo": "4b", "cfo": "4c", "gc": "4d"}, opts)
    )
    assert vote["winningOptionId"] == "4a"
    assert vote["tieBrokenBy"] == "chair"


def test_gated_ballot_dropped():
    available = [OPTS[0], OPTS[1]]  # 4c gated out
    vote = AuthoredBoardVote().resolve(
        _ctx({"chair": "4c", "ceo": "4b", "cfo": "4b", "gc": "4a"}, available)
    )
    assert "chair" not in vote["ballots"]
    assert vote["winningOptionId"] == "4b"
    assert not vote.get("tieBrokenBy")


def test_all_ballots_invalid_uses_first_available():
    vote = AuthoredBoardVote().resolve(
        _ctx({"chair": "nope", "ceo": "nope", "cfo": "nope", "gc": "nope"}, OPTS)
    )
    assert vote["winningOptionId"] == "4a"
    assert vote["ballots"] == {}
    assert not vote.get("tieBrokenBy")


def test_factory_unknown_name_returns_authored(monkeypatch):
    monkeypatch.setenv("BOARD_VOTE_RESOLVER", "not-a-real-resolver")
    resolver = create_board_vote_resolver()
    assert isinstance(resolver, AuthoredBoardVote)


def test_safe_resolve_falls_back_when_resolver_raises():
    class Boom:
        def resolve(self, ctx):
            raise RuntimeError("agentic down")

    vote = safe_resolve(Boom(), _ctx({"chair": "4b", "ceo": "4b", "cfo": "4a", "gc": "4b"}, OPTS))
    assert vote["winningOptionId"] == "4b"


def test_public_payload_has_labels_no_deltas():
    vote = AuthoredBoardVote().resolve(
        _ctx({"chair": "4b", "ceo": "4b", "cfo": "4a", "gc": "4b"}, OPTS)
    )
    payload = public_board_vote(vote, OPTS, "4a", "Demand two board seats")
    assert payload["motionId"] == "4a"
    assert payload["motionLabel"] == "Demand two board seats"
    assert payload["winningOptionId"] == "4b"
    assert payload["winningLabel"] == "Demand a formal strategic review"
    assert "deltas" not in payload
    names = {row["speakerId"]: row["name"] for row in payload["votes"]}
    assert names["gc"] == "General Counsel"
    assert names["chair"] == "Independent Chair"
    for row in payload["votes"]:
        assert "deltas" not in row
