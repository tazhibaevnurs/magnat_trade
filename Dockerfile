FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-mysql.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-mysql.txt

COPY . .

RUN mkdir -p /app/staticfiles

EXPOSE 8000

CMD ["gunicorn", "magnat_trade_project.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
