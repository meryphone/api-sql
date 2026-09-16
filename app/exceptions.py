"""Domain errors, translated to HTTP responses in app.main.

EntityNotFound -> 404, InvalidFile -> 400, RepositoryError and GraphError -> 500.
"""


class EntityNotFound(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class RepositoryError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class InvalidFile(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class GraphError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
