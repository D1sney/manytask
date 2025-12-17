# OAuth Authentication Flow в Local Development

Этот документ подробно описывает процесс OAuth авторизации при локальной разработке с использованием Docker-контейнеров для Manytask и GitLab.

## Архитектура

При локальной разработке используются два URL для GitLab:

- **`GITLAB_OAUTH_URL`** (`http://localhost:8929`) - внешний URL, доступный из браузера на хост-машине
- **`GITLAB_URL`** (`http://gitlab:8929`) - внутренний URL для взаимодействия между Docker-контейнерами

## Полный OAuth Flow: Пошаговое описание

### Шаг 1: Начало авторизации

Пользователь открывает Manytask и нажимает кнопку "Sign in with GitLab".

```
Браузер → GET http://localhost:8081/signup
Manytask отдаёт HTML страницу с кнопкой входа
```

### Шаг 2: Редирект на GitLab (Authorization Request)

Когда пользователь кликает по кнопке, браузер отправляет запрос:

```
Браузер → GET http://localhost:8081/login
```

Manytask (через библиотеку authlib) генерирует OAuth authorization URL и делает HTTP редирект:

```http
HTTP/1.1 302 Found
Location: http://localhost:8929/oauth/authorize?
  client_id=af7c91ddc14af9c1bcb58c204ec3509dde06bbf838e4e26492ddb1ed6826cc99&
  redirect_uri=http://localhost:8081/login_finish&
  response_type=code&
  scope=openid+email+profile+read_user&
  state=7h20JYtLEm8CNzZSGnAOEPQYcvLdWD&
  code_challenge=Qh7j5U8eYQ1Xj0B_dP8E...&
  code_challenge_method=S256
```

**Параметры:**
- `client_id` - идентификатор OAuth приложения в GitLab
- `redirect_uri` - куда вернуться после авторизации
- `response_type=code` - OAuth 2.0 Authorization Code flow
- `scope` - запрашиваемые права доступа
- `state` - случайная строка для защиты от CSRF атак
- `code_challenge` + `code_challenge_method` - PKCE для дополнительной безопасности

🔑 **Важно:** Этот запрос идёт **из браузера на хост-машине**, поэтому используется `localhost:8929` (GITLAB_OAUTH_URL).

### Шаг 3: GitLab показывает страницу авторизации

```
Браузер → GET http://localhost:8929/oauth/authorize?client_id=...
```

GitLab проверяет параметры запроса:
- ✅ Существует ли OAuth приложение с таким `client_id`?
- ✅ Совпадает ли `redirect_uri` с зарегистрированным в OAuth приложении?
- ✅ Разрешены ли запрашиваемые `scopes`?

Если всё корректно, GitLab показывает:
- Форму входа (если пользователь не залогинен)
- Или страницу с кнопкой "Authorize" (если уже залогинен)

### Шаг 4: Пользователь авторизуется

Пользователь вводит credentials (например, `root` / `changeme123!`) и нажимает "Sign in" или "Authorize":

```
Браузер → POST http://localhost:8929/oauth/authorize
Body: username=root&password=changeme123!&approve=true
```

GitLab выполняет:
1. **Проверяет пароль** ✅
2. **Создаёт временный `authorization_code`** - одноразовый код, живущий ~10 минут
3. **Делает редирект** обратно в Manytask:

```http
HTTP/1.1 302 Found
Location: http://localhost:8081/login_finish?
  code=32cbd73f23223576462dc2e82a1a2afb8e51929da99422dd1efdd59d7e896dc5&
  state=7h20JYtLEm8CNzZSGnAOEPQYcvLdWD
```

🔑 **Важно:** `code` - это временный код, который нужно обменять на `access_token`. Он одноразовый и истекает через несколько минут.

### Шаг 5: Браузер следует редиректу

Браузер автоматически переходит по адресу из `Location`:

```
Браузер → GET http://localhost:8081/login_finish?code=32cbd73f...&state=7h20JYtLEm8C...
```

Manytask получает временный `code` в query параметрах.

### Шаг 6: Token Exchange - обмен `code` на `access_token` ⚠️ КРИТИЧЕСКИЙ МОМЕНТ

Теперь Manytask должен обменять временный `code` на долгоживущий `access_token`. Это происходит в коде:

```python
# manytask/auth.py:98
def handle_oauth_callback(oauth: OAuth, app: CustomFlask) -> Response:
    gitlab_oauth_token = oauth.gitlab.authorize_access_token()
    # ...
```

**Внутри authlib делает POST запрос из контейнера Manytask:**

```http
POST http://gitlab:8929/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&
code=32cbd73f23223576462dc2e82a1a2afb8e51929da99422dd1efdd59d7e896dc5&
redirect_uri=http://localhost:8081/login_finish&
client_id=af7c91ddc14af9c1bcb58c204ec3509dde06bbf838e4e26492ddb1ed6826cc99&
client_secret=0b3a36157c043e64a6100fc9aee51f6ad76bbedfdde000664688cc59e587402d...&
code_verifier=...
```

### 🔥 Почему используется `http://gitlab:8929`, а не `http://localhost:8929`?

**Проблема:**
- Этот запрос идёт **из контейнера Manytask** в **контейнер GitLab**
- Внутри Docker-контейнера `localhost` указывает на **сам контейнер**, а не на хост-машину
- Если использовать `localhost:8929`, Manytask попытается подключиться к самому себе → Connection refused ❌

**Решение:**
- Docker создаёт внутреннюю сеть между контейнерами
- Контейнеры могут обращаться друг к другу **по именам** (hostname)
- Имя контейнера GitLab = `gitlab` (указано в docker-compose.yml)
- Поэтому используется `http://gitlab:8929` ✅

**Настройка в коде:**

```python
# manytask/main.py:240-254
def _authenticate(oauth: OAuth, internal_url: str, external_url: str, ...):
    oauth.register(
        name="gitlab",
        authorize_url=f"{external_url}/oauth/authorize",      # http://localhost:8929 - для браузера
        access_token_url=f"{internal_url}/oauth/token",       # http://gitlab:8929 - между контейнерами
        userinfo_endpoint=f"{internal_url}/oauth/userinfo",   # http://gitlab:8929
        jwks_uri=f"{internal_url}/oauth/discovery/keys",      # http://gitlab:8929
        # ...
    )
```

### Шаг 7: GitLab выдаёт `access_token`

GitLab проверяет запрос:
- ✅ `code` валиден и ещё не использовался?
- ✅ `client_id` + `client_secret` правильные?
- ✅ `redirect_uri` совпадает с оригинальным?
- ✅ `code_verifier` соответствует `code_challenge` (PKCE)?

Если всё корректно, GitLab **создаёт долгоживущий `access_token`** и возвращает:

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 7200,
  "refresh_token": "8f63f3c4b8d12e7a9f6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f",
  "scope": "openid email profile read_user api",
  "created_at": 1702738695
}
```

**Токены:**
- `access_token` - JWT токен, используется для аутентификации API запросов, живёт 2 часа
- `refresh_token` - используется для получения нового `access_token` после истечения срока действия

### Шаг 8: Manytask получает информацию о пользователе

С полученным `access_token`, Manytask запрашивает данные пользователя:

```python
# manytask/auth.py:102
auth_user = app.auth_api.get_authenticated_user(token)
```

Это делает запрос:

```http
GET http://gitlab:8929/oauth/userinfo
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

GitLab возвращает:

```json
{
  "sub": "1",
  "sub_legacy": "1",
  "name": "Administrator",
  "nickname": "root",
  "email": "admin@example.com",
  "email_verified": true,
  "profile": "http://localhost:8929/root",
  "picture": "https://www.gravatar.com/avatar/...",
  "groups": ["Developers"]
}
```

### Шаг 9: Manytask сохраняет сессию

Manytask сохраняет токены и данные пользователя в Flask session:

```python
# manytask/auth.py:108
session.setdefault("gitlab", {}).update(set_oauth_session(auth_user, gitlab_oauth_token))
session.permanent = True
```

Структура сессии:

```python
session["gitlab"] = {
    "username": "root",
    "user_id": 1,
    "version": 1.5,
    "access_token": "eyJhbGciOiJSUzI1...",
    "refresh_token": "8f63f3c4b8d12e7a..."
}
```

#### Где хранится сессия?

- Flask сохраняет сессию в **подписанном cookie** на стороне клиента
- Cookie называется `session`
- Данные **зашифрованы и подписаны** с помощью `FLASK_SECRET_KEY`
- Браузер отправляет этот cookie с каждым последующим запросом
- Сервер может расшифровать и проверить подпись cookie

### Шаг 10: Редирект на финальную страницу

```python
# manytask/auth.py:112
return redirect(url_for("root.signup_finish"))
```

Manytask отправляет редирект:

```http
HTTP/1.1 302 Found
Location: http://localhost:8081/signup_finish
Set-Cookie: session=eyJnaXRsYWIiOnsiYWNjZXNzX3Rva2VuIjoi...; HttpOnly; Path=/; SameSite=Lax
```

Браузер:
1. Сохраняет cookie `session`
2. Переходит на `/signup_finish`
3. Страница просит заполнить First name / Last name

### Шаг 11: Последующие запросы - проверка авторизации

После успешной авторизации, каждый защищённый роут проверяет сессию пользователя:

```python
# manytask/auth.py:131 - декоратор @requires_auth
@requires_auth
def some_protected_route():
    # ...
```

При каждом запросе:

```
Браузер → GET http://localhost:8081/course/python2025
Cookie: session=eyJnaXRsYWIiOnsiYWNjZXNzX3Rva2VuIjoi...
```

Manytask проверяет:

```python
# 1. Проверка валидности структуры сессии
if not valid_gitlab_session(session):
    return redirect_to_login_with_bad_session()

# 2. Проверка токена в GitLab
if not app.auth_api.check_user_is_authenticated(
    app.oauth,
    session["gitlab"]["access_token"],
    session["gitlab"]["refresh_token"]
):
    return redirect_to_login_with_bad_session()
```

Проверка токена делает запрос:

```http
GET http://gitlab:8929/api/v4/user
Authorization: Bearer eyJhbGciOiJSUzI1...
```

**Результат:**
- ✅ Токен валиден → GitLab возвращает данные пользователя → доступ разрешён
- ❌ Токен истёк → используется `refresh_token` для получения нового `access_token`
- ❌ Токен невалиден → редирект на страницу входа

## Схема потока данных

```
┌─────────┐                 ┌─────────┐                 ┌────────┐
│ Browser │                 │Manytask │                 │ GitLab │
│(Mac Host)                 │Container│                 │Container
└────┬────┘                 └────┬────┘                 └────┬───┘
     │                           │                           │
     │ 1. GET /signup            │                           │
     │──────────────────────────>│                           │
     │                           │                           │
     │ 2. 302 Redirect to GitLab │                           │
     │   (http://localhost:8929) │                           │
     │<──────────────────────────│                           │
     │                           │                           │
     │ 3. GET /oauth/authorize   │                           │
     │───────────────────────────────────────────────────────>│
     │                           │                           │
     │ 4. Show login page        │                           │
     │<───────────────────────────────────────────────────────│
     │                           │                           │
     │ 5. POST credentials       │                           │
     │───────────────────────────────────────────────────────>│
     │                           │                           │
     │ 6. 302 Redirect with code │                           │
     │<───────────────────────────────────────────────────────│
     │                           │                           │
     │ 7. GET /login_finish?code=│                           │
     │──────────────────────────>│                           │
     │                           │                           │
     │                           │ 8. POST /oauth/token      │
     │                           │   (http://gitlab:8929)    │
     │                           │──────────────────────────>│
     │                           │                           │
     │                           │ 9. access_token           │
     │                           │<──────────────────────────│
     │                           │                           │
     │                           │ 10. GET /oauth/userinfo   │
     │                           │──────────────────────────>│
     │                           │                           │
     │                           │ 11. User data             │
     │                           │<──────────────────────────│
     │                           │                           │
     │ 12. 302 Redirect + cookie │                           │
     │<──────────────────────────│                           │
     │                           │                           │
     │ 13. All future requests   │                           │
     │     with session cookie   │                           │
     │──────────────────────────>│                           │
     │                           │                           │
```

## Конфигурация URL

### Переменные окружения

```bash
# .env
GITLAB_URL=http://gitlab:8929           # Внутренний URL (контейнер → контейнер)
GITLAB_OAUTH_URL=http://localhost:8929  # Внешний URL (браузер → GitLab)
```

### Использование в коде

```python
# manytask/main.py
app.oauth = _authenticate(
    OAuth(app),
    app.app_config.gitlab_url,        # Internal: http://gitlab:8929
    app.app_config.gitlab_oauth_url,  # External: http://localhost:8929
    app.app_config.gitlab_client_id,
    app.app_config.gitlab_client_secret
)

def _authenticate(oauth: OAuth, internal_url: str, external_url: str, ...):
    oauth.register(
        name="gitlab",
        # Браузер обращается к GitLab
        authorize_url=f"{external_url}/oauth/authorize",

        # Manytask контейнер обращается к GitLab контейнеру
        access_token_url=f"{internal_url}/oauth/token",
        userinfo_endpoint=f"{internal_url}/oauth/userinfo",
        jwks_uri=f"{internal_url}/oauth/discovery/keys",
        # ...
    )
```

## Создание OAuth приложения в GitLab

OAuth приложение создаётся автоматически через скрипт `scripts/setup_local_gitlab.sh`:

```bash
./scripts/setup_local_gitlab.sh
```

Скрипт создаёт OAuth приложение с параметрами:

```ruby
Doorkeeper::Application.create!(
  name: 'manytask-local',
  redirect_uri: 'http://localhost:8081/login_finish',
  scopes: 'openid email profile read_user api',
  confidential: true
)
```

**Scopes:**
- `openid` - OpenID Connect для получения ID token
- `email` - доступ к email пользователя
- `profile` - доступ к профилю (имя, аватар)
- `read_user` - чтение информации о пользователе
- `api` - доступ к API GitLab

## Частые проблемы и их решение

### 1. "Connection refused" при token exchange

**Симптом:** В логах Manytask:
```
ConnectionError: HTTPConnectionPool(host='localhost', port=8929):
Max retries exceeded with url: /oauth/token
```

**Причина:** Manytask пытается обратиться к `localhost:8929`, но внутри контейнера `localhost` = сам контейнер.

**Решение:** Использовать `http://gitlab:8929` для `access_token_url`.

### 2. "The requested scope is invalid, unknown, or malformed"

**Симптом:** Ошибка на странице GitLab после клика "Authorize".

**Причина:** OAuth приложение создано без всех необходимых scopes.

**Решение:** Пересоздать OAuth приложение с правильными scopes:
```bash
# Удалить старое приложение
docker exec -i manytask_gitlab sh -lc "gitlab-rails runner \"
  app = Doorkeeper::Application.find_by(name: 'manytask-local')
  app.destroy if app
\""

# Создать новое через скрипт
./scripts/setup_local_gitlab.sh
```

### 3. Редирект обратно на `/signup` после авторизации

**Симптом:** После успешной авторизации в GitLab, возвращаешься на страницу `/signup`.

**Причина:** Token exchange не прошёл успешно (см. проблему #1).

**Решение:** Проверить логи Manytask и исправить URL для token exchange.

## Docker Networking

### Как контейнеры находят друг друга?

Docker Compose создаёт внутреннюю сеть `manytask_default` для всех сервисов:

```yaml
# docker-compose.development.yml
services:
  manytask:
    container_name: test-manytask
    networks:
      - default

  gitlab:
    container_name: manytask_gitlab
    hostname: gitlab  # <-- Это имя доступно внутри сети
    networks:
      - default
```

**DNS резолюция:**
- Внутри сети контейнеры могут обращаться друг к другу по `hostname`
- `gitlab` → резолвится в IP адрес контейнера `manytask_gitlab`
- `postgres` → резолвится в IP адрес контейнера `manytask_postgres`

### Проброс портов

```yaml
gitlab:
  ports:
    - "8929:8929"  # хост:контейнер
```

- **Порт 8929 на хосте** → доступен из браузера как `localhost:8929`
- **Порт 8929 внутри контейнера** → доступен из других контейнеров как `gitlab:8929`

## Безопасность

### PKCE (Proof Key for Code Exchange)

PKCE защищает от атак перехвата `authorization_code`:

1. Manytask генерирует случайный `code_verifier`
2. Вычисляет `code_challenge = SHA256(code_verifier)`
3. Отправляет `code_challenge` в authorization request
4. При token exchange отправляет оригинальный `code_verifier`
5. GitLab проверяет, что `SHA256(code_verifier) == code_challenge`

### State parameter

Защита от CSRF атак:

1. Manytask генерирует случайный `state`
2. Сохраняет его в сессии
3. Отправляет в authorization request
4. GitLab возвращает тот же `state` в редиректе
5. Manytask проверяет, что `state` совпадает с сохранённым

### Client Secret

- `client_secret` хранится **только на сервере** (в `.env`)
- **Никогда не передаётся в браузер**
- Используется только в server-to-server запросах (token exchange)
- GitLab проверяет `client_secret` при выдаче `access_token`

## Дополнительные ресурсы

- [OAuth 2.0 RFC 6749](https://datatracker.ietf.org/doc/html/rfc6749)
- [PKCE RFC 7636](https://datatracker.ietf.org/doc/html/rfc7636)
- [OpenID Connect Core](https://openid.net/specs/openid-connect-core-1_0.html)
- [GitLab OAuth 2.0 Documentation](https://docs.gitlab.com/ee/api/oauth2.html)
- [Authlib Documentation](https://docs.authlib.org/en/latest/client/flask.html)

---

**Дата создания:** 2025-12-16
**Последнее обновление:** 2025-12-16
