import pytest
import pathlib
from common.logger import SingletonLoggerSafe

@pytest.fixture(autouse=True, scope="module")
def fresh_logger(request):
    """
    Automatically generate independent SingletonLoggerSafe instances for each test file.
    """
    module_name = pathlib.Path(request.module.__file__).stem
    log_file = f"./output/tests/{module_name}.log"

    SingletonLoggerSafe._instance = None
    SingletonLoggerSafe(str(log_file))
    print(log_file)
    yield
    SingletonLoggerSafe._instance = None
