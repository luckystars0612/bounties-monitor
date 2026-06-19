"""
Diff engine: compares old vs new program snapshots and produces ScopeChange events.
"""

from typing import List, Optional

from core.models import BountyRange, ChangeType, Program, ScopeChange, ScopeItem


def _scope_map(items: List[ScopeItem]) -> dict:
    """Build a dict keyed by (identifier.lower, asset_type) for O(1) lookup."""
    return {
        (item.asset_identifier.lower().strip(), item.asset_type): item
        for item in items
    }


def diff_programs(
    old: Optional[Program],
    new: Program,
    notify_on: List[str],
) -> List[ScopeChange]:
    """
    Compare old vs new program state.
    Returns a list of ScopeChange objects representing detected differences.

    Args:
        old:        Previous snapshot (None = program is brand new)
        new:        Current snapshot fetched from platform
        notify_on:  List of change type strings to include (from config)
    """
    changes: List[ScopeChange] = []

    # ── Brand new program ────────────────────────────────────────────────────
    if old is None:
        if "new_program" in notify_on:
            changes.append(
                ScopeChange(
                    platform=new.platform,
                    program_handle=new.handle,
                    program_name=new.name,
                    program_url=new.url,
                    change_type=ChangeType.NEW_PROGRAM,
                    detail=f"New program discovered: {new.name}",
                    added_scopes=new.in_scope,
                )
            )
        return changes

    # ── Scope diff ───────────────────────────────────────────────────────────
    old_map = _scope_map(old.in_scope)
    new_map = _scope_map(new.in_scope)

    added = [item for key, item in new_map.items() if key not in old_map]
    removed = [item for key, item in old_map.items() if key not in new_map]

    if added and "new_scope" in notify_on:
        changes.append(
            ScopeChange(
                platform=new.platform,
                program_handle=new.handle,
                program_name=new.name,
                program_url=new.url,
                change_type=ChangeType.NEW_SCOPE,
                detail=f"{len(added)} new scope item(s) added",
                added_scopes=added,
            )
        )

    if removed and "removed_scope" in notify_on:
        changes.append(
            ScopeChange(
                platform=new.platform,
                program_handle=new.handle,
                program_name=new.name,
                program_url=new.url,
                change_type=ChangeType.REMOVED_SCOPE,
                detail=f"{len(removed)} scope item(s) removed",
                removed_scopes=removed,
            )
        )

    # ── Bounty range diff ────────────────────────────────────────────────────
    old_bounty = old.bounty_range
    new_bounty = new.bounty_range

    if old_bounty is not None and new_bounty is not None:
        old_max = old_bounty.max_amount or 0
        new_max = new_bounty.max_amount or 0

        if new_max > old_max and "bounty_increase" in notify_on:
            changes.append(
                ScopeChange(
                    platform=new.platform,
                    program_handle=new.handle,
                    program_name=new.name,
                    program_url=new.url,
                    change_type=ChangeType.BOUNTY_INCREASE,
                    detail=f"Max bounty increased: {old_bounty} → {new_bounty}",
                    old_bounty=old_bounty,
                    new_bounty=new_bounty,
                )
            )
        elif new_max < old_max and "bounty_decrease" in notify_on:
            changes.append(
                ScopeChange(
                    platform=new.platform,
                    program_handle=new.handle,
                    program_name=new.name,
                    program_url=new.url,
                    change_type=ChangeType.BOUNTY_DECREASE,
                    detail=f"Max bounty decreased: {old_bounty} → {new_bounty}",
                    old_bounty=old_bounty,
                    new_bounty=new_bounty,
                )
            )

    return changes
