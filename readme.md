# PrettyServer

<div align="center">
    
功能 | 描述
--- | ---
roletask | 替换演员为中文名
sorttask | 改变标题排序
synctask | emby、plex观看同步
scantask | emby、plex定时刷新媒体库
mergetask | emby电影，混合内容库自动合并多版本电影
titletask | 通过获取tmdb季标题，修改emby剧集季标题
…… | ……
TODO | 增加豆瓣源，plex集演员中文名
</div>

### 1. 安装
```
docker run -d --name ps --network host -v <your_config.yaml>:/home/config.yaml -v <your_log_path>:/log bespertrijun/ps:latest
```

### 2.更新
```
docker rm -f ps
docker pull bespertrijun/ps:latest
docker run -d --name ps --network host -v <your_config.yaml>:/home/config.yaml -v <your_log_path>:/log bespertrijun/ps:latest
```

### 3.更新说明
 - 2024.02.21 ~修复了emby更新导致的bug （引进了emby api登录的bug，请保证用户名登录时候，config.yaml文件的的emby token为空）~
 - 2024.06.02
     - 修复2024.02.21的bug；
     - 新增jellyfin（不支持演员中文化，同步进度）；
     - 同步进度支持emby同步emby，plex同步plex。

### 4. 注意事项

* 对于linux，若出现
`OSError: /lib/x86_64-linux-gnu/libm.so.6: version GLIBC_2.29' not found (required by /root/PrettyServer/lib/python3.7/site-packages/opencc/clib/lib/libopencc.so.1.1)`
通过以下方式解决：`pip install --upgrade opencc`
* 执行任务时，可能会出现内存激增的问题，之后可能会解决。
* 对于plex中文演员，执行完后可能会发现修改失败，请尝试修改plex `在线媒体资源` -> `发现更多` -> 停用`发现来源`
* 若报错`aiohttp.client_exceptions.InvalidURL: xxx/library/sections/`
请在配置文件中删除你不需要的服务器 [Issues#4](https://github.com/Bespertrijun/PrettyServer/issues/4#issue-2046900493).
* 已更换tmdb api为 api.tmdb.org，对国内用户更加友好，无需代理。[Issues#3](https://github.com/Bespertrijun/PrettyServer/issues/3#issue-2046653124).
* 关于arm机器，opencc依赖只有0.1，0.2版本，可以通过手动build的方式解决：[Issues#1](https://github.com/Bespertrijun/PrettyServer/issues/1#issue-2046264436).
参考指令（Debian）
```
wget https://github.com/BYVoid/OpenCC/archive/refs/tags/ver.1.1.1.tar.gz &&
tar -xzf ver.1.1.1.tar.gz &&
cd ./OpenCC-ver.1.1.1/python &&
pip install -q wheel &&
apt-get install -y cmake &&
python setup.py bdist_wheel &&
cd ./dist &&
pip install ./OpenCC-ver.1.1.1/python/dist/OpenCC-1.1.1-py3-none-manylinux1_aarch64.whl
#若报错：OpenCC-1.1.1-py3-none-manylinux1_aarch64.whl is not a supported wheel on this platform.
尝试：
mv OpenCC-1.1.1-py3-none-manylinux1_aarch64.whl OpenCC-1.1.1-py3-none-linux_aarch64.whl &&
pip install ./OpenCC-1.1.1-py3-none-linux_aarch64.whl
```
