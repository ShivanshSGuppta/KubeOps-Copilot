PY=python

install:
	$(PY) -m pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker-build:
	docker build -t app .

docker-run:
	docker run --rm -p 8000:8000 --env-file .env.example app
