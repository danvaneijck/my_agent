FROM python:3.12-slim
WORKDIR /app
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/
COPY modules/crew/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY modules/ /app/modules/
ENV PYTHONPATH="/app:/shared"
EXPOSE 8000
CMD ["uvicorn", "modules.crew.main:app", "--host", "0.0.0.0", "--port", "8000"]
