FROM python:3.11-slim AS builder
WORKDIR /app
COPY backend/app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --target /app/lib

FROM gcr.io/distroless/python3 AS runtime
WORKDIR /app
COPY --from=builder /app/lib /app/lib
COPY . .
ENV PYTHONPATH=/app/lib

EXPOSE 8000

ENTRYPOINT ["/usr/bin/python3", "-m", "uvicorn"]
CMD ["backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
