from tracemoe import ATraceMoe

from twsaucenao.config import config

tracemoe = ATraceMoe(config.get('TraceMoe', 'token', fallback=None))