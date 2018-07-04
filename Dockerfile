#
# Build image
#
FROM python:3.7-slim-stretch as python

ENV LANG=C.UTF-8 
ENV DEBIAN_FRONTEND=noninteractive

ENV PYTHONUSERBASE=/opt/python

ENV PATH=/opt/python/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

FROM python as build

RUN set -x \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
         git \
         vim

RUN set -x \
    && pip install --no-cache-dir pipenv

WORKDIR /usr/src/app

COPY Pipfile Pipfile.lock ./

RUN set -x \
    && cp Pipfile.lock Pipfile.lock.orig \
    && pipenv lock -r > requirements.txt \
    && diff -u --color=always Pipfile.lock.orig Pipfile.lock \
    && rm Pipfile.lock.orig

RUN set -x \
    && pip install -r requirements.txt --no-cache-dir --ignore-installed --no-deps --user

COPY imapmover.py ./
COPY imapmover.yml config/

CMD [ "/usr/local/bin/python", "imapmover.py", "config/imapmover.yml" ]

#
# Run image
#
FROM python

COPY --from=build /opt/python/ /opt/python/
COPY --from=build /usr/src/app/ /opt/app/

COPY changelog.txt version.txt /

WORKDIR /opt/app

CMD [ "/usr/local/bin/python", "imapmover.py", "config/imapmover.yml" ]

# vim: set filetype=dockerfile:
