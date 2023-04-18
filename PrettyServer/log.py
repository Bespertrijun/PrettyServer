import os
import sys
from datetime import datetime
from loguru import logger as log
from conf import LOG_PATH

if LOG_PATH == 'default':
    LOG_PATH = sys.path[0]
logfile = f'{datetime.now():%Y-%m-%d-%H-%M-%S}.log'

log.add(os.path.join(LOG_PATH,logfile),
        enqueue=True,
        format='{time:YYYY-MM-DD HH:mm:ss} - {name}:{line} - {level} - {message}'
        )


