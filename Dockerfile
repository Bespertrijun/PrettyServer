FROM --platform=$TARGETPLATFORM python:3.11.1-slim-bullseye
ENV TZ=Asia/Shanghai

COPY . /home
WORKDIR "/home"

RUN if [ "$(uname -m)" = "x86_64" ]; then \
        pip --no-cache-dir install -r requirements.txt; \
    elif [ "$(uname -m)" = "aarch64" ]; then \
        apt-get update -y && \
        apt-get install -y wget build-essential cmake && \
        wget https://github.com/BYVoid/OpenCC/archive/refs/tags/ver.1.1.1.tar.gz && \
        tar -xzf ver.1.1.1.tar.gz && \
        rm -f ver.1.1.1.tar.gz && \
        cd ./OpenCC-ver.1.1.1/python && \
        pip install -q wheel && \
        python setup.py bdist_wheel && \
        cd ./dist && \
        mv OpenCC-1.1.1-py3-none-manylinux1_aarch64.whl OpenCC-1.1.1-py3-none-linux_aarch64.whl && \
        pip --no-cache-dir install ./OpenCC-1.1.1-py3-none-linux_aarch64.whl && \
        cd /home && \
        rm -rf /home/OpenCC-ver.1.1.1 && \
        pip --no-cache-dir install -r requirements.txt && \
        apt-get remove -y wget build-essential cmake; \
    fi && \
    apt-get autoremove -y && \
    apt-get clean -y && \
    rm -rf \
        /tmp/* \
        /var/lib/apt/lists/* \
        /var/tmp/*
VOLUME [ "/log" ]
CMD ["/bin/bash", "run.sh"]