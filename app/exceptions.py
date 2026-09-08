
class EntidadNoEncontrada(Exception):
    def __init__(self, mensaje : str):
        super().__init__(mensaje)


class RepositorioExcepcion(Exception):
    def __init__(self, mensaje : str):
        super().__init__(mensaje)


class ArchivoInvalido(Exception):
    def __init__(self, mensaje : str):
        super().__init__(mensaje)