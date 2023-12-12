import os
import sys
from datetime import timedelta
from loguru import logger as log
from conf import LOG_PATH,LOG_EXPIRE,LOG_LEVEL

if LOG_PATH in ('default',None):
    LOG_PATH = sys.path[0]
LOG_EXPIRE = timedelta(days=LOG_EXPIRE)

log.add(os.path.join(LOG_PATH,'{time}.log'),
        enqueue=True,
        format='{time:YYYY-MM-DD HH:mm:ss} - {name}:{line} - {level} - {message}',
        retention=LOG_EXPIRE,
        rotation='00:00',
        level=LOG_LEVEL
        )


