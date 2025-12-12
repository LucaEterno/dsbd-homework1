FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Converte i CRLF in LF (rimuove i caratteri \r)
RUN sed -i 's/\r$//' start.sh
RUN chmod +x start.sh
CMD ["/bin/bash", "start.sh"]