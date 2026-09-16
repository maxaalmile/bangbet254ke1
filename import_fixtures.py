from datetime import datetime
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.league import League
from app.models.team import Team
from app.models.match import Match
from app.models.market import Market
from app.models.odd import Odd


FIXTURES = [
    # September 16, 2026

    {"league": "La Liga", "country": "Spain", "home": "Atletico Madrid", "away": "Osasuna", "date": "2026-09-16", "time": "20:00", "home_odds": 1.41, "draw_odds": 5.00, "away_odds": 8.00},
    {"league": "La Liga", "country": "Spain", "home": "Deportivo A Coruna", "away": "Sevilla", "date": "2026-09-16", "time": "20:00", "home_odds": 2.60, "draw_odds": 3.15, "away_odds": 3.00},

    {"league": "UEFA Europa League", "country": "International Clubs", "home": "FC Ararat Armenia", "away": "Sparta Prague", "date": "2026-09-16", "time": "19:45", "home_odds": 5.00, "draw_odds": 4.10, "away_odds": 1.67},
    {"league": "UEFA Europa League", "country": "International Clubs", "home": "Omonia Nicosi", "away": "Celta Vigo", "date": "2026-09-16", "time": "19:45", "home_odds": 3.80, "draw_odds": 3.35, "away_odds": 2.09},
    {"league": "UEFA Europa League", "country": "International Clubs", "home": "AC Milan", "away": "Benfica", "date": "2026-09-16", "time": "22:00", "home_odds": 2.15, "draw_odds": 3.65, "away_odds": 3.35},
    {"league": "UEFA Europa League", "country": "International Clubs", "home": "Leverkusen", "away": "NK Celje", "date": "2026-09-16", "time": "22:00", "home_odds": 1.13, "draw_odds": 9.80, "away_odds": 19.00},
    {"league": "UEFA Europa League", "country": "International Clubs", "home": "Olympiacos", "away": "Jagiellonia Bialystok", "date": "2026-09-16", "time": "22:00", "home_odds": 1.41, "draw_odds": 5.00, "away_odds": 7.60},
    {"league": "UEFA Europa League", "country": "International Clubs", "home": "RSC Anderlecht", "away": "Lyon", "date": "2026-09-16", "time": "22:00", "home_odds": 2.90, "draw_odds": 3.65, "away_odds": 2.36},
    {"league": "UEFA Europa League", "country": "International Clubs", "home": "SK Sturm Graz", "away": "Rennes", "date": "2026-09-16", "time": "22:00", "home_odds": 3.50, "draw_odds": 3.85, "away_odds": 2.01},
    {"league": "UEFA Europa League", "country": "International Clubs", "home": "Hapoel Be'er Sheva FC", "away": "Dinamo Zagreb", "date": "2026-09-16", "time": "22:00", "home_odds": 3.65, "draw_odds": 3.75, "away_odds": 2.01},

    {"league": "EFL Cup", "country": "England", "home": "Everton", "away": "Wolves", "date": "2026-09-16", "time": "21:45", "home_odds": 1.55, "draw_odds": 4.40, "away_odds": 6.00},
    {"league": "EFL Cup", "country": "England", "home": "Man Utd", "away": "Brighton", "date": "2026-09-16", "time": "22:00", "home_odds": 1.88, "draw_odds": 4.00, "away_odds": 3.85},
    {"league": "EFL Cup", "country": "England", "home": "Coventry City", "away": "Aston Villa", "date": "2026-09-16", "time": "22:00", "home_odds": 3.10, "draw_odds": 3.70, "away_odds": 2.24},
    {"league": "EFL Cup", "country": "England", "home": "Fleetwood", "away": "Sheffield Utd", "date": "2026-09-16", "time": "21:45", "home_odds": 4.80, "draw_odds": 4.10, "away_odds": 1.70},

    {"league": "Greece Cup", "country": "Greece", "home": "Kifisias", "away": "Panathinaikos", "date": "2026-09-16", "time": "17:45", "home_odds": 5.20, "draw_odds": 3.75, "away_odds": 1.58},
    {"league": "Greece Cup", "country": "Greece", "home": "Atromitos Athens", "away": "PAOK", "date": "2026-09-16", "time": "20:00", "home_odds": 5.40, "draw_odds": 3.85, "away_odds": 1.55},

    {"league": "Premier League Russia", "country": "Russia", "home": "FK Spartak Moscow", "away": "FC Fakel Voronezh", "date": "2026-09-16", "time": "18:30", "home_odds": 1.35, "draw_odds": 5.40, "away_odds": 8.80},

    # September 17, 2026

    {"league": "UEFA Europa League", "country": "International Clubs", "home": "PFC Levski Sofia", "away": "FC Salzburg", "date": "2026-09-17", "time": "19:45", "home_odds": 3.00, "draw_odds": 3.55, "away_odds": 2.34},
    {"league": "UEFA Europa League", "country": "International Clubs", "home": "Besiktas", "away": "Marseille", "date": "2026-09-17", "time": "22:00", "home_odds": 1.79, "draw_odds": 4.10, "away_odds": 4.20},
    {"league": "UEFA Europa League", "country": "International Clubs", "home": "Viktoria Plzen", "away": "Union Saint-Gilloise", "date": "2026-09-17", "time": "22:00", "home_odds": 2.70, "draw_odds": 3.50, "away_odds": 2.60},
    {"league": "UEFA Europa League", "country": "International Clubs", "home": "Real Sociedad", "away": "Bournemouth", "date": "2026-09-17", "time": "22:00", "home_odds": 2.90, "draw_odds": 3.60, "away_odds": 2.41},
    {"league": "La Liga", "country": "Spain", "home": "Malaga", "away": "Villarreal", "date": "2026-09-17", "time": "22:30", "home_odds": 3.60, "draw_odds": 3.80, "away_odds": 2.05},
]



def get_or_create_league(
    db: Session,
    name: str,
    country: str | None,
):
    league = (
        db.query(League)
        .filter(League.name == name)
        .first()
    )

    if league:
        return league

    league = League(
        name=name,
        country=country,
        sport="football",
        is_active=True,
    )

    db.add(league)
    db.flush()

    print(f"Created league: {name}")

    return league


def get_or_create_team(
    db: Session,
    name: str,
    country: str | None,
    league_id: int,
):
    team = (
        db.query(Team)
        .filter(
            Team.name == name,
            Team.league_id == league_id,
        )
        .first()
    )

    if team:
        return team

    team = Team(
        name=name,
        short_name=None,
        logo_url=None,
        country=country,
        sport="football",
        is_active=True,
        league_id=league_id,
    )

    db.add(team)
    db.flush()

    print(f"  Created team: {name}")

    return team


def fixture_exists(
    db: Session,
    league_id: int,
    home_team_id: int,
    away_team_id: int,
    scheduled_at: datetime,
):
    return (
        db.query(Match)
        .filter(
            Match.league_id == league_id,
            Match.home_team_id == home_team_id,
            Match.away_team_id == away_team_id,
            Match.scheduled_at == scheduled_at,
        )
        .first()
    )


def create_fixture(db: Session, fixture: dict):
    league = get_or_create_league(
        db,
        fixture["league"],
        fixture.get("country"),
    )

    home_team = get_or_create_team(
        db,
        fixture["home"],
        fixture.get("country"),
        league.id,
    )

    away_team = get_or_create_team(
        db,
        fixture["away"],
        fixture.get("country"),
        league.id,
    )

    scheduled_at = datetime.fromisoformat(
        f'{fixture["date"]}T{fixture["time"]}:00+03:00'
    )

    existing = fixture_exists(
        db,
        league.id,
        home_team.id,
        away_team.id,
        scheduled_at,
    )

    if existing:
        print(
            f"SKIPPED: {fixture['home']} vs {fixture['away']} "
            f"already exists as match #{existing.id}"
        )
        return existing

    match = Match(
        league_id=league.id,
        home_team_id=home_team.id,
        away_team_id=away_team.id,
        scheduled_at=scheduled_at,
        status="upcoming",
        is_live=False,
        is_featured=False,
        is_betting_open=True,
        home_score=0,
        away_score=0,
    )

    db.add(match)
    db.flush()

    market = Market(
        match_id=match.id,
        name="Match Winner",
        market_type="1x2",
        is_active=True,
    )

    db.add(market)
    db.flush()

    db.add_all([
        Odd(
            market_id=market.id,
            name=home_team.name,
            value=float(fixture["home_odds"]),
            is_active=True,
        ),
        Odd(
            market_id=market.id,
            name="Draw",
            value=float(fixture["draw_odds"]),
            is_active=True,
        ),
        Odd(
            market_id=market.id,
            name=away_team.name,
            value=float(fixture["away_odds"]),
            is_active=True,
        ),
    ])

    db.flush()

    print(
        f"ADDED: {fixture['home']} vs {fixture['away']} "
        f"→ match #{match.id}"
    )

    return match


def main():
    db = SessionLocal()

    try:
        for fixture in FIXTURES:
            create_fixture(db, fixture)

        db.commit()

        print()
        print("Fixture import completed successfully.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
