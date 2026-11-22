# Tek imaj: derlenmiş arayüz + API. Kurum içi sunucuda internet gerektirmeden çalışır
# (imaj bir kez derlendikten sonra iç kayıt deposuna aktarılabilir).

FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app/backend
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    GA_FRONTEND_DIST=/app/frontend/dist \
    GA_DATABASE_URL=sqlite:////data/gorev_asistani.db
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist
RUN useradd -r -u 1001 app && mkdir -p /data && chown app /data
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
