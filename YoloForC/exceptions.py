class YFCError(Exception):
    """基底例外"""
    pass

class YFCConfigError(YFCError):
    """ROOT未設定など設定不備"""
    pass

class YFCStorageError(YFCError):
    """書き込み失敗、NFS切断など"""
    pass

class YFCValidationError(YFCError):
    """データが壊れている or スキーマ違反"""
    pass

class YFCNotFoundError(YFCError):
    """UUIDやデータセット不在"""
    pass

class YFCImportError(YFCError):
    """タグ形式が違うなどのインポート失敗"""
    pass