FROM python:3.11 as dev

RUN pip install --upgrade pip
WORKDIR /app

RUN pip install playwright
RUN playwright install --with-deps chromium

COPY backend/requirements* /app/

RUN pip install -r requirements.txt

COPY backend/betatester /app/betatester

EXPOSE 8080
CMD ["uvicorn", "betatester.server:app", "--host", "0.0.0.0"]

FROM node:20.11.1-alpine3.18 as frontend

WORKDIR /usr/src/app

# Copy / Install dependencies
COPY frontend/*.json ./

RUN npm ci --no-audit

# Copy source (ts(x)/css/js(x)/html) code
ADD frontend/ /usr/src/app/

# Build
RUN npm run build

FROM dev as prod

COPY --from=frontend /usr/src/app/dist /app/betatester/ui/