# api-sql

API REST para actualizar el enlace de SharePoint de documentos almacenados en SQL Server.

## Stack

- **FastAPI** + **Uvicorn**
- **SQL Server 2022** (dockerizado para desarrollo)
- **pyodbc** para el acceso a datos
- **pydantic-settings** para la configuración

## Estructura

```
app/
  config.py       # Settings (pydantic-settings): lee y valida el .env
  db.py           # get_cursor(): conexión + transacción + cierre por operación
  repository.py   # actualizar_documento(): acceso a la tabla documentos
  exceptions.py   # EntidadNoEncontrada, RepositorioExcepcion
  schemas.py      # modelos de entrada (Pydantic)
  main.py         # app FastAPI, router, auth por cabecera y logging
docker-compose.yaml
requirements.txt
.env.example
```

## Requisitos previos

- Python 3.11+
- Docker Desktop
- Un driver ODBC para SQL Server. Por defecto se usa `SQL Server` (el que trae Windows).
  Para el moderno instala [ODBC Driver 18 for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server)
  y ajusta `DRIVER` en el `.env`.

## Puesta en marcha

### 1. Base de datos

> **Solo para desarrollo local.** El `docker-compose.yaml` monta un SQL Server con
> contraseña de ejemplo y sin endurecer; no debe usarse en producción. En producción
> la API apunta a un SQL Server gestionado aparte, configurado mediante el `.env`.

```bash
docker compose up -d
```

Levanta SQL Server en `localhost:1433` (usuario `sa`, contraseña la de `MSSQL_SA_PASSWORD`
en `docker-compose.yaml`). Crea la base de datos y la tabla:

```sql
CREATE DATABASE vendedores;
GO
USE vendedores;
GO
CREATE TABLE documentos (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    sharepoint_link VARCHAR(500) NULL
);
```

### 2. Entorno Python

```bash
python -m venv venv
venv\Scripts\activate        # PowerShell/CMD;  en bash: source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configuración

```bash
copy .env.example .env       # en bash: cp .env.example .env
```

Edita `.env`:

| Variable    | Descripción                          | Ejemplo                     |
|-------------|--------------------------------------|-----------------------------|
| `DRIVER`    | Nombre del driver ODBC               | `SQL Server`                |
| `SERVER`    | Host del servidor                    | `localhost`                 |
| `DATABASE`  | Base de datos                        | `vendedores`                |
| `UID`       | Usuario                              | `sa`                        |
| `PWD_SQL`   | Contraseña                           | `YourStrong!Passw0rd`       |
| `API_TOKEN` | Token para la cabecera `X-API-Key`   | *(ver abajo)*               |

Genera el token:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Si falta alguna variable, la app no arranca y avisa de cuál falta.

### 4. Arrancar la API

```bash
uvicorn app.main:app --port 8090
```

- Documentación interactiva: http://127.0.0.1:8080/docs

## Endpoint

### `POST /api/documentos`

Actualiza el `sharepoint_link` de un documento existente.

**Cabeceras**

| Cabecera        | Valor                       |
|-----------------|-----------------------------|
| `Content-Type`  | `application/json`          |
| `X-API-Key`     | el valor de `API_TOKEN`     |

**Cuerpo**

```json
{
  "id": 1,
  "sharepoint_link": "https://sharepoint/doc1"
}
```

**Respuestas**

| Código | Cuándo                                            |
|--------|--------------------------------------------------|
| `204`  | Documento actualizado                             |
| `401`  | Falta la cabecera `X-API-Key` o el token no coincide |
| `404`  | No existe ningún documento con ese `id`           |
| `422`  | Cuerpo inválido (falta un campo o tipo incorrecto) |
| `500`  | Error de base de datos                            |

**Ejemplo (curl / Git Bash)**

```bash
curl -i -X POST http://127.0.0.1:8080/api/documentos \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <API_TOKEN>" \
  -d '{"id": 1, "sharepoint_link": "https://sharepoint/doc1"}'
```

**Ejemplo (PowerShell)**

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/api/documentos `
  -Headers @{ "X-API-Key" = "<API_TOKEN>" } `
  -ContentType application/json `
  -Body '{"id": 1, "sharepoint_link": "https://sharepoint/doc1"}'
```

## Logging

Configurado en `main.py` a nivel `INFO`, formato `fecha nivel logger: mensaje`.

| Evento                          | Nivel     | Origen           |
|---------------------------------|-----------|------------------|
| Documento actualizado           | `INFO`    | `app.repository` |
| Documento inexistente al actualizar | `WARNING` | `app.repository` |
| Token inválido o ausente        | `WARNING` | `app.main`       |
| Error de base de datos          | `ERROR` (con traceback) | `app.repository` |

## Notas

- Cada petición abre y cierra su propia conexión; pyodbc reutiliza las del pool del
  driver ODBC, así que es seguro bajo carga concurrente.
