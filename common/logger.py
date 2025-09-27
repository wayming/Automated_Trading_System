import asyncio
import os
import threading
import logging
import sys

class SingletonLoggerSafe:
    _instance = None
    _create_lock = threading.Lock()
    class _ComponentLoggerAdapter(logging.LoggerAdapter):
        """LoggerAdapter wrapper that supports async methods ainfo / aerror"""
        def __init__(self, logger, component_name: str):
            super().__init__(logger, {"component": component_name})
            self._component_name = component_name

        def info(self, msg, *args, **kwargs):
            msg = f"[{self._component_name}] {msg}"
            super().info(msg, *args, **kwargs)

        def error(self, msg, *args, **kwargs):
            msg = f"[{self._component_name}] {msg}"
            super().error(msg, *args, **kwargs)

        async def ainfo(self, msg: str):
            await asyncio.to_thread(self.info, msg)

        async def aerror(self, msg: str):
            await asyncio.to_thread(self.error, msg)

    def __new__(cls, file_path: str):
        if cls._instance:
            return cls._instance

        with cls._create_lock:
            if cls._instance:
                return cls._instance

            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s [%(levelname)s] %(message)s"
            )
            logger = logging.getLogger("SingletonLoggerSafe")
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)

            logger.setLevel(logging.INFO)
            logger.propagate = False     # Prevent double logging
            logger.write_lock = threading.Lock()

            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
                handler.close()

            # # Console handler
            ch = logging.StreamHandler(sys.stdout)
            ch.setLevel(logging.INFO)
            ch_formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s")
            ch.setFormatter(ch_formatter)
            logger.addHandler(ch)

            # File handler
            fh = logging.FileHandler(file_path)
            fh.setLevel(logging.INFO)
            fh_formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s")
            fh.setFormatter(fh_formatter)
            logger.addHandler(fh)
            
            cls._instance = logger
        logger.info(cls.__dict__)
        return cls

    @classmethod
    def info(cls, msg: str):
        if not cls._instance:
            raise ValueError("Logger not initialized")
        with cls._instance.write_lock:
            cls._instance.info(msg)
    
    @classmethod
    def error(cls, msg: str):
        if not cls._instance:
            raise ValueError("Logger not initialized")
        with cls._instance.write_lock:
            cls._instance.error(msg)

    @classmethod
    def section(cls, section: str):
        line = "#" * 50
        message = "\n" + line + "\n#  " + section + "\n" + line
        cls.info(message)

    @classmethod
    async def ainfo(cls, msg: str):
        await asyncio.to_thread(cls.info, msg)

    @classmethod
    async def aerror(cls, msg: str):
        await asyncio.to_thread(cls.error, msg)
        
    @classmethod
    def component(cls, name: str):
        if not cls._instance:
            raise ValueError("Logger not initialized")
        return cls._ComponentLoggerAdapter(cls._instance, name)


