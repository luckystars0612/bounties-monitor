"""
Fetcher module: downloads JSON data files from arkadiyt/bounty-targets-data
and parses them into Program objects.

Data source: https://github.com/arkadiyt/bounty-targets-data
Updated hourly by the upstream GitHub Actions crawler.
"""

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import config
from core.models import BountyRange, Program, ScopeItem

# ── Data file URLs ────────────────────────────────────────────────────────────

PLATFORM_URLS = {
    "hackerone": f"{config.data_base_url}/hackerone_data.json",
    "bugcrowd":  f"{config.data_base_url}/bugcrowd_data.json",
    "intigriti": f"{config.data_base_url}/intigriti_data.json",
    "yeswehack": f"{config.data_base_url}/yeswehack_data.json",
    "federacy":  f"{config.data_base_url}/federacy_data.json",
}


def _build_headers() -> dict:
    """Build HTTP headers, adding GitHub token if available."""
    headers = {"User-Agent": "bounties-monitor/1.0"}
    token = config.github_token.strip()
    if token and not token.startswith("github_pat_antigravity"):
        headers["Authorization"] = f"token {token}"
    return headers


@retry(
    stop=stop_after_attempt(config.max_retries),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def _fetch_json(url: str) -> list:
    """Download and parse a JSON array from a URL with retry logic."""
    with httpx.Client(timeout=config.request_timeout, headers=_build_headers(), follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()


# ── Platform-specific parsers ─────────────────────────────────────────────────

def _parse_hackerone_target(raw: dict, handle: str) -> ScopeItem:
    """Convert a raw HackerOne target dict into a ScopeItem."""
    return ScopeItem(
        asset_identifier=(raw.get("asset_identifier") or "").strip(),
        asset_type=(raw.get("asset_type") or "other").lower(),
        eligible_for_bounty=raw.get("eligible_for_bounty", True),
        eligible_for_submission=raw.get("eligible_for_submission", True),
        max_severity=raw.get("max_severity"),
        instruction=(raw.get("instruction") or "").strip() or None,
        platform="hackerone",
        program_handle=handle,
    )


def _parse_bugcrowd_target(raw: dict, handle: str) -> ScopeItem:
    """Convert a raw Bugcrowd target dict into a ScopeItem."""
    asset_id = raw.get("target") or raw.get("uri") or raw.get("name") or ""
    return ScopeItem(
        asset_identifier=(asset_id or "").strip(),
        asset_type=(raw.get("type") or "other").lower(),
        eligible_for_bounty=True,
        eligible_for_submission=True,
        max_severity=None,
        instruction=None,
        platform="bugcrowd",
        program_handle=handle,
    )


def _parse_intigriti_target(raw: dict, handle: str) -> ScopeItem:
    """Convert a raw Intigriti target dict into a ScopeItem."""
    return ScopeItem(
        asset_identifier=(raw.get("endpoint") or "").strip(),
        asset_type=(raw.get("type") or "other").lower(),
        eligible_for_bounty=True,
        eligible_for_submission=True,
        max_severity=raw.get("impact"),
        instruction=(raw.get("description") or "").strip() or None,
        platform="intigriti",
        program_handle=handle,
    )


def _parse_yeswehack_target(raw: dict, handle: str) -> ScopeItem:
    """Convert a raw YesWeHack target dict into a ScopeItem."""
    return ScopeItem(
        asset_identifier=(raw.get("target") or "").strip(),
        asset_type=(raw.get("type") or "other").lower(),
        eligible_for_bounty=True,
        eligible_for_submission=True,
        max_severity=None,
        instruction=None,
        platform="yeswehack",
        program_handle=handle,
    )


def _parse_federacy_target(raw: dict, handle: str) -> ScopeItem:
    """Convert a raw Federacy target dict into a ScopeItem."""
    return ScopeItem(
        asset_identifier=(raw.get("target") or "").strip(),
        asset_type=(raw.get("type") or "other").lower(),
        eligible_for_bounty=True,
        eligible_for_submission=True,
        max_severity=None,
        instruction=None,
        platform="federacy",
        program_handle=handle,
    )


def _parse_hackerone(data: list) -> list[Program]:
    """Parse HackerOne JSON format."""
    programs = []
    for p in data:
        handle = p.get("handle", "")
        targets = p.get("targets", {})

        in_scope = [
            _parse_hackerone_target(s, handle)
            for s in targets.get("in_scope", [])
        ]
        out_of_scope = [
            _parse_hackerone_target(s, handle)
            for s in targets.get("out_of_scope", [])
        ]

        programs.append(
            Program(
                platform="hackerone",
                handle=handle,
                name=p.get("name", handle),
                url=p.get("url", f"https://hackerone.com/{handle}"),
                in_scope=in_scope,
                out_of_scope=out_of_scope,
                offers_bounties=p.get("offers_bounties", True),
                managed=p.get("managed_program", False),
                state=p.get("submission_state", "open"),
            )
        )
    return programs


def _parse_bugcrowd(data: list) -> list[Program]:
    """Parse Bugcrowd JSON format."""
    programs = []
    for p in data:
        url = p.get("url") or p.get("program_url") or ""
        handle = p.get("handle") or (url.rstrip("/").split("/")[-1] if url else "")
        targets = p.get("targets", {})

        in_scope = [
            _parse_bugcrowd_target(s, handle)
            for s in targets.get("in_scope", [])
        ]
        out_of_scope = [
            _parse_bugcrowd_target(s, handle)
            for s in targets.get("out_of_scope", [])
        ]

        bounty_range = None
        max_payout = p.get("max_payout")
        offers_bounties = False
        if max_payout:
            try:
                bounty_range = BountyRange(max_amount=float(max_payout))
                if float(max_payout) > 0:
                    offers_bounties = True
            except (TypeError, ValueError):
                pass

        programs.append(
            Program(
                platform="bugcrowd",
                handle=handle,
                name=p.get("name", handle),
                url=url or f"https://bugcrowd.com/{handle}",
                in_scope=in_scope,
                out_of_scope=out_of_scope,
                offers_bounties=offers_bounties,
                bounty_range=bounty_range,
            )
        )
    return programs


def _parse_intigriti(data: list) -> list[Program]:
    """Parse Intigriti JSON format."""
    programs = []
    for p in data:
        handle = p.get("handle", p.get("id", ""))
        targets = p.get("targets", {})

        in_scope = [
            _parse_intigriti_target(s, handle)
            for s in targets.get("in_scope", [])
        ]
        out_of_scope = [
            _parse_intigriti_target(s, handle)
            for s in targets.get("out_of_scope", [])
        ]

        min_b = p.get("min_bounty")
        max_b = p.get("max_bounty")
        bounty_range = None
        offers_bounties = False

        if min_b or max_b:
            min_val = min_b.get("value") if isinstance(min_b, dict) else None
            max_val = max_b.get("value") if isinstance(max_b, dict) else None
            currency = (max_b.get("currency") if isinstance(max_b, dict) else None) or \
                       (min_b.get("currency") if isinstance(min_b, dict) else None) or "EUR"
            try:
                bounty_range = BountyRange(
                    min_amount=float(min_val) if min_val is not None else None,
                    max_amount=float(max_val) if max_val is not None else None,
                    currency=currency
                )
                if max_val and float(max_val) > 0:
                    offers_bounties = True
            except (TypeError, ValueError):
                pass

        programs.append(
            Program(
                platform="intigriti",
                handle=handle,
                name=p.get("name", handle),
                url=p.get("url", f"https://app.intigriti.com/programs/{handle}"),
                in_scope=in_scope,
                out_of_scope=out_of_scope,
                offers_bounties=offers_bounties,
                bounty_range=bounty_range,
            )
        )
    return programs


def _parse_yeswehack(data: list) -> list[Program]:
    """Parse YesWeHack JSON format."""
    programs = []
    for p in data:
        handle = p.get("slug") or p.get("handle") or p.get("id") or ""
        targets = p.get("targets", {})

        in_scope = [
            _parse_yeswehack_target(s, handle)
            for s in targets.get("in_scope", [])
        ]
        out_of_scope = [
            _parse_yeswehack_target(s, handle)
            for s in targets.get("out_of_scope", [])
        ]

        bounty_range = None
        offers_bounties = False
        min_b = p.get("min_bounty")
        max_b = p.get("max_bounty")
        if min_b or max_b:
            try:
                bounty_range = BountyRange(
                    min_amount=float(min_b) if min_b is not None else None,
                    max_amount=float(max_b) if max_b is not None else None,
                )
                if max_b and float(max_b) > 0:
                    offers_bounties = True
            except (TypeError, ValueError):
                pass

        programs.append(
            Program(
                platform="yeswehack",
                handle=handle,
                name=p.get("name", handle),
                url=p.get("program_url") or p.get("url") or f"https://yeswehack.com/programs/{handle}",
                in_scope=in_scope,
                out_of_scope=out_of_scope,
                offers_bounties=offers_bounties,
                bounty_range=bounty_range,
            )
        )
    return programs


def _parse_federacy(data: list) -> list[Program]:
    """Parse Federacy JSON format."""
    programs = []
    for p in data:
        handle = p.get("id", "")
        targets = p.get("targets", {})

        in_scope = [
            _parse_federacy_target(s, handle)
            for s in targets.get("in_scope", [])
        ]
        out_of_scope = [
            _parse_federacy_target(s, handle)
            for s in targets.get("out_of_scope", [])
        ]

        offers_bounties = p.get("offers_awards", False)

        programs.append(
            Program(
                platform="federacy",
                handle=handle,
                name=p.get("name", handle),
                url=p.get("url", f"https://www.federacy.com/{handle}"),
                in_scope=in_scope,
                out_of_scope=out_of_scope,
                offers_bounties=offers_bounties,
            )
        )
    return programs


_PARSERS = {
    "hackerone": _parse_hackerone,
    "bugcrowd":  _parse_bugcrowd,
    "intigriti": _parse_intigriti,
    "yeswehack": _parse_yeswehack,
    "federacy":  _parse_federacy,
}


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_platform(platform: str) -> list[Program]:
    """
    Fetch and parse all programs for a given platform.

    Args:
        platform: One of 'hackerone', 'bugcrowd', 'intigriti', 'yeswehack'

    Returns:
        List of Program objects with current scope data.
    """
    if platform not in PLATFORM_URLS:
        raise ValueError(f"Unknown platform: {platform}. Valid: {list(PLATFORM_URLS)}")

    url = PLATFORM_URLS[platform]
    logger.info(f"[{platform}] Fetching data from {url}")

    try:
        raw_data = _fetch_json(url)
        parser = _PARSERS[platform]
        programs = parser(raw_data)
        logger.info(f"[{platform}] Parsed {len(programs)} programs")
        return programs
    except httpx.HTTPStatusError as e:
        logger.error(f"[{platform}] HTTP error {e.response.status_code}: {url}")
        raise
    except Exception as e:
        logger.error(f"[{platform}] Failed to fetch/parse: {e}")
        raise


def fetch_all_platforms() -> dict[str, list[Program]]:
    """
    Fetch data for all enabled platforms.

    Returns:
        Dict mapping platform name → list of Programs.
        Failed platforms are skipped (logged as errors).
    """
    results = {}
    for platform in config.enabled_platforms:
        if platform not in PLATFORM_URLS:
            logger.warning(f"Skipping unknown platform: {platform}")
            continue
        try:
            results[platform] = fetch_platform(platform)
        except Exception as e:
            logger.error(f"[{platform}] Skipping due to error: {e}")
    return results
