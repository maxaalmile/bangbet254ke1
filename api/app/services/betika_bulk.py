import re
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

from app.core.database import SessionLocal
from app.models.league import League
from app.models.team import Team
from app.models.match import Match
from app.models.market import Market
from app.models.odd import Odd


API_URL = "https://api.betika.com/v1/uo/matches"
NAIROBI = ZoneInfo("Africa/Nairobi")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 Chrome/147 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.betika.com/lite/en-ke/",
}

PERIOD_IDS = (-1, 1, 2, 3, 4, 5)
PAGE_LIMIT = 200
MAX_PAGES = 10


def normalize(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(
        c for c in value
        if not unicodedata.combining(c)
    )
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_start_time(value):
    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d %H:%M:%S",
        ).replace(tzinfo=NAIROBI)
    except (TypeError, ValueError):
        return None


def fetch_page(session, period_id, page):
    params = {
        "page": page,
        "limit": PAGE_LIMIT,
        "tab": "",
        "sub_type_id": "1,186,340",
        "sport_id": 14,
        "tag_id": "",
        "sort_id": 1,
        "period_id": period_id,
        "esports": "false",
    }

    response = session.get(
        API_URL,
        params=params,
        headers=HEADERS,
        timeout=20,
    )
    response.raise_for_status()

    payload = response.json()

    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Betika response")

    return payload.get("data") or []


def collect_events(start_dt, end_dt, requested_count):
    """
    Fetch upcoming Betika fixtures inside the requested window.

    We use a safety buffer because some fixtures may already
    exist in the database. Once enough candidates have been
    collected, we stop making unnecessary Betika requests.
    """

    session = requests.Session()

    # Small buffer for existing/duplicate fixtures.
    target_candidates = min(
        requested_count + max(5, requested_count // 2),
        200,
    )

    now = datetime.now(NAIROBI)

    events = []
    seen = set()

    for period_id in PERIOD_IDS:
        for page in range(1, MAX_PAGES + 1):

            rows = fetch_page(
                session,
                period_id,
                page,
            )

            if not rows:
                break

            for row in rows:

                if str(row.get("sport_id")) != "14":
                    continue

                scheduled = parse_start_time(
                    row.get("start_time")
                )

                if scheduled is None:
                    continue

                if scheduled < start_dt:
                    continue

                if scheduled > end_dt:
                    continue

                if scheduled <= now:
                    continue

                home = str(
                    row.get("home_team") or ""
                ).strip()

                away = str(
                    row.get("away_team") or ""
                ).strip()

                league = str(
                    row.get("competition_name") or ""
                ).strip()

                country = str(
                    row.get("category")
                    or "International"
                ).strip()

                if not home or not away or not league:
                    continue

                try:
                    home_odd = float(
                        row.get("home_odd")
                    )
                    draw_odd = float(
                        row.get("neutral_odd")
                    )
                    away_odd = float(
                        row.get("away_odd")
                    )
                except (TypeError, ValueError):
                    continue

                provider_match_id = str(
                    row.get("match_id") or ""
                )

                key = (
                    provider_match_id,
                    scheduled.isoformat(),
                    normalize(home),
                    normalize(away),
                )

                if key in seen:
                    continue

                seen.add(key)

                events.append({
                    "provider_match_id": provider_match_id,
                    "scheduled": scheduled,
                    "league": league,
                    "country": country,
                    "home": home,
                    "away": away,
                    "home_odd": home_odd,
                    "draw_odd": draw_odd,
                    "away_odd": away_odd,
                })

            # We already have enough possible fixtures.
            if len(events) >= target_candidates:
                events.sort(
                    key=lambda item: item["scheduled"]
                )
                return events

            if len(rows) < PAGE_LIMIT:
                break

    events.sort(
        key=lambda item: item["scheduled"]
    )

    return events

def load_existing_data(db):
    """
    Load the relevant database data once.

    This replaces the previous pattern of repeatedly calling
    db.get() while checking every Betika event.
    """

    leagues = db.query(League).all()
    teams = db.query(Team).all()
    matches = db.query(Match).all()
    markets = db.query(Market).all()
    odds = db.query(Odd).all()

    league_cache = {}
    for league in leagues:
        key = normalize(league.name)
        league_cache[key] = league

    team_cache = {}
    for team in teams:
        key = (
            normalize(team.name),
            normalize(team.country or ""),
        )
        team_cache[key] = team

    match_cache = {}

    for match in matches:
        key = (
            match.league_id,
            match.home_team_id,
            match.away_team_id,
        )

        match_cache.setdefault(key, []).append(match)

    market_cache = {}

    for market in markets:
        if market.market_type != "1x2":
            continue

        market_cache[
            market.match_id
        ] = market

    odd_cache = {}

    for odd in odds:
        odd_cache[
            (odd.market_id, odd.name)
        ] = odd

    return (
        league_cache,
        team_cache,
        match_cache,
        market_cache,
        odd_cache,
    )


def match_exists(
    candidates,
    scheduled,
):
    for match in candidates:
        existing = match.scheduled_at

        if existing is None:
            continue

        if existing.tzinfo is None:
            existing = existing.replace(
                tzinfo=NAIROBI
            )
        else:
            existing = existing.astimezone(
                NAIROBI
            )

        if abs(
            (
                existing - scheduled
            ).total_seconds()
        ) <= 120:
            return True

    return False


def filter_new_events(
    db,
    events,
    requested_count,
):
    """
    Find enough fixtures that are NOT already in the DB.

    All existing DB data is cached once.
    """

    (
        league_cache,
        team_cache,
        match_cache,
        _,
        _,
    ) = load_existing_data(db)

    selected = []

    for event in events:

        league = league_cache.get(
            normalize(event["league"])
        )

        if league is None:
            # No league means there cannot be an
            # existing match in that league.
            league_id = None
        else:
            league_id = league.id

        if league_id is None:
            selected.append(event)

        else:
            home_team = team_cache.get(
                (
                    normalize(event["home"]),
                    normalize(event["country"]),
                )
            )

            away_team = team_cache.get(
                (
                    normalize(event["away"]),
                    normalize(event["country"]),
                )
            )

            if home_team is None or away_team is None:
                selected.append(event)
            else:
                key = (
                    league_id,
                    home_team.id,
                    away_team.id,
                )

                if not match_exists(
                    match_cache.get(key, []),
                    event["scheduled"],
                ):
                    selected.append(event)

        if len(selected) >= requested_count:
            break

    return selected


def import_events(events):
    if not events:
        return {
            "betika_found": 0,
            "created_matches": 0,
            "existing_matches": 0,
            "created_leagues": 0,
            "created_teams": 0,
            "created_markets": 0,
            "created_odds": 0,
        }

    db = SessionLocal()

    created_matches = 0
    existing_matches = 0
    created_leagues = 0
    created_teams = 0
    created_markets = 0
    created_odds = 0

    try:
        (
            league_cache,
            team_cache,
            match_cache,
            market_cache,
            odd_cache,
        ) = load_existing_data(db)

        for event in events:

            # =================================================
            # LEAGUE
            # =================================================

            league_key = normalize(
                event["league"]
            )

            league = league_cache.get(
                league_key
            )

            if league is None:
                league = League(
                    name=event["league"],
                    country=event["country"],
                    sport="football",
                    is_active=True,
                )

                db.add(league)
                db.flush()

                league_cache[league_key] = league
                created_leagues += 1

            # =================================================
            # TEAMS
            # =================================================

            country_key = normalize(
                event["country"]
            )

            home_key = (
                normalize(event["home"]),
                country_key,
            )

            home_team = team_cache.get(
                home_key
            )

            if home_team is None:
                home_team = Team(
                    name=event["home"],
                    country=event["country"],
                    sport="football",
                    is_active=True,
                    league_id=league.id,
                )

                db.add(home_team)
                db.flush()

                team_cache[home_key] = home_team
                created_teams += 1

            away_key = (
                normalize(event["away"]),
                country_key,
            )

            away_team = team_cache.get(
                away_key
            )

            if away_team is None:
                away_team = Team(
                    name=event["away"],
                    country=event["country"],
                    sport="football",
                    is_active=True,
                    league_id=league.id,
                )

                db.add(away_team)
                db.flush()

                team_cache[away_key] = away_team
                created_teams += 1

            # =================================================
            # MATCH
            # =================================================

            match_key = (
                league.id,
                home_team.id,
                away_team.id,
            )

            candidates = match_cache.setdefault(
                match_key,
                [],
            )

            match = None

            for candidate in candidates:
                if match_exists(
                    [candidate],
                    event["scheduled"],
                ):
                    match = candidate
                    break

            if match is None:
                if Match.__table__.c.scheduled_at.type.timezone:
                    scheduled_db = (
                        event["scheduled"]
                        .astimezone(timezone.utc)
                    )
                else:
                    scheduled_db = (
                        event["scheduled"]
                        .replace(tzinfo=None)
                    )

                match = Match(
                    league_id=league.id,
                    home_team_id=home_team.id,
                    away_team_id=away_team.id,
                    scheduled_at=scheduled_db,
                    status="upcoming",
                    is_live=False,
                    is_featured=False,
                    is_betting_open=True,
                    home_score=0,
                    away_score=0,
                )

                db.add(match)
                db.flush()

                candidates.append(match)

                created_matches += 1

            else:
                existing_matches += 1

            # =================================================
            # MARKET
            # =================================================

            market = market_cache.get(
                match.id
            )

            if market is None:
                market = Market(
                    match_id=match.id,
                    name="Match Winner",
                    market_type="1x2",
                    is_active=True,
                )

                db.add(market)
                db.flush()

                market_cache[match.id] = market
                created_markets += 1

            # =================================================
            # ODDS
            # =================================================

            event_odds = (
                (event["home"], event["home_odd"]),
                ("Draw", event["draw_odd"]),
                (event["away"], event["away_odd"]),
            )

            for odd_name, odd_value in event_odds:
                odd_key = (
                    market.id,
                    odd_name,
                )

                odd = odd_cache.get(
                    odd_key
                )

                if odd is None:
                    odd = Odd(
                        market_id=market.id,
                        name=odd_name,
                        value=odd_value,
                        is_active=True,
                    )

                    db.add(odd)

                    odd_cache[odd_key] = odd
                    created_odds += 1

                else:
                    odd.value = odd_value
                    odd.is_active = True

        db.commit()

        return {
            "betika_found": len(events),
            "created_matches": created_matches,
            "existing_matches": existing_matches,
            "created_leagues": created_leagues,
            "created_teams": created_teams,
            "created_markets": created_markets,
            "created_odds": created_odds,
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def bulk_create_matches(
    start_dt,
    end_dt,
    requested_count,
):
    # One DB session for duplicate filtering.
    db = SessionLocal()

    try:
        all_events = collect_events(
            start_dt,
            end_dt,
        )

        selected_events = filter_new_events(
            db,
            all_events,
            requested_count,
        )

    finally:
        db.close()

    result = import_events(
        selected_events
    )

    result["betika_available"] = len(
        all_events
    )

    result["requested"] = requested_count

    result["start"] = start_dt.strftime(
        "%Y-%m-%d %H:%M"
    )

    result["end"] = end_dt.strftime(
        "%Y-%m-%d %H:%M"
    )

    return result
