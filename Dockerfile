FROM python:3.13-slim

WORKDIR /opt/UdpGameServerChecker

COPY . .

RUN apt-get update; \
    apt-get install -y --no-install-recommends curl; \
    pip install --no-cache-dir -r requirements.txt

VOLUME ["/opt/UdpGameServerChecker/config"]

CMD ["python", "./WebServer.py"]
