# README

---

## Ön Koşullar

- [Docker](https://www.docker.com/get-started) yüklü olmalı
- [Docker Compose](https://docs.docker.com/compose/install/) yüklü olmalı

---

## Kurulum ve Çalıştırma

1. Repoyu klonlayın:

```bash
git clone <REPO_URL>
cd <REPO_ADI>
````

2. Ortam değişkenlerini ayarlayın:


`.env` dosyasında aşağıdaki ayarları kendi bilgisayarınıza göre düzenleyin:

```env
# PostgreSQL ayarları
POSTGRES_USER=DB-USERNAME      
POSTGRES_PASSWORD=DB-PASSWORD    
POSTGRES_DB=DB-NAME           
POSTGRES_PORT=DB-PORT             

# FastAPI ayarları
FASTAPI_PORT=8000               # Host makinede FastAPI portu
DATABASE_URL=postgresql+psycopg2://POSTGRES_USER:POSTGRES_PASSWORD@db:5432/POSTGRES_DB
SECRET_KEY=your_secret_key_here
```

```

3. Docker Compose ile uygulamayı başlatın:

```bash
docker-compose up --build
```

* Docker, PostgreSQL’i `POSTGRES_PORT` ile host makinenize yönlendirir.
* FastAPI, `FASTAPI_PORT` üzerinden erişilebilir.

4. Tarayıcıda API’ye erişim:

* API root: [http://localhost:8000](http://localhost:8000)
* Swagger docs: [http://localhost:8000/docs](http://localhost:8000/docs)
* ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)