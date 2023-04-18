class BaseException(Exception):
    def __init__(self,msg:str=None) -> None:
        self.msg = msg

    def __str__(self) -> str:
        if self.msg:
            return self.msg
        else:
            return ''
        
class MediaTypeError(BaseException):
    pass

class FailRequest(BaseException):
    pass

class AsyncError(BaseException):
    pass

class ConfigError(BaseException):
    pass

class InvalidParams(BaseException):
    pass