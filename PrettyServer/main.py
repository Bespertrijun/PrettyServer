import asyncio
import traceback
import warnings
from pytz_deprecation_shim import PytzUsageWarning
from plexserver import Plexserver
from embyserver import Embyserver
from task import Task
from log import log
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from conf import PLEX_TOKEN,PLEX_URL,EMBY_URL,EMBY_PW,EMBY_USERNAME,PLEX_ROLE,PLEX_ROLE_CRON\
,PLEX_SORT,PLEX_SORT_CRON,FIRST_RUN,SYNC_TASK,EMBY_MERGE,EMBY_MERGE_CRON,EMBY_SORT,EMBY_SORT_CRON\
,PLEX_SACN,EMBY_SACN,EMBY_ROLE,EMBY_ROLE_CRON,EMBY_TITLE,EMBY_TITLE_CRON

async def plex_roletask(task:Task):
    await task.plex_role()

async def plex_sorttask(task:Task):
    await task.plex_sort()

async def plex_sacntask(task:Task,scheduler:AsyncIOScheduler):
    await task.plex_scan(scheduler)

async def emby_sorttask(task:Task):
    await task.emby_sort()

async def emby_sacntask(task:Task,scheduler:AsyncIOScheduler):
    await task.emby_scan(scheduler)

async def emby_roletask(task:Task):
    await task.emby_role()

async def emby_titletask(task:Task):
    await task.emby_season_title()

async def cron_sync(task:Task):
    await task.cronsync()

async def sync_task(task:Task):
    await task.synctask()

async def merge_task(task:Task):
    await task.emby_movie_merge()

async def main():
    try:
        warnings.filterwarnings('ignore', category=PytzUsageWarning)
        scheduler = AsyncIOScheduler()
        scheduler.start()
        log.info('初始化中.....')
        plex = Plexserver(PLEX_URL,PLEX_TOKEN)
        emby = Embyserver(EMBY_URL,username=EMBY_USERNAME,password=EMBY_PW)
        task = Task(plex,emby)
        await task.init()
        if FIRST_RUN:
            await sync_task(task)
        if PLEX_SACN:
            await plex_sacntask(task,scheduler)
        if EMBY_SACN:
            await emby_sacntask(task,scheduler)
        if PLEX_ROLE:
            scheduler.add_job(plex_roletask,args=[task], trigger=CronTrigger.from_crontab(PLEX_ROLE_CRON))
        if PLEX_SORT:
            scheduler.add_job(plex_sorttask,args=[task], trigger=CronTrigger.from_crontab(PLEX_SORT_CRON))
        if EMBY_SORT:
            scheduler.add_job(emby_sorttask,args=[task], trigger=CronTrigger.from_crontab(EMBY_SORT_CRON))
        if EMBY_MERGE:
            scheduler.add_job(merge_task,args=[task], trigger=CronTrigger.from_crontab(EMBY_MERGE_CRON))
        if EMBY_ROLE:
            scheduler.add_job(emby_roletask,args=[task], trigger=CronTrigger.from_crontab(EMBY_ROLE_CRON))
        if EMBY_TITLE:
            scheduler.add_job(emby_titletask,args=[task], trigger=CronTrigger.from_crontab(EMBY_TITLE_CRON))
        if SYNC_TASK:
            log.info('初始化同步参数')
            await task.cronsync()
            scheduler.add_job(cron_sync,args=[task], trigger='interval',minutes=1)
        log.info('启动完成，开始调度任务')
        while True:
            await asyncio.sleep(60)
    except:
        log.critical(traceback.format_exc())
        log.info("退出任务中...")
        await task.close()
        await plex.close()
        await emby.close()
        scheduler.remove_all_jobs()
        tasks = asyncio.all_tasks(loop=asyncio.get_running_loop())
        for t in tasks:
            t.cancel()
        group = asyncio.gather(*tasks,return_exceptions=True)
        asyncio.get_running_loop().run_until_complete(group)
        asyncio.get_running_loop().close()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except:
        pass