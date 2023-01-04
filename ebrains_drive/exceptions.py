
class ClientHttpError(Exception):
    """This exception is raised if the returned http response is not as
    expected"""
    def __init__(self, code: int, message: str) -> None:
        super(ClientHttpError, self).__init__()
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return 'ClientHttpError[%s: %s]' % (self.code, self.message)

class OperationError(Exception):
    """Expcetion to raise when an opeartion is failed"""
    pass


class DoesNotExist(Exception):
    """Raised when not matching resource can be found."""
    def __init__(self, msg: str) -> None:
        super(DoesNotExist, self).__init__()
        self.msg = msg

    def __str__(self):
        return 'DoesNotExist: %s' % self.msg
