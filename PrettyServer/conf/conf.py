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
        SERVER_LIST = check_exist(data ,'Server','conf')
        if check_exist(data, 'Env', 'Env'):
            if check_exist(data['Env'], 'proxy', 'proxy'):
                ISPROXY = check_exist(data['Env']['proxy'] ,'isproxy','proxy')
                PROXY = check_exist(data['Env']['proxy'] ,'http','proxy')
            CONCURRENT_NUM = check_exist(data['Env'] ,'concurrent_num','Env')
            LOG_PATH = check_exist(data['Env'] ,'log_path','Env')
            LOG_LEVEL = check_exist(data['Env'] ,'log_level','Env')
            LOG_EXPIRE = check_exist(data['Env'] ,'log_expire','Env')
            TMDB_API = check_exist(data['Env'] ,'tmdb_api','Env')
        SYNC_TASK_LIST = check_exist(data ,'Synctask','conf')
    except:
        raise ConfigError('请检查config.yaml文件')