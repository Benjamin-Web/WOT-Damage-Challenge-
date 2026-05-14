FROM python:3.11-slim

WORKDIR /app

COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ ./server/
COPY overlay/ ./overlay/

EXPOSE 5000

CMD ["python", "server/server.py"]
