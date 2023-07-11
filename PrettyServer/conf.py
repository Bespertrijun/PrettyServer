import yaml
from exception import ConfigError

with open('configtest.yaml', 'r', encoding='utf-8') as f:
    data = yaml.load(stream=f, Loader=yaml.FullLoader)
    try:
        PLEX_URL = data['Server']['plex'].get('url')
        PLEX_TOKEN = data['Server']['plex'].get('token')
        EMBY_API = data['Server']['emby'].get('token')
        EMBY_URL = data['Server']['emby'].get('url')
        EMBY_USERNAME = data['Server']['emby'].get('username')
        EMBY_PW = data['Server']['emby'].get('password')
        ISPROXY = data['Proxy'].get('isproxy')
        PROXY = data['Proxy'].get('http')
        CONCURRENT_NUM = data['Env'].get('concurrent_num')
        LOG_PATH = data['Env'].get('log_path')
        LOG_EXPIRE = data['Env'].get('log_expire')
        FIRST_RUN = data['Env'].get('isfirst')
        TMDB_API = data['Env'].get('tmdb_api')
        PLEX_ROLE = data['Task']['plex']['roletask'].get('run')
        PLEX_ROLE_CRON = data['Task']['plex']['roletask'].get('crontab')
        PLEX_SORT = data['Task']['plex']['sorttask'].get('run')
        PLEX_SORT_CRON = data['Task']['plex']['sorttask'].get('crontab')
        EMBY_ROLE = data['Task']['emby']['roletask'].get('run')
        EMBY_ROLE_CRON = data['Task']['plex']['roletask'].get('crontab')
        EMBY_SORT = data['Task']['emby']['sorttask'].get('run')
        EMBY_SORT_CRON = data['Task']['emby']['sorttask'].get('crontab')
        SYNC_TASK = data['Task'].get('synctask')
    except:
        raise ConfigError('请检查config.yaml文件')