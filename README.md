# AI Dev Team — Backend

## Ön koşullar

- [Docker](https://www.docker.com/get-started) yüklü olmalı
- [Docker Compose](https://docs.docker.com/compose/install/) yüklü olmalı
- GitHub OAuth App oluşturulmuş olmalı
- Groq API key alınmış olmalı ([console.groq.com](https://console.groq.com))

---

## Kurulum

### 1. Repoyu klonla

```bash
git clone <REPO_URL>
cd <REPO_ADI>
```

### 2. `.env` dosyası oluştur

```bash
cp .env.example .env
```

`.env` dosyasını düzenle:

```env
# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=your_db
DATABASE_URL=postgresql://postgres:your_password@db:5432/your_db

# FastAPI
FASTAPI_PORT=8000
SECRET_KEY=your_secret_key_here

# GitHub OAuth
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret

# Groq
GROQ_API_KEY=your_groq_api_key
```

### 3. GitHub OAuth App oluştur

1. [github.com/settings/developers](https://github.com/settings/developers) → **New OAuth App**
2. **Homepage URL:** `http://localhost:5173`
3. **Callback URL:** `http://localhost:8000/auth/github/callback`
4. `Client ID` ve `Client Secret`'ı `.env`'e yapıştır

### 4. Groq API key al

1. [console.groq.com](https://console.groq.com) → ücretsiz kayıt
2. **API Keys** → **Create API Key**
3. Key'i `.env`'e yapıştır

### 5. Docker ile başlat

```bash
docker-compose up --build
```

İlk çalıştırmada embedding modeli otomatik indirilir (~280MB), biraz zaman alabilir.

---

## Erişim

| Servis | URL |
|--------|-----|
| API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |

---

## Kullanım

### 1. GitHub ile giriş yap
`http://localhost:8000/auth/github/login`

### 2. Repo indexle
```bash
curl -X POST http://localhost:8000/agents/index \
  -H "Content-Type: application/json" \
  -d '{
    "token": "JWT_TOKEN",
    "owner": "github_kullanici_adi",
    "repo": "repo_adi"
  }'
```

### 3. Repo'ya soru sor
```bash
curl -X POST http://localhost:8000/agents/codebase-qa \
  -H "Content-Type: application/json" \
  -d '{
    "token": "JWT_TOKEN",
    "owner": "github_kullanici_adi",
    "repo": "repo_adi",
    "query": "authentication nerede implement edilmiş?"
  }'
```