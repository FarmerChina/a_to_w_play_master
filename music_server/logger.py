import queue
import datetime

class Logger:
    _instance = None
    _log_queue = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._log_queue = queue.Queue()
        return cls._instance

    @classmethod
    def get_queue(cls):
        if cls._log_queue is None:
            cls._log_queue = queue.Queue()
        return cls._log_queue

    @classmethod
    def log(cls, message, level="INFO"):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}"
        if cls._log_queue:
            cls._log_queue.put(log_message)

    @classmethod
    def info(cls, message):
        cls.log(message, "INFO")

    @classmethod
    def error(cls, message):
        cls.log(message, "ERROR")

    @classmethod
    def warning(cls, message):
        cls.log(message, "WARNING")
