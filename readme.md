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
TODO | 增加豆瓣源，增加docker部署方式
</div>

### 1. 下载项目
```
git clone https://github.com/Bespertrijun/PrettyServer.git
cd PrettyServer
```

### 2. 修改配置文件

```
在 config.yaml 文件按需修改
```

### 3. 安装依赖
```
python -m pip install -r requirements.txt
```

### 4. 运行

```
#可以开个screen后台运行
python ./PrettyServer/main.py
```

### 5. 注意事项

* 对于linux，若出现
`OSError: /lib/x86_64-linux-gnu/libm.so.6: version GLIBC_2.29' not found (required by /root/PrettyServer/lib/python3.7/site-packages/opencc/clib/lib/libopencc.so.1.1)`
通过以下方式解决：`pip install --upgrade opencc`
* 执行任务时，可能会出现内存激增的问题，之后可能会解决。