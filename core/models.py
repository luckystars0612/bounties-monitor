"""
Data models / dataclasses for Bounty Scope Monitor.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class ScopeType(str, Enum):
    URL = "url"
    WILDCARD = "wildcard"
    IP_RANGE = "ip_range"
    MOBILE_APP = "mobile_app"
    EXECUTABLE = "executable"
    SOURCE_CODE = "source_code"
    OTHER = "other"


class ChangeType(str, Enum):
    NEW_SCOPE = "new_scope"
    REMOVED_SCOPE = "removed_scope"
    NEW_PROGRAM = "new_program"
    BOUNTY_INCREASE = "bounty_increase"
    BOUNTY_DECREASE = "bounty_decrease"
    PROGRAM_UPDATED = "program_updated"


@dataclass
class ScopeItem:
    """A single scope target within a program."""
    asset_identifier: str          # e.g. "*.example.com" or "192.168.1.0/24"
    asset_type: str                 # url, wildcard, ip_range, mobile, etc.
    eligible_for_bounty: bool = True
    eligible_for_submission: bool = True
    max_severity: Optional[str] = None   # critical, high, medium, low
    instruction: Optional[str] = None
    # Internal
    platform: str = ""
    program_handle: str = ""

    def __hash__(self):
        return hash((self.asset_identifier.lower().strip(), self.asset_type))

    def __eq__(self, other):
        if not isinstance(other, ScopeItem):
            return False
        return (
            self.asset_identifier.lower().strip() == other.asset_identifier.lower().strip()
            and self.asset_type == other.asset_type
        )


@dataclass
class BountyRange:
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    currency: str = "USD"

    def __str__(self) -> str:
        if self.min_amount is None and self.max_amount is None:
            return "N/A"
        if self.min_amount is not None and self.max_amount is not None:
            return f"${self.min_amount:,.0f} – ${self.max_amount:,.0f} {self.currency}"
        if self.max_amount is not None:
            return f"up to ${self.max_amount:,.0f} {self.currency}"
        return f"${self.min_amount:,.0f}+ {self.currency}"


@dataclass
class Program:
    """Represents a bug bounty program snapshot."""
    platform: str                   # hackerone, bugcrowd, intigriti, yeswehack
    handle: str                     # unique identifier on that platform
    name: str
    url: str
    in_scope: List[ScopeItem] = field(default_factory=list)
    out_of_scope: List[ScopeItem] = field(default_factory=list)
    bounty_range: Optional[BountyRange] = None
    offers_bounties: bool = True
    managed: bool = False
    state: str = "public"           # public, private, paused
    last_updated: Optional[datetime] = None
    # Internal tracking
    snapshot_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def platform_url(self) -> str:
        return self.url

    def in_scope_identifiers(self) -> set:
        return {item.asset_identifier.lower().strip() for item in self.in_scope}


@dataclass
class ScopeChange:
    """A detected change in a program's scope or metadata."""
    platform: str
    program_handle: str
    program_name: str
    program_url: str
    change_type: ChangeType
    detail: str                     # Human-readable description
    # For scope changes
    added_scopes: List[ScopeItem] = field(default_factory=list)
    removed_scopes: List[ScopeItem] = field(default_factory=list)
    # For bounty changes
    old_bounty: Optional[BountyRange] = None
    new_bounty: Optional[BountyRange] = None
    detected_at: datetime = field(default_factory=datetime.utcnow)
