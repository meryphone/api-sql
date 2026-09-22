# api-sql

REST API to upload compressed documents to SharePoint (Microsoft Graph) and
start the comparison process, and to update the resulting link of a document
in SQL Server.

## Stack

- **FastAPI** + **Uvicorn**
- **SQL Server 2022** (dockerized for development)
- **pyodbc** for data access
- **httpx** + **MSAL** for uploading to SharePoint via Microsoft Graph (app-only auth with certificate)
- **pydantic-settings** for configuration

## Structure

```
app/
  config/
    settings.py                  # Settings (pydantic-settings): reads and validates the .env
    logging.yaml               # logging config passed to uvicorn with --log-config
  db.py                        # get_cursor(): connection + transaction + close per operation
  repository.py                # update_document(): access to the documentos table
  exceptions.py                # EntityNotFound, RepositoryError, InvalidFile, GraphError
  schemas.py                   # input models (Pydantic)
  main.py                      # FastAPI app, router and header auth
  adapters/
    sharepoint/
      auth.py                  # get_token(): app-only Graph token, cached
      client.py                # upload_to_sharepoint(): uploads the file to the configured library
docker-compose.yaml
requirements.txt
.env.example
```

## Prerequisites

- Python 3.11+
- Docker Desktop
- An ODBC driver for SQL Server. By default `SQL Server` is used (the one bundled with Windows).
  For the modern one, install [ODBC Driver 18 for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server)
  and adjust `DRIVER` in the `.env`.
- An application registration in Microsoft Entra ID with app-only permission
  (`Sites.ReadWrite.All` or similar) over Microsoft Graph, authenticated with
  a certificate (no client secret is used).

## Getting started

### 1. Database

> **Local development only.** The `docker-compose.yaml` spins up a SQL Server with
> a sample password and no hardening; it must not be used in production. In production
> the API points to a SQL Server managed separately, configured through the `.env`.

```bash
docker compose up -d
```

Brings up SQL Server at `localhost:1433` (user `sa`, password the one from `MSSQL_SA_PASSWORD`
in `docker-compose.yaml`). Create the database and the table:

```sql
CREATE DATABASE vendedores;
GO
USE vendedores;
GO
CREATE TABLE documentos (
    id              VARCHAR(50) PRIMARY KEY,
    sharepoint_link VARCHAR(500) NULL
);
```

### 2. Python environment

```bash
python -m venv venv
venv\Scripts\activate        # PowerShell/CMD;  in bash: source venv/bin/activate
python -m pip install -r requirements.txt
```

### 3. Configuration

```bash
copy .env.example .env       # in bash: cp .env.example .env
```

Edit `.env`:

| Variable          | Description                                     | Example                     |
|-------------------|-------------------------------------------------|-----------------------------|
| `DRIVER`          | ODBC driver name                                | `SQL Server`                |
| `SERVER`          | Server host                                     | `localhost`                 |
| `DATABASE`        | Database                                        | `vendedores`                |
| `UID`             | User                                            | `sa`                        |
| `PWD_SQL`         | Password                                        | `yourpassword`       |
| `API_TOKEN`       | Token for the `X-API-Key` header               | *(see below)*                |
| `TENANT_ID`       | Microsoft Entra ID tenant id                   | *(GUID)*                     |
| `CLIENT_ID`       | Registered app id                              | *(GUID)*                     |
| `CERT_PATH`       | Path to the certificate (private key, PEM)     | `certs/sharepoint.pem`       |
| `CERT_THUMBPRINT` | Thumbprint of the certificate uploaded to the app | *(hex)*                   |
| `SHAREPOINT_URL`  | URL of the SharePoint site                     | `https://<tenant>.sharepoint.com/sites/<site>` |
| `COMMENTS_LIBRARY`| Name of the target document library            | *(library name)*             |

Generate the token:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

If any required variable is missing, the app does not start and reports which one is missing.

### 4. Start the API

From the project root:

```bash
uvicorn app.main:app --reload --port 8090 --log-config app/config/logging.yaml
```

`--log-config` is required: without it Uvicorn uses its own logging setup and the
app's `INFO` lines are not printed. In production the service runs through
systemd with the unit in `deploy/api-sql.service` (same command, without `--reload`).

- Interactive docs: http://127.0.0.1:8090/docs

## Endpoints

All of them require the `X-API-Key` header with the value of `API_TOKEN`.

### `POST /api/sharepoint`

Uploads a compressed file to the configured SharePoint library and starts
the comparison process. It does not touch the database.

**Headers**

| Header          | Value                       |
|-----------------|-----------------------------|
| `Content-Type`  | `multipart/form-data`       |
| `X-API-Key`     | the value of `API_TOKEN`    |

**Body**: form-data with the `file` field (the file).

**Responses**

| Code   | When                                                 |
|--------|------------------------------------------------------|
| `204`  | File uploaded successfully                            |
| `400`  | Empty file or larger than the 512 MB limit           |
| `401`  | Missing `X-API-Key` header or token does not match   |
| `422`  | Missing file in the request body                     |
| `500`  | Error uploading to SharePoint (Graph/network)        |

**Example (curl / Git Bash)**

```bash
curl -i -X POST http://127.0.0.1:8090/api/sharepoint \
  -H "X-API-Key: <API_TOKEN>" \
  -F "file=@document.zip"
```

### `POST /api/links/{id}`

Updates the `sharepoint_link` of an existing document in the database
(normally with the result of the process started by `/api/sharepoint`).

**Path parameters**

| Parameter | Type  | Description                     |
|-----------|-------|--------------------------------|
| `id`      | `int` | Id of the document to update   |

**Headers**

| Header          | Value                       |
|-----------------|-----------------------------|
| `Content-Type`  | `application/json`          |
| `X-API-Key`     | the value of `API_TOKEN`    |

**Body**

```json
{
  "sharepoint_link": "https://sharepoint/doc1"
}
```

**Responses**

| Code   | When                                             |
|--------|--------------------------------------------------|
| `204`  | Document updated                                 |
| `401`  | Missing `X-API-Key` header or token does not match |
| `404`  | No document exists with that `id`                |
| `422`  | Invalid body (missing field or wrong type)       |
| `500`  | Database error                                   |

**Example (curl / Git Bash)**

```bash
curl -i -X POST http://127.0.0.1:8090/api/links/1 \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <API_TOKEN>" \
  -d '{"sharepoint_link": "https://sharepoint/doc1"}'
```

**Example (PowerShell)**

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8090/api/links/1 `
  -Headers @{ "X-API-Key" = "<API_TOKEN>" } `
  -ContentType application/json `
  -Body '{"sharepoint_link": "https://sharepoint/doc1"}'
```

## Logging

Defined in `app/config/logging.yaml` and applied by Uvicorn (`--log-config`) before
it starts, so every line, Uvicorn's included, uses the format
`date level logger: message` and goes to stdout. In production journald stores
the logs and deletes them after 7 days (`deploy/journald@api-sql.conf`). The line
already carries its date, so read it with `journalctl -o cat` to avoid seeing it twice:

```bash
journalctl --namespace=api-sql -u api-sql -o cat -f
```

Every module uses its own logger (`logging.getLogger(__name__)`). The level is `INFO`;
to see `DEBUG` lines while developing, change `root.level` in `logging.yaml` (without
committing it). `httpx`, `httpcore`, `msal`, `urllib3` and `asyncio` are limited to `WARNING`.

Each error is logged once, in `main.py`, where it is turned into an HTTP response.

| Event                                | Level     | Source           |
|--------------------------------------|-----------|------------------|
| Request received (method, path, status) | `INFO` | `uvicorn.access` |
| Document updated                     | `INFO`    | `app.repository` |
| File uploaded to SharePoint          | `INFO`    | `app.adapters.sharepoint.client` |
| Transient Graph error, retrying      | `WARNING` | `app.adapters.sharepoint.client` |
| Invalid or missing token             | `WARNING` | `app.main`       |
| Non-existent document on update      | `WARNING` | `app.main`       |
| Invalid file (empty / too large)     | `WARNING` | `app.main`       |
| Database error                       | `ERROR` (with traceback) | `app.main` |
| Error uploading to SharePoint        | `ERROR` (with traceback) | `app.main` |
| Graph token acquired / drive id resolved | `DEBUG` | `app.adapters.sharepoint.*` |
| SharePoint link of the updated document | `DEBUG` | `app.repository` |

## Notes

- Each database request opens and closes its own connection; pyodbc
  reuses those from the ODBC driver pool, so it is safe under concurrent load.
- The HTTP client towards Microsoft Graph (`app/adapters/sharepoint/client.py`) is a
  single `httpx.AsyncClient` shared by the whole process, to reuse
  connections between uploads instead of opening a new one per request.
- The Graph token is cached in memory until it expires (`app/adapters/sharepoint/auth.py`);
  concurrent requests reuse the same token instead of each requesting one.
- In `/api/sharepoint`, the 400 is only returned for `InvalidFile` (empty file
  or larger than 512 MB) — any other failure (MSAL config, network, Graph down) falls
  into the generic 500. Avoid catching a bare `ValueError` there: MSAL also uses it for
  configuration errors (e.g. a misconfigured `TENANT_ID`), and with `except ValueError`
  those server errors were returned as if they were a client 400.
