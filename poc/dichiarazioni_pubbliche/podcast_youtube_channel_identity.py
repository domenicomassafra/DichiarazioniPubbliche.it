"""#182: one strict channel identity across the two YouTube Atom feed forms.

YouTube's ``videos.xml`` feed reports the channel twice with different spellings:
the feed-level ``yt:channelId`` carries the 22-character channel key while each
``entry`` repeats the canonical ``UC``-prefixed 24-character channel ID
(observed 2026-10-23 on the approved Pulp channel and on two unrelated public
channels). Both spellings name exactly one channel, so identity has to be
compared on the ``UC``-prefixed canonical form and nothing else.

Malformed input never matches: an unexpected prefix, length or character set is a
refusal, never a fuzzy match, a case-fold or a prefix comparison.
"""

from __future__ import annotations

import re

# Canonical channel IDs are exactly "UC" plus 22 URL-safe characters.
CHANNEL_ID = re.compile(r"UC[A-Za-z0-9_-]{22}\Z")
# The feed form drops the leading "UC"; nothing else is accepted.
FEED_CHANNEL_FORM = re.compile(r"(?:UC)?([A-Za-z0-9_-]{22})\Z")


def canonical_channel_id(value: object) -> str:
    """Return the canonical ``UC``-prefixed channel ID or raise ``ValueError``."""
    text = value.strip() if isinstance(value, str) else ""
    if not CHANNEL_ID.fullmatch(text):
        raise ValueError("YOUTUBE_CHANNEL_ID_INVALID")
    return text


def same_channel(left: object, right: object) -> bool:
    """True only when both spellings identify the same canonical channel."""
    try:
        return canonical_channel_id(_from_feed_form(left)) == canonical_channel_id(
            _from_feed_form(right)
        )
    except ValueError:
        return False


def _from_feed_form(value: object) -> object:
    """Expand the 22-character feed spelling; leave anything else untouched."""
    text = value.strip() if isinstance(value, str) else ""
    match = FEED_CHANNEL_FORM.fullmatch(text)
    if match is None:
        return text
    return f"UC{match.group(1)}"
