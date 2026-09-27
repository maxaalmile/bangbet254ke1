from datetime import datetime
import requests
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.admin import get_current_admin
from app.core.database import get_db
from app.models.league import League
from app.models.match import Match
from app.services.settlement import settle_match
from app.services.betika_bulk import bulk_create_matches
from app.models.team import Team
from app.models.market import Market
from app.models.odd import Odd
from app.models.user import User
from app.schemas.match import (
    MatchBettingUpdate,
    MatchCreate,
    MatchFeaturedUpdate,
    MatchResponse,
    MatchScoreUpdate,
    MatchStatusUpdate,
)


router = APIRouter(
    prefix="/api/admin/matches",
    tags=["Admin - Matches"],
)


class BulkMatchDeleteRequest(BaseModel):
    match_ids: list[int]


class BulkMatchCreateRequest(BaseModel):
    start_date: str
    start_time: str
    end_date: str
    end_time: str
    count: int


NAIROBI = ZoneInfo("Africa/Nairobi")


@router.post(
    "/bulk-create",
    status_code=status.HTTP_200_OK,
)
def create_matches_bulk(
    data: BulkMatchCreateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    allowed_counts = {10, 20, 30, 50, 100}

    if data.count not in allowed_counts:
        raise HTTPException(
            status_code=400,
            detail=(
                "Count must be one of: "
                "10, 20, 30, 50, 100."
            ),
        )

    try:
        start_dt = datetime.strptime(
            f"{data.start_date} {data.start_time}",
            "%Y-%m-%d %H:%M",
        ).replace(tzinfo=NAIROBI)

        end_dt = datetime.strptime(
            f"{data.end_date} {data.end_time}",
            "%Y-%m-%d %H:%M",
        ).replace(tzinfo=NAIROBI)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid date/time. "
                "Use YYYY-MM-DD and HH:MM."
            ),
        )

    if end_dt <= start_dt:
        raise HTTPException(
            status_code=400,
            detail="End date/time must be after start date/time.",
        )

    # Keep serverless requests reasonable.
    if (end_dt - start_dt).total_seconds() > 7 * 24 * 60 * 60:
        raise HTTPException(
            status_code=400,
            detail="The maximum bulk-create window is 7 days.",
        )

    try:
        return bulk_create_matches(
            start_dt=start_dt,
            end_dt=end_dt,
            requested_count=data.count,
        )

    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Betika request failed: {exc}",
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Bulk match creation failed: {exc}",
        )


@router.post(
    "",
    response_model=MatchResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_match(
    data: MatchCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if data.home_team_id == data.away_team_id:
        raise HTTPException(
            status_code=400,
            detail="Home and away teams must be different",
        )

    league = db.get(League, data.league_id)

    if not league:
        raise HTTPException(
            status_code=404,
            detail="League not found",
        )

    home_team = db.get(Team, data.home_team_id)
    away_team = db.get(Team, data.away_team_id)

    if not home_team or not away_team:
        raise HTTPException(
            status_code=404,
            detail="One or both teams not found",
        )

    match = Match(
        league_id=data.league_id,
        home_team_id=data.home_team_id,
        away_team_id=data.away_team_id,
        scheduled_at=data.scheduled_at,
        status="upcoming",
        is_live=False,
        is_featured=False,
        is_betting_open=True,
        home_score=0,
        away_score=0,
    )

    db.add(match)
    db.flush()

    # Create the standard 1X2 / Match Winner market.
    market = Market(
        match_id=match.id,
        name="Match Winner",
        market_type="1x2",
        is_active=True,
    )

    db.add(market)
    db.flush()

    # Create Home / Draw / Away odds.
    db.add_all([
        Odd(
            market_id=market.id,
            name=home_team.name,
            value=data.home_odds,
            is_active=True,
        ),
        Odd(
            market_id=market.id,
            name="Draw",
            value=data.draw_odds,
            is_active=True,
        ),
        Odd(
            market_id=market.id,
            name=away_team.name,
            value=data.away_odds,
            is_active=True,
        ),
    ])

    db.commit()
    db.refresh(match)

    return match


@router.get(
    "",
    response_model=list[MatchResponse],
)
def get_matches(
    status_filter: str | None = Query(
        default=None,
        alias="status",
    ),
    league_id: int | None = None,
    team_id: int | None = None,
    is_live: bool | None = None,
    is_featured: bool | None = None,
    is_betting_open: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    query = db.query(Match)

    if status_filter:
        query = query.filter(
            Match.status == status_filter.lower()
        )

    if league_id is not None:
        query = query.filter(
            Match.league_id == league_id
        )

    if team_id is not None:
        query = query.filter(
            (Match.home_team_id == team_id)
            | (Match.away_team_id == team_id)
        )

    if is_live is not None:
        query = query.filter(
            Match.is_live == is_live
        )

    if is_featured is not None:
        query = query.filter(
            Match.is_featured == is_featured
        )

    if is_betting_open is not None:
        query = query.filter(
            Match.is_betting_open == is_betting_open
        )

    if date_from is not None:
        query = query.filter(
            Match.scheduled_at >= date_from
        )

    if date_to is not None:
        query = query.filter(
            Match.scheduled_at <= date_to
        )

    if search:
        search_term = f"%{search.strip()}%"

        query = (
            query
            .join(
                Team,
                Match.home_team_id == Team.id,
            )
            .filter(Team.name.ilike(search_term))
        )

    return (
        query
        .order_by(Match.scheduled_at.asc())
        .all()
    )


@router.patch(
    "/{match_id}/score",
    response_model=MatchResponse,
)
def update_score(
    match_id: int,
    data: MatchScoreUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if data.home_score < 0 or data.away_score < 0:
        raise HTTPException(
            status_code=400,
            detail="Scores cannot be negative",
        )

    match = db.get(Match, match_id)

    if not match:
        raise HTTPException(
            status_code=404,
            detail="Match not found",
        )

    if match.status == "ended":
        raise HTTPException(
            status_code=400,
            detail="Final score cannot be changed after the match has been settled.",
        )

    match.home_score = data.home_score
    match.away_score = data.away_score
    match.final_score_entered = True

    db.commit()
    db.refresh(match)

    return match


@router.patch(
    "/{match_id}/status",
    response_model=MatchResponse,
)
def update_status(
    match_id: int,
    data: MatchStatusUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    allowed_statuses = {
        "upcoming",
        "live",
        "ended",
        "suspended",
        "cancelled",
    }

    new_status = data.status.lower()

    if new_status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid status. Use: upcoming, live, "
                "ended, suspended, or cancelled"
            ),
        )

    match = db.get(Match, match_id)

    if not match:
        raise HTTPException(
            status_code=404,
            detail="Match not found",
        )

    # A match cannot be ended before the admin explicitly enters the final score.
    if new_status == "ended":
        if not match.final_score_entered:
            raise HTTPException(
                status_code=400,
                detail="Enter the final score before ending the match.",
            )

        # Prevent changing an already settled match through this endpoint.
        if match.status == "ended":
            raise HTTPException(
                status_code=400,
                detail="This match has already been ended and settled.",
            )

    match.status = new_status
    match.is_live = new_status == "live"

    if new_status in {"ended", "cancelled"}:
        match.is_betting_open = False

    if new_status == "ended":
        settlement = settle_match(db, match)

        db.commit()
        db.refresh(match)

        return match

    db.commit()
    db.refresh(match)

    return match


@router.patch(
    "/{match_id}/featured",
    response_model=MatchResponse,
)
def update_featured(
    match_id: int,
    data: MatchFeaturedUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    match = db.get(Match, match_id)

    if not match:
        raise HTTPException(
            status_code=404,
            detail="Match not found",
        )

    match.is_featured = data.is_featured

    db.commit()
    db.refresh(match)

    return match


@router.patch(
    "/{match_id}/betting",
    response_model=MatchResponse,
)
def update_betting(
    match_id: int,
    data: MatchBettingUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    match = db.get(Match, match_id)

    if not match:
        raise HTTPException(
            status_code=404,
            detail="Match not found",
        )

    if match.status in {"ended", "cancelled"}:
        raise HTTPException(
            status_code=400,
            detail="Betting cannot be reopened for this match",
        )

    match.is_betting_open = data.is_betting_open

    db.commit()
    db.refresh(match)

    return match




@router.delete(
    "/bulk",
    status_code=status.HTTP_200_OK,
)
def delete_matches_bulk(
    data: BulkMatchDeleteRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    # Remove duplicates while preserving the supplied IDs.
    match_ids = list(dict.fromkeys(data.match_ids))

    if not match_ids:
        raise HTTPException(
            status_code=400,
            detail="No matches selected.",
        )

    # Only operate on matches that actually exist.
    matches = (
        db.query(Match)
        .filter(Match.id.in_(match_ids))
        .all()
    )

    found_ids = {match.id for match in matches}
    missing_ids = [
        match_id
        for match_id in match_ids
        if match_id not in found_ids
    ]

    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Match(es) not found: {missing_ids}",
        )

    # Find all markets belonging to the selected matches.
    markets = (
        db.query(Market)
        .filter(Market.match_id.in_(match_ids))
        .all()
    )

    market_ids = [market.id for market in markets]

    # Delete odds first because odds belong to markets.
    deleted_odds = 0
    if market_ids:
        deleted_odds = (
            db.query(Odd)
            .filter(Odd.market_id.in_(market_ids))
            .delete(synchronize_session=False)
        )

    # Delete markets second because markets belong to matches.
    deleted_markets = 0
    if match_ids:
        deleted_markets = (
            db.query(Market)
            .filter(Market.match_id.in_(match_ids))
            .delete(synchronize_session=False)
        )

    # Delete matches last.
    deleted_matches = (
        db.query(Match)
        .filter(Match.id.in_(match_ids))
        .delete(synchronize_session=False)
    )

    # One transaction for the entire operation.
    db.commit()

    return {
        "message": "Matches deleted successfully.",
        "deleted_matches": deleted_matches,
        "deleted_markets": deleted_markets,
        "deleted_odds": deleted_odds,
    }

@router.delete(
    "/{match_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_match(
    match_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    match = db.get(Match, match_id)

    if not match:
        raise HTTPException(
            status_code=404,
            detail="Match not found",
        )

    db.delete(match)
    db.commit()

    return None
