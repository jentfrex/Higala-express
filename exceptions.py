class AppException(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message

class InsufficientWalletBalanceError(AppException):
    def __init__(self, message: str = "Insufficient wallet balance."):
        super().__init__(status_code=400, message=message)

class OrderAlreadyAcceptedError(AppException):
    def __init__(self, message: str = "This order has already been accepted by another driver."):
        super().__init__(status_code=400, message=message)

class ResourceNotFoundError(AppException):
    def __init__(self, message: str = "Requested resource not found."):
        super().__init__(status_code=404, message=message)