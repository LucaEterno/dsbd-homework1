FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
WORKDIR /app/user-manager
EXPOSE 50051 8000
CMD ["python", "app.py"]
