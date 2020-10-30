ARG DOCKER_REPO_BASE=docker.io
FROM ${DOCKER_REPO_BASE}/python:3.7-buster AS builder
ENV PYTHONPATH=$PYTHONPATH:/app/vendor

WORKDIR /usr/src/app

COPY . ./
RUN pip install setuptools_scm
RUN pip install -r requirements.txt --target=vendor
RUN pip install $(pwd) --upgrade --target=vendor

FROM ${DOCKER_REPO_BASE}/python:3.7-slim
ENV PYTHONPATH=$PYTHONPATH:/app/vendor

# RUN groupadd -g 1001 appuser; useradd -u 1001 -m -g 1001 -s /usr/sbin/nologin appuser; chown -R 1001:1001 /app
RUN groupadd -g 1001 appuser; useradd -u 1001 -g appuser -s /sbin/nologin -r appuser
COPY --from=builder --chown=1001:1001 /usr/src/app/vendor/ /app/vendor/
COPY --from=builder --chown=1001:1001 /usr/src/app/vendor/bin/gadget /usr/local/bin/gadget

RUN mkdir /config; chown 1001:1001 /config
WORKDIR /config

USER appuser
CMD ["/usr/local/bin/gadget", "-l"]
