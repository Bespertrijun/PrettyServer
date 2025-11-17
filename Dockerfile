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

WORKDIR /app

# 分层复制：先复制依赖文件，利用 Docker 缓存
COPY requirements.txt /app/

# 声明构建参数(Docker Buildx 自动注入)
ARG TARGETARCH

# 使用 TARGETARCH 判断目标架构
RUN if [ "$TARGETARCH" = "amd64" ]; then \
        echo "Building for AMD64 (x86_64)..." && \
        pip install --no-cache-dir -r requirements.txt; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
        echo "Building for ARM64 (aarch64)..." && \
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
        cd /app && \
        rm -rf /app/OpenCC-ver.1.1.1 && \
        pip install --no-cache-dir -r requirements.txt && \
        apt-get remove -y wget build-essential cmake && \
        apt-get autoremove -y; \
    else \
        echo "Unsupported architecture: $TARGETARCH" && exit 1; \
    fi && \
    apt-get clean -y && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 复制应用代码
COPY . /app

# 创建数据目录(用于配置文件和日志等持久化数据)
RUN mkdir -p /data/log && \
    # 复制默认配置文件到 /app 作为模板
    cp /app/config.yaml /app/config.yaml.example

# 创建入口脚本
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# 首次运行:如果 /data 没有配置文件,复制默认配置\n\
if [ ! -f /data/config.yaml ]; then\n\
    echo "First run: Initializing config.yaml..."\n\
    cp /app/config.yaml.example /data/config.yaml\n\
    echo "Config file created at /data/config.yaml"\n\
    echo "Please edit it and restart the container."\n\
fi\n\
\n\
# 创建软链接,让应用使用 /data 中的配置和日志\n\
ln -sf /data/config.yaml /app/config.yaml\n\
ln -sf /data/log /app/log\n\
\n\
# 启动应用\n\
cd /app\n\
exec python ./PrettyServer/web_main.py\n\
' > /app/docker-entrypoint.sh && \
    chmod +x /app/docker-entrypoint.sh

VOLUME [ "/data" ]
EXPOSE 8000
CMD ["/app/docker-entrypoint.sh"]