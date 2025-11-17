import yaml
import os
from util.exception import ConfigError

def check_exist(dict, key, title):
    try:
        result = dict[key]
        return result
    except:
        raise ConfigError(f'{title}缺失{key}: 请检查config.yaml文件')

path = os.path.abspath(__file__)
dirname = os.path.dirname(os.path.dirname(os.path.dirname(path)))
with open(os.path.join(dirname,'config.yaml'), 'r', encoding='utf-8') as f:
    data = yaml.load(stream=f, Loader=yaml.FullLoader)
    try:
        SERVER_LIST = check_exist(data ,'Server','conf') or []
        if check_exist(data, 'Env', 'Env'):
            if check_exist(data['Env'], 'proxy', 'proxy'):
                ISPROXY = check_exist(data['Env']['proxy'] ,'isproxy','proxy')
                PROXY = check_exist(data['Env']['proxy'] ,'http','proxy')
            CONCURRENT_NUM = check_exist(data['Env'] ,'concurrent_num','Env')
            # Docker deployment: logs go to /conf/log
            LOG_PATH = os.path.join(dirname, 'log')
            LOG_LEVEL = "INFO"
            LOG_EXPIRE = 7
            TMDB_API = check_exist(data['Env'] ,'tmdb_api','Env')
        SYNC_TASK_LIST = check_exist(data ,'Synctask','conf') or []
        COLLECTION_SYNC_TASK_LIST = check_exist(data, 'CollectionSyncTask', 'conf') or []
    except:
        raise ConfigError('请检查config.yaml文件')