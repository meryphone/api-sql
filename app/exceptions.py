
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
