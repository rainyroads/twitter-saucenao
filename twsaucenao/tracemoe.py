from typing import Optional

from tracemoe import ATraceMoe

from twsaucenao.config import config

tracemoe = None  # type: Optional[ATraceMoe]
if config.getboolean('TraceMoe', 'enabled', fallback=False):
    tracemoe = ATraceMoe(config.get('TraceMoe', 'token', fallback=None))