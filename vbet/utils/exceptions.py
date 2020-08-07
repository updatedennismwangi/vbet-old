class VError(Exception):
    pass


class StopApplication(VError):
    pass


class InvalidUserAuthentication(VError):
    INVALID_PASSWORD = 301
    INVALID_CREDENTIALS = 300
    UNKNOWN_ERROR = 303

    def __init__(self, username, password, code=301, body=None):
        self.username = username
        self.password = password
        self.code = code
        self.body = body


class InvalidUserHash(VError):
    def __init__(self, username, error_code, message):
        self.username = username
        self.error_code = error_code
        self.message = message

    def __str__(self):
        return f'Error getting hash {self.username} [{self.error_code}] {self.message}'


class InvalidUserCache(VError):
    def __init__(self, username):
        self.username = username

    def __str__(self):
        return f'User {self.username} not found in cache'


class InvalidEvents(VError):
    def __init__(self):
        pass

    def __str__(self):
        return 'Invalid Results'


class InvalidResults(VError):
    def __init__(self, e_block_id: int, n: int, retry_count: int):
        self.e_block_id = e_block_id
        self.n = n
        self.retry_count = retry_count

    def __str__(self):
        return f'{self.e_block_id} | {self.n}'


class InvalidHistory(VError):
    def __init__(self, e_block_id: int, n: int, retry_count: int):
        self.e_block_id = e_block_id
        self.n = n
        self.retry_count = retry_count

    def __str__(self):
        return f'{self.e_block_id} | {self.n | self.retry_count}'
