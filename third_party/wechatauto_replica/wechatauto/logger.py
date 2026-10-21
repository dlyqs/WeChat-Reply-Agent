"""Local patch: library logging belongs to the host; no plaintext files/stdout changes."""
import logging

class WechatautoLogger:
    def __init__(self):
        self.logger = logging.getLogger("wechatauto")
        self.logger.addHandler(logging.NullHandler())
        self.logger.propagate = False
        self.logger.disabled = True
    def set_debug(self, debug=False):
        pass
    def debug(self, *args, **kwargs):
        pass
    info = warning = error = critical = debug

wxlog = WechatautoLogger()
