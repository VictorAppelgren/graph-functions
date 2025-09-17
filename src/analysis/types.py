from typing import TypedDict


class ReplacementInfo(TypedDict):
    tool: str | None
    id: str | None
    motivation: str


class RewriteInfo(TypedDict):
    should_rewrite: bool
    motivation: str
    section: str | None


class TestParams(TypedDict):
    motivation: str
    tool: str
    id: str | None
