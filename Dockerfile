FROM python:3.12.5

WORKDIR /app

# Cài system lib
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# ❗ COPY requirements trước
COPY requirements.txt .

# ❗ rồi mới pip install
RUN pip install --no-cache-dir -r requirements.txt

# (tuỳ chọn) nếu chưa có trong requirements
RUN pip install arq redis

# ❗ cuối cùng mới copy code
COPY . .