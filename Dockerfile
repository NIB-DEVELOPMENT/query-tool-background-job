# Pinned to the exact version the running prod image was built with (2025-12):
# the floating :3.11 tag drifted to a base without pkg_resources, breaking
# sdist builds in requirements.txt (found 2026-08-04).
FROM python:3.11.13

WORKDIR /app

COPY . .

RUN apt-get install -y curl

# cx-oracle==8.3.0 predates py3.11 (no wheel) and its sdist setup.py imports
# pkg_resources, removed in setuptools>=81. pip's isolated build env (PEP 517)
# ignores image-level installs, so constrain it via PIP_CONSTRAINT instead.
RUN echo "setuptools<81" > /tmp/build-constraints.txt
ENV PIP_CONSTRAINT=/tmp/build-constraints.txt
RUN pip install -r requirements.txt

RUN wget --no-check-certificate https://raw.githubusercontent.com/vishnubob/wait-for-it/master/wait-for-it.sh -O /usr/wait-for-it.sh \
    && chmod +x /usr/wait-for-it.sh

CMD ["python", "app.py"]