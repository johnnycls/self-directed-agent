class AgentError(Exception):
    def __init__(self, message: str, path: str | None = None) -> None:
        super().__init__(message)
        self.path: str | None = path
