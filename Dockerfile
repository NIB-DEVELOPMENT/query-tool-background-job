FROM python:3.11

WORKDIR /

COPY . .

RUN apt-get update \
    && apt-get install -y curl

RUN pip install -r requirements.txt

RUN wget --no-check-certificate https://raw.githubusercontent.com/vishnubob/wait-for-it/master/wait-for-it.sh -O /usr/wait-for-it.sh \
    && chmod +x /usr/wait-for-it.sh

CMD ["python", "app.py"]