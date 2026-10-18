"""Static, login-only local Studio HTML shell and nonce validation.

The private template lives in small immutable fragments, assembled in order.
Neither source contents nor credentials are embedded in this page.
"""

from __future__ import annotations

import re

from dichiarazioni_pubbliche.studio_capture_diff_browser import CAPTURE_DIFF_BROWSER_JS
from dichiarazioni_pubbliche.studio_local_page_fragment_00 import PART as PART_00
from dichiarazioni_pubbliche.studio_local_page_fragment_01 import PART as PART_01
from dichiarazioni_pubbliche.studio_local_page_fragment_02 import PART as PART_02
from dichiarazioni_pubbliche.studio_local_page_fragment_03 import PART as PART_03
from dichiarazioni_pubbliche.studio_local_page_fragment_04 import PART as PART_04
from dichiarazioni_pubbliche.studio_local_page_fragment_05 import PART as PART_05
from dichiarazioni_pubbliche.studio_local_page_fragment_06 import PART as PART_06
from dichiarazioni_pubbliche.studio_local_page_fragment_07 import PART as PART_07
from dichiarazioni_pubbliche.studio_local_page_fragment_08 import PART as PART_08
from dichiarazioni_pubbliche.studio_local_page_fragment_09 import PART as PART_09
from dichiarazioni_pubbliche.studio_local_page_fragment_10 import PART as PART_10

_NONCE = re.compile(r"^[0-9a-f]{32}$")
_PAGE = "".join((PART_00, PART_01, PART_02, PART_03, PART_04, PART_05, PART_06, PART_07, PART_08, PART_09, PART_10))

def render_studio_login_page(nonce: str) -> bytes:
    if not isinstance(nonce, str) or not _NONCE.fullmatch(nonce):
        raise ValueError("STUDIO_LOCAL_PAGE_NONCE_INVALID")
    return (_PAGE.replace("__NONCE__", nonce)
            .replace("__CAPTURE_DIFF_BROWSER_HELPERS__", CAPTURE_DIFF_BROWSER_JS)).encode("utf-8")

__all__ = ["render_studio_login_page"]
