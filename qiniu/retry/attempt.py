class Attempt:
    def __init__(self, custom_context=None):
        self.context = custom_context if custom_context is not None else {}
        self.exception = None
        self.result = None

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and exc_val is not None:
            self.exception = exc_val
            return True  # Swallow exception.
