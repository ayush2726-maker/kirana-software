from __future__ import annotations

import backend.native_owner_app_ext as native_owner
import backend.owner_final_inline_ext as final_owner
import backend.stable_owner_app_ext as stable_owner


VERSION = "134"
native_owner.BUILD = VERSION
final_owner.BUILD = VERSION
stable_owner.VERSION = VERSION
