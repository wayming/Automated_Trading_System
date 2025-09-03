import asyncio
import os
import threading
import logging

class SafeSingletonLogger:
    _the_logger = None
    _create_lock = threading.Lock()
    def __init__(self, file_path: str):
        self.file_path = file_path

    def __new__(cls, file_path: str):
        if cls._the_logger:
            return cls._the_logger

        with cls._create_lock:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            logger = logging.getLogger(__name__)

            if not logger.handlers:
                # Console handler
                ch = logging.StreamHandler()
                ch.setLevel(logging.INFO)
                ch_formatter = logging.Formatter("[%(levelname)s] %(message)s")
                ch.setFormatter(ch_formatter)
                logger.addHandler(ch)

                # File handler
                fh = logging.FileHandler(file_path)
                fh.setLevel(logging.INFO)
                fh_formatter = logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(name)s: %(message)s")
                fh.setFormatter(fh_formatter)

                logger.addHandler(fh)
                logger.propagate = False     # Prevent double logging
                logger.write_lock = threading.Lock()
            cls._the_logger = logger
        return cls._the_logger

    @classmethod
    def info(cls, msg: str):
        if not cls._the_logger:
            raise ValueError("Logger not initialized")
        with cls._the_logger.write_lock:
            cls._the_logger.info(msg)
    
    @classmethod
    def error(cls, msg: str):
        if not cls._the_logger:
            raise ValueError("Logger not initialized")
        with cls._the_logger.write_lock:
            cls._the_logger.error(msg)

    @classmethod
    def section(cls, section: str):
        line = "#" * 50
        message = line + "\n#  " + section + "\n" + line
        cls.info(message)

    @classmethod
    async def ainfo(cls, msg: str):
        await asyncio.to_thread(cls.info, msg)

    @classmethod
    async def aerror(cls, msg: str):
        await asyncio.to_thread(cls.error, msg)
        
        