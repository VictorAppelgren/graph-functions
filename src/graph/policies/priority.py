from enum import IntEnum
from dataclasses import dataclass


class PriorityLevel(IntEnum):
    CORE = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    STRUCTURAL = 5


@dataclass(frozen=True)
class PriorityPolicy:
    interval_seconds: int
    label: str
    characteristics: str
    number_of_articles: int


PRIORITY_POLICY: dict[PriorityLevel, PriorityPolicy] = {
    PriorityLevel.CORE: PriorityPolicy(
        interval_seconds=900,
        label="traded/core",
        characteristics=(
            "Highest centrality, intraday impact, broad cross-asset transmission; directly traded and monitored continuously. "
            "Examples: major FX pairs, front-month energy, policy shocks or central-bank decisions with immediate market impact. "
            "Emphasis: macro core with clear, actionable intraday implications. "
            "Type guidance: macro, currency, commodity, asset are usually 1. "
        ),
        number_of_articles=25,
    ),
    PriorityLevel.HIGH: PriorityPolicy(
        interval_seconds=3600,
        label="high",
        characteristics=(
            "High centrality with short time-to-impact; multi-asset relevance; monitored intra-day to daily. "
            "Examples: major central-bank guidance/setup outside meetings, key index/theme/driver signals, liquidity/funding impulses. "
            "Type guidance: index, theme, driver are usually 2. "
        ),
        number_of_articles=25,
    ),
    PriorityLevel.MEDIUM: PriorityPolicy(
        interval_seconds=7200,
        label="medium",
        characteristics=(
            "Meaningful drivers with sector/thematic scope; medium horizon (days–months); indirect cross-asset spillovers. "
            "Type guidance: company is usually 3. "
        ),
        number_of_articles=20,
    ),
    PriorityLevel.LOW: PriorityPolicy(
        interval_seconds=14400,
        label="low",
        characteristics=(
            "Supporting signals with limited centrality and slow impact; monitor periodically for regime shifts or structural evidence. "
            "Type guidance: policy, event, sector, supporting, structural, geography are usually 4. "
        ),
        number_of_articles=15,
    ),
    PriorityLevel.STRUCTURAL: PriorityPolicy(
        interval_seconds=86400,
        label="structural",
        characteristics=(
            "Foundational, slow-moving macro anchors with long-run impact; strategic cadence suffices. "
            "Examples: demographics, secular policy regimes, long-run productivity."
        ),
        number_of_articles=10,
    ),
}


def get_interval_for_importance(importance: int) -> int:
    try:
        # Convert int to PriorityLevel safely
        level = PriorityLevel(importance)
    except ValueError:
        raise ValueError(f"Invalid importance: {importance}")

    return PRIORITY_POLICY[level].interval_seconds
