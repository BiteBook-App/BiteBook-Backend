FROM mcr.microsoft.com/playwright/python:v1.43.0-jammy

WORKDIR /app

COPY . /app

RUN pip install --upgrade pip && pip install -r requirements.txt

RUN playwright install --with-deps

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]