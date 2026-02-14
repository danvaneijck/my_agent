# Stage 1: Build React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY portal/frontend/package.json portal/frontend/package-lock.json* ./
RUN npm ci --ignore-scripts 2>/dev/null || npm install
COPY portal/frontend/ ./
RUN npm run build

# Stage 2: Python backend + static files
FROM python:3.12-slim
WORKDIR /app

# Install shared package
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

# Install portal requirements
COPY portal/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY portal/ /app/portal/

# Copy built frontend
COPY --from=frontend-builder /frontend/dist /app/portal/static/dist

ENV PYTHONPATH="/app:/shared"
EXPOSE 8000

CMD ["uvicorn", "portal.main:app", "--host", "0.0.0.0", "--port", "8000"]
