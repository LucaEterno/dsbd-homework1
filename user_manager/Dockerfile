FROM python:3.11-slim
WORKDIR /app
COPY . .
# Converte i CRLF in LF (rimuove i caratteri \r)
RUN sed -i 's/\r$//' start.sh
RUN pip install --no-cache-dir -r requirements.txt

RUN chmod +x start.sh

CMD ["/bin/bash", "start.sh"]