# api-sql

API REST para subir documentos comprimidos a SharePoint (Microsoft Graph) e
iniciar el proceso de comparacion, y para actualizar el enlace resultante de
un documento en SQL Server.

## Stack

- **FastAPI** + **Uvicorn**
- **SQL Server 2022** (dockerizado para desarrollo)
- **pyodbc** para el acceso a datos
- **httpx** + **MSAL** para la subida a SharePoint vía Microsoft Graph (auth app-only con certificado)
- **pydantic-settings** para la configuración

## Estructura

```
app/
  config.py                    # Settings (pydantic-settings): lee y valida el .env
  db.py                        # get_cursor(): conexión + transacción + cierre por operación
  repository.py                # actualizar_documento(): acceso a la tabla documentos
  exceptions.py                # EntidadNoEncontrada, RepositorioExcepcion
  schemas.py                   # modelos de entrada (Pydantic)
  main.py                      # app FastAPI, router, auth por cabecera y logging
  adapters/
    sharepoint/
      auth.py                  # obtener_token(): token app-only de Graph, cacheado
      client.py                # subir_sharepoint(): sube el fichero a la biblioteca configurada
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
- Un registro de aplicación en Microsoft Entra ID con permiso app-only
  (`Sites.ReadWrite.All` o similar) sobre Microsoft Graph, autenticado con
  certificado (no se usa client secret).

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
python -m pip install -r requirements.txt
```

### 3. Configuración

```bash
copy .env.example .env       # en bash: cp .env.example .env
```

Edita `.env`:

| Variable          | Descripción                                    | Ejemplo                     |
|-------------------|-------------------------------------------------|-----------------------------|
| `DRIVER`          | Nombre del driver ODBC                         | `SQL Server`                |
| `SERVER`          | Host del servidor                              | `localhost`                 |
| `DATABASE`        | Base de datos                                  | `vendedores`                |
| `UID`             | Usuario                                        | `sa`                        |
| `PWD_SQL`         | Contraseña                                     | `YourStrong!Passw0rd`       |
| `API_TOKEN`       | Token para la cabecera `X-API-Key`             | *(ver abajo)*                |
| `TENANT_ID`       | Id del tenant de Microsoft Entra ID            | *(GUID)*                     |
| `CLIENT_ID`       | Id de la app registrada                        | *(GUID)*                     |
| `CERT_PATH`       | Ruta al certificado (clave privada, PEM)       | `certs/sharepoint.pem`       |
| `CERT_THUMBPRINT` | Huella del certificado subido a la app         | *(hex)*                      |
| `SHAREPOINT_URL`  | Ruta de la biblioteca destino. Opcional, tiene valor por defecto en `config.py` | `https://.../DesarrolloAutomatizaciones/Comentarios` |

Genera el token:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Si falta alguna variable obligatoria, la app no arranca y avisa de cuál falta.

### 4. Arrancar la API

```bash
uvicorn app.main:app --port 8090
```

- Documentación interactiva: http://127.0.0.1:8090/docs

## Endpoints

Todos requieren la cabecera `X-API-Key` con el valor de `API_TOKEN`.

### `POST /api/sharepoint`

Sube un fichero comprimido a la biblioteca de SharePoint configurada e inicia
el proceso de comparación. No toca la base de datos.

**Cabeceras**

| Cabecera        | Valor                       |
|-----------------|-----------------------------|
| `Content-Type`  | `multipart/form-data`       |
| `X-API-Key`     | el valor de `API_TOKEN`     |

**Cuerpo**: form-data con el campo `comprimido` (el fichero).

**Respuestas**

| Código | Cuándo                                              |
|--------|------------------------------------------------------|
| `204`  | Fichero subido correctamente                          |
| `400`  | Fichero vacío o supera el límite de 512 MB            |
| `401`  | Falta la cabecera `X-API-Key` o el token no coincide  |
| `422`  | Falta el fichero en el cuerpo de la petición          |
| `500`  | Error al subir a SharePoint (Graph/red)               |

**Ejemplo (curl / Git Bash)**

```bash
curl -i -X POST http://127.0.0.1:8090/api/sharepoint \
  -H "X-API-Key: <API_TOKEN>" \
  -F "comprimido=@documento.zip"
```

### `POST /api/links`

Actualiza el `sharepoint_link` de un documento existente en la base de datos
(normalmente, con el resultado del proceso iniciado por `/api/sharepoint`).

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
curl -i -X POST http://127.0.0.1:8090/api/links \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <API_TOKEN>" \
  -d '{"id": 1, "sharepoint_link": "https://sharepoint/doc1"}'
```

**Ejemplo (PowerShell)**

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8090/api/links `
  -Headers @{ "X-API-Key" = "<API_TOKEN>" } `
  -ContentType application/json `
  -Body '{"id": 1, "sharepoint_link": "https://sharepoint/doc1"}'
```

## Logging

Configurado en `main.py` a nivel `INFO`, formato `fecha nivel logger: mensaje`.

| Evento                              | Nivel     | Origen           |
|--------------------------------------|-----------|------------------|
| Documento actualizado                | `INFO`    | `app.repository` |
| Documento inexistente al actualizar  | `WARNING` | `app.repository` |
| Token inválido o ausente             | `WARNING` | `app.main`       |
| Error de base de datos               | `ERROR` (con traceback) | `app.repository` |
| Fichero inválido (vacío / demasiado grande) | `ERROR` (con traceback) | `app.main` |
| Error al subir a SharePoint          | `ERROR` (con traceback) | `app.main`       |

## Notas

- Cada petición a la base de datos abre y cierra su propia conexión; pyodbc
  reutiliza las del pool del driver ODBC, así que es seguro bajo carga concurrente.
- El cliente HTTP hacia Microsoft Graph (`app/adapters/sharepoint/client.py`) es un
  único `httpx.AsyncClient` compartido por todo el proceso, para reutilizar
  conexiones entre subidas en vez de abrir una nueva por petición.
- El token de Graph se cachea en memoria hasta que expira (`app/adapters/sharepoint/auth.py`);
  las peticiones concurrentes reutilizan el mismo token en vez de pedir uno cada una.
- En `/api/sharepoint`, el 400 solo se devuelve para `ArchivoInvalido` (fichero vacío
  o mayor de 512 MB) — cualquier otro fallo (config de MSAL, red, Graph caído) cae en
  el 500 genérico. Evita capturar `ValueError` a secas ahí: MSAL también lo usa para
  errores de configuración (p.ej. `TENANT_ID` mal puesto), y con `except ValueError`
  esos errores de servidor se devolvían como si fueran un 400 del cliente.
