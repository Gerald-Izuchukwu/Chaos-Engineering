FROM python:3.11-alpine

WORKDIR /

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY watcher.py .

RUN chmod +x watcher.py

CMD ["python", "-u", "watcher.py"]