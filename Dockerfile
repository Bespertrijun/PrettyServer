FROM --platform=$TARGETPLATFORM python:3.11-slim-bookworm
ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安全更新：先更新系统包修复已知漏洞
RUN apt-get update -y && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
    && apt-get clean -y && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /conf

# 分层复制：先复制依赖文件，利用 Docker 缓存
COPY requirements.txt /conf/

RUN if [ "$(uname -m)" = "x86_64" ]; then \
        pip install --no-cache-dir -r requirements.txt; \
    elif [ "$(uname -m)" = "aarch64" ]; then \
        apt-get update -y && \
        apt-get install -y --no-install-recommends wget build-essential cmake && \
        wget -q https://github.com/BYVoid/OpenCC/archive/refs/tags/ver.1.1.1.tar.gz && \
        tar -xzf ver.1.1.1.tar.gz && \
        rm -f ver.1.1.1.tar.gz && \
        cd ./OpenCC-ver.1.1.1/python && \
        pip install --no-cache-dir wheel && \
        python setup.py bdist_wheel && \
        cd ./dist && \
        mv OpenCC-1.1.1-py3-none-manylinux1_aarch64.whl OpenCC-1.1.1-py3-none-linux_aarch64.whl && \
        pip install --no-cache-dir ./OpenCC-1.1.1-py3-none-linux_aarch64.whl && \
        cd /conf && \
        rm -rf /conf/OpenCC-ver.1.1.1 && \
        pip install --no-cache-dir -r requirements.txt && \
        apt-get remove -y wget build-essential cmake && \
        apt-get autoremove -y; \
    fi && \
    apt-get clean -y && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 复制应用代码
COPY . /conf

VOLUME [ "/conf/log" ]
EXPOSE 8000
CMD ["/bin/bash", "run.sh"]