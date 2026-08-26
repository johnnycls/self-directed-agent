class AgentError(Exception):
    """Error raised by the harness, usually tied to a fixable config file."""

    def __init__(self, message: str, path: str | None = None) -> None:
        super().__init__(message)
        self.path: str | None = path
