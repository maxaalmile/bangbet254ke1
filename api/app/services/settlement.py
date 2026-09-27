from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.bet import Bet
from app.models.match import Match
from app.models.transaction import Transaction
from app.models.wallet import Wallet


def money(value: Decimal) -> Decimal:
    return value.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def get_match_result(match: Match) -> str:
    if match.home_score > match.away_score:
        return "home"

    if match.home_score < match.away_score:
        return "away"

    return "draw"


def normalize_selection(selection: str) -> str:
    value = str(selection).strip().lower()

    if value in {"home", "h", "1", "home win"}:
        return "home"

    if value in {"draw", "x", "d", "tie"}:
        return "draw"

    if value in {"away", "a", "2", "away win"}:
        return "away"

    return value


def selection_wins(selection: dict, match: Match) -> bool:
    return (
        normalize_selection(selection.get("selection", ""))
        == get_match_result(match)
    )


def settle_match(
    db: Session,
    match: Match,
) -> dict:
    """
    Settle active bets containing this match.

    Single match:
        payout = stake * total_odds

    Accumulator:
        Remains active until every selected match is ended.
        It wins only when every selection wins.

    Only active bets are processed, preventing duplicate payouts.
    """

    if match.status != "ended":
        raise HTTPException(
            status_code=400,
            detail="Match must be ended before bets can be settled.",
        )

    if match.home_score is None or match.away_score is None:
        raise HTTPException(
            status_code=400,
            detail="Final scores must be entered before ending the match.",
        )

    match.is_live = False
    match.is_betting_open = False

    bets = (
        db.query(Bet)
        .filter(Bet.status == "active")
        .all()
    )

    settled_count = 0
    won_count = 0
    lost_count = 0
    total_paid = Decimal("0.00")

    for bet in bets:
        selections = bet.selections or []

        current_selection = None

        for selection in selections:
            try:
                selection_match_id = int(selection.get("match_id"))
            except (TypeError, ValueError):
                continue

            if selection_match_id == match.id:
                current_selection = selection
                break

        if current_selection is None:
            continue

        # If this match's selection loses, the whole accumulator loses.
        if not selection_wins(current_selection, match):
            bet.status = "lost"
            settled_count += 1
            lost_count += 1
            continue

        # This match won. For an accumulator, make sure every
        # other selected match has also ended.
        all_matches_ended = True
        all_selections_won = True

        for selection in selections:
            try:
                selection_match_id = int(selection.get("match_id"))
            except (TypeError, ValueError):
                all_matches_ended = False
                all_selections_won = False
                break

            other_match = db.get(Match, selection_match_id)

            if other_match is None:
                all_matches_ended = False
                all_selections_won = False
                break

            if other_match.status != "ended":
                all_matches_ended = False
                break

            if not selection_wins(selection, other_match):
                all_selections_won = False

        # Accumulator is still waiting for another match.
        if not all_matches_ended:
            continue

        wallet = (
            db.query(Wallet)
            .filter(Wallet.user_id == bet.user_id)
            .with_for_update()
            .first()
        )

        if wallet is None:
            continue

        if all_selections_won:
            payout = money(
                Decimal(str(bet.stake))
                * Decimal(str(bet.total_odds))
            )

            wallet.balance = money(
                Decimal(str(wallet.balance)) + payout
            )

            bet.status = "won"

            transaction = Transaction(
                user_id=bet.user_id,
                wallet_id=wallet.id,
                transaction_type="bet_win",
                status="approved",
                amount=payout,
                fee=Decimal("0.00"),
                total_debit=Decimal("0.00"),
                reference=f"BETWIN-{bet.id}-{match.id}",
                payment_method="betting",
                description=(
                    f"Bet #{bet.id} won. "
                    f"Match #{match.id} payout."
                ),
            )

            db.add(transaction)

            won_count += 1
            total_paid += payout

        else:
            bet.status = "lost"
            lost_count += 1

        settled_count += 1

    return {
        "match_id": match.id,
        "result": get_match_result(match),
        "settled": settled_count,
        "won": won_count,
        "lost": lost_count,
        "total_paid": money(total_paid),
    }
