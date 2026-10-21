from backend.constants.bgm import BGM_ERROR_MESSAGES


class BgmError(Exception):
    def __init__(self, code, status=409):
        self.code = code
        self.status = status
        super().__init__(BGM_ERROR_MESSAGES[code])
