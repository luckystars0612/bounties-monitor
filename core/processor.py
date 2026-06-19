"""
Processor: ties together fetching, diffing, persisting, and notifying.
Called by the scheduler on each poll cycle.
"""

from loguru import logger

from core.config import config
from core.database import get_program, log_change, upsert_program
from core.diff_engine import diff_programs
from core.fetcher import fetch_all_platforms
from core.models import BountyRange, Program, ScopeChange
from core.notifier import send_changes


def _program_to_db_scope(items: list) -> list:
    """Serialize scope items to a lightweight list for DB storage."""
    return [
        {
            "asset_identifier": item.asset_identifier,
            "asset_type": item.asset_type,
            "eligible_for_bounty": item.eligible_for_bounty,
            "max_severity": item.max_severity,
        }
        for item in items
    ]


def _db_row_to_program(row, platform: str) -> Program:
    """Reconstruct a minimal Program from a DBProgram row for diffing."""
    from core.models import ScopeItem

    in_scope = [
        ScopeItem(
            asset_identifier=s["asset_identifier"],
            asset_type=s["asset_type"],
            eligible_for_bounty=s.get("eligible_for_bounty", True),
            max_severity=s.get("max_severity"),
            platform=platform,
            program_handle=row.handle,
        )
        for s in row.get_in_scope()
    ]

    bounty_range = None
    if row.bounty_max or row.bounty_min:
        bounty_range = BountyRange(
            min_amount=row.bounty_min,
            max_amount=row.bounty_max,
            currency=row.bounty_currency or "USD",
        )

    return Program(
        platform=platform,
        handle=row.handle,
        name=row.name or row.handle,
        url=row.url or "",
        in_scope=in_scope,
        bounty_range=bounty_range,
        offers_bounties=row.offers_bounties,
        state=row.state or "public",
    )


def process_program(new_program: Program) -> list[ScopeChange]:
    """
    Process a single program:
    1. Load previous snapshot from DB
    2. Diff old vs new
    3. Persist changes to DB
    4. Return detected ScopeChange objects
    """
    db_row = get_program(new_program.platform, new_program.handle)

    # Reconstruct old Program from DB (or None if first time seen)
    old_program = _db_row_to_program(db_row, new_program.platform) if db_row else None

    # Run diff
    changes = diff_programs(old_program, new_program, config.notify_on)

    # Persist new snapshot regardless of changes
    upsert_program(
        platform=new_program.platform,
        handle=new_program.handle,
        name=new_program.name,
        url=new_program.url,
        in_scope=_program_to_db_scope(new_program.in_scope),
        out_of_scope=_program_to_db_scope(new_program.out_of_scope),
        state=new_program.state,
        offers_bounties=new_program.offers_bounties,
        bounty_min=new_program.bounty_range.min_amount if new_program.bounty_range else None,
        bounty_max=new_program.bounty_range.max_amount if new_program.bounty_range else None,
        bounty_currency=new_program.bounty_range.currency if new_program.bounty_range else "USD",
    )

    # Log each change to DB
    for change in changes:
        log_change(
            platform=change.platform,
            program_handle=change.program_handle,
            program_name=change.program_name,
            program_url=change.program_url,
            change_type=change.change_type.value,
            detail=change.detail,
            added_scopes=[
                {"asset_identifier": s.asset_identifier, "asset_type": s.asset_type}
                for s in change.added_scopes
            ],
            removed_scopes=[
                {"asset_identifier": s.asset_identifier, "asset_type": s.asset_type}
                for s in change.removed_scopes
            ],
            old_bounty=str(change.old_bounty) if change.old_bounty else None,
            new_bounty=str(change.new_bounty) if change.new_bounty else None,
        )

    return changes


def run_poll_cycle(skip_notifications: bool = False) -> dict:
    """
    Main poll cycle: fetch all platforms, process all programs, send notifications.

    Returns:
    ---
        Summary dict with counts per platform.
    """
    logger.info("━━━ Starting poll cycle ━━━")
    summary = {}
    all_changes = []

    platform_data = fetch_all_platforms()

    for platform, programs in platform_data.items():
        platform_changes = []
        for program in programs:
            try:
                changes = process_program(program)
                platform_changes.extend(changes)
            except Exception as e:
                logger.error(
                    f"[{platform}] Error processing {program.handle}: {e}"
                )

        summary[platform] = {
            "programs": len(programs),
            "changes":  len(platform_changes),
        }
        if platform_changes:
            logger.info(
                f"[{platform}] {len(platform_changes)} change(s) detected "
                f"across {len(programs)} programs"
            )
        else:
            logger.info(f"[{platform}] No changes ({len(programs)} programs checked)")

        all_changes.extend(platform_changes)

    # Send Telegram notifications
    if all_changes and not skip_notifications:
        sent = send_changes(all_changes)
        logger.info(f"Sent {sent}/{len(all_changes)} Telegram notifications")
    else:
        logger.info("No changes detected or notifications skipped this cycle")

    logger.info("━━━ Poll cycle complete ━━━")
    return summary
