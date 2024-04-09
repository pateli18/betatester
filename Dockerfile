FROM python:3.11 as backend-base

RUN pip install --upgrade pip
WORKDIR /app

RUN pip install playwright
RUN playwright install --with-deps chromium

COPY backend/requirements.txt /app/

RUN pip install -r requirements.txt -t /usr/local/lib/python3.11/site-packages

FROM backend-base as backend-dev

RUN pip install watchfiles

COPY python_package /python_package

RUN pip install -e /python_package/[local] -t /usr/local/lib/python3.11/site-packages

COPY backend/betatester_web_service /app/betatester_web_service

FROM backend-base as backend-prod

RUN pip install betatester[local]

COPY backend/betatester_web_service /app/betatester_web_service

EXPOSE 8080

CMD ["uvicorn", "betatester_web_service.server:app", "--host", "0.0.0.0"]

FROM node:20.11.1-alpine3.18 as frontend

WORKDIR /usr/src/app

# Copy / Install dependencies
COPY frontend/*.json ./

RUN npm ci --no-audit

# Copy source (ts(x)/css/js(x)/html) code
ADD frontend/ /usr/src/app/

# Build
RUN npm run build

FROM backend-prod as prod

COPY --from=frontend /usr/src/app/dist /app/betatester_web_service/ui/