import asyncio
import traceback
import datetime
import warnings
from pytz_deprecation_shim import PytzUsageWarning
from plexserver import Plexserver
from embyserver import Embyserver
from task import Task
from log import log
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from conf import PLEX_TOKEN,PLEX_URL,EMBY_URL,EMBY_PW,EMBY_USERNAME,PLEX_ROLE,PLEX_ROLE_CRON\
,PLEX_SORT,PLEX_SORT_CRON,FIRST_RUN,SYNC_TASK



async def plex_roletask(task:Task):
    await task.roletask()

async def plex_sorttask(task:Task):
    await task.sorttask()

async def cron_sync(task:Task):
    await task.cronsync()

async def sync_task(task:Task):
    await task.synctask()

async def main(scheduler,task):
    try:
        await task.init()
        if PLEX_ROLE:
            scheduler.add_job(plex_roletask,args=[task], trigger=CronTrigger.from_crontab(PLEX_ROLE_CRON))
        if PLEX_SORT:
            scheduler.add_job(plex_sorttask,args=[task], trigger=CronTrigger.from_crontab(PLEX_SORT_CRON))
        if FIRST_RUN:
            await sync_task(task)
        if SYNC_TASK:
            scheduler.add_job(cron_sync,args=[task], trigger='interval',minutes=5)
        log.info('启动完成，开始调度任务')
    except:
        log.critical(traceback.format_exc())

if __name__ == '__main__':
    warnings.filterwarnings('ignore', category=PytzUsageWarning)
    scheduler = AsyncIOScheduler()
    scheduler.start()
    log.info('初始化中.....')
    plex = Plexserver(PLEX_URL,PLEX_TOKEN)
    emby = Embyserver(EMBY_URL,username=EMBY_USERNAME,password=EMBY_PW)
    task = Task(plex,emby)
    scheduler.add_job(main,args=[scheduler,task],trigger='date',next_run_time=datetime.datetime.now()+datetime.timedelta(seconds=3))
    asyncio.get_event_loop().run_forever()