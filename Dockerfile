FROM centos:7

RUN yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm && \
    yum install -y gcc gcc-c++ \
                   libtool libtool-ltdl \
                   make cmake \
                   git \
                   pkgconfig \
                   sudo \
                   automake autoconf \
                   yum-utils rpm-build python36 python36-pip && \
    yum clean all

ENV TZ="Europe/Moscow"

RUN pip3 install --upgrade pip && pip3 install pyTelegramBotAPI GitPython PySocks && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime

RUN useradd builder -u 1000 -m -G users,wheel && \
    echo "builder ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers && \
    echo "# macros"                      >  /home/builder/.rpmmacros && \
    echo "%_topdir    %(pwd)" >> /home/builder/.rpmmacros && \
    chown -R builder /home/builder

USER builder

RUN mkdir -p /home/builder/rpm/

RUN mkdir /home/builder/.ssh
COPY buildobot.py /home/builder/buildobot.py
COPY db.sql /home/builder/db.sql
COPY build-rpm /home/builder/build-rpm
COPY config.json /home/builder/config.json

ADD id_rsa /home/builder/.ssh/id_rsa
RUN sudo chown builder:builder /home/builder/.ssh/id_rsa
RUN echo -e "Host ds.autumn.su\n\tStrictHostKeyChecking no\n" >> /home/builder/.ssh/config

WORKDIR /home/builder

RUN mkdir sqlite && sqlite3 sqlite/database.sqlite <db.sql
VOLUME /home/builder/sqlite

CMD ["python3", "buildobot.py"]

