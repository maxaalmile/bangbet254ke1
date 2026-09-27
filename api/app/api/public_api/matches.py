from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.match import Match
from app.models.market import Market
from app.models.odd import Odd
from app.models.league import League
from app.models.team import Team
from sqlalchemy.orm import aliased

router = APIRouter(
    prefix="/api/public/matches",
    tags=["Public - Matches"],
)


@router.get("")
def get_public_matches(
    status: str | None = None,
    league_id: int | None = None,
    team_id: int | None = None,
    is_live: bool | None = None,
    is_featured: bool | None = None,
    search: str | None = None,
    limit: int = Query(100, ge=1, le=300),
    db: Session = Depends(get_db),
):
    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)

    stmt = (
        select(
            Match.id,
            Match.league_id,
            Match.home_team_id,
            Match.away_team_id,
            Match.scheduled_at,
            Match.status,
            Match.is_live,
            Match.is_featured,
            Match.is_betting_open,
            Match.home_score,
            Match.away_score,
            League.id.label("league_id_value"),
            League.name.label("league_name"),
            League.country.label("league_country"),
            League.sport.label("league_sport"),
            HomeTeam.id.label("home_id"),
            HomeTeam.name.label("home_name"),
            HomeTeam.country.label("home_country"),
            AwayTeam.id.label("away_id"),
            AwayTeam.name.label("away_name"),
            AwayTeam.country.label("away_country"),
        )
        .select_from(Match)
        .outerjoin(League, League.id == Match.league_id)
        .outerjoin(HomeTeam, HomeTeam.id == Match.home_team_id)
        .outerjoin(AwayTeam, AwayTeam.id == Match.away_team_id)
    )

    if status:
        stmt = stmt.where(Match.status == status.lower())

    if league_id is not None:
        stmt = stmt.where(Match.league_id == league_id)

    if team_id is not None:
        stmt = stmt.where(
            or_(
                Match.home_team_id == team_id,
                Match.away_team_id == team_id,
            )
        )

    if is_live is not None:
        stmt = stmt.where(Match.is_live == is_live)

    if is_featured is not None:
        stmt = stmt.where(Match.is_featured == is_featured)

    if search:
        search_term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                HomeTeam.name.ilike(search_term),
                AwayTeam.name.ilike(search_term),
            )
        )

    stmt = (
        stmt
        .where(Match.scheduled_at >= func.now())
        .order_by(Match.scheduled_at.asc())
        .limit(limit)
    )

    rows = db.execute(stmt).all()

    match_map = {}

    for row in rows:
        match_map[row.id] = {
            "id": row.id,
            "league_id": row.league_id,
            "league": (
                {
                    "id": row.league_id_value,
                    "name": row.league_name,
                    "country": row.league_country,
                    "sport": row.league_sport,
                }
                if row.league_id_value is not None
                else None
            ),
            "home_team_id": row.home_team_id,
            "home_team": (
                {
                    "id": row.home_id,
                    "name": row.home_name,
                    "country": row.home_country,
                }
                if row.home_id is not None
                else None
            ),
            "away_team_id": row.away_team_id,
            "away_team": (
                {
                    "id": row.away_id,
                    "name": row.away_name,
                    "country": row.away_country,
                }
                if row.away_id is not None
                else None
            ),
            "scheduled_at": row.scheduled_at,
            "status": row.status,
            "is_live": row.is_live,
            "is_featured": row.is_featured,
            "is_betting_open": row.is_betting_open,
            "home_score": row.home_score,
            "away_score": row.away_score,
            "markets": [],
        }

    match_ids = list(match_map.keys())

    if not match_ids:
        return []

    market_rows = db.execute(
        select(
            Market.id,
            Market.match_id,
            Market.name,
            Market.market_type,
            Market.is_active,
        )
        .where(
            Market.match_id.in_(match_ids),
            Market.is_active.is_(True),
        )
    ).all()

    market_map = {}

    for row in market_rows:
        market_map[row.id] = {
            "id": row.id,
            "match_id": row.match_id,
            "name": row.name,
            "market_type": row.market_type,
            "is_active": row.is_active,
            "odds": [],
        }
        match_map[row.match_id]["markets"].append(market_map[row.id])

    market_ids = list(market_map.keys())

    if market_ids:
        odd_rows = db.execute(
            select(
                Odd.id,
                Odd.market_id,
                Odd.name,
                Odd.value,
                Odd.is_active,
            )
            .where(
                Odd.market_id.in_(market_ids),
                Odd.is_active.is_(True),
            )
        ).all()

        for row in odd_rows:
            market = market_map.get(row.market_id)
            if market is not None:
                market["odds"].append(
                    {
                        "id": row.id,
                        "market_id": row.market_id,
                        "name": row.name,
                        "value": row.value,
                        "is_active": row.is_active,
                    }
                )

    return list(match_map.values())
