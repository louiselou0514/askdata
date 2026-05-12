from __future__ import annotations

import json
import uuid
import os

from fastapi import APIRouter, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep, TenantScopedRepository
from app.core.security import decrypt_config, encrypt_config
from app.models import DataSource
from app.services.llm import get_llm_provider
from app.services.schema_embeddings import refresh_embeddings

router = APIRouter(prefix="/data-sources", tags=["data-sources"])


class DataSourceResponse(BaseModel):
    id: uuid.UUID
    name: str
    source_type: str
    status: str


class ConnectSQLRequest(BaseModel):
    name: str
    source_type: str  # postgres | mysql
    host: str
    port: int = 5432
    dbname: str
    user: str
    password: str


class ConnectSheetsRequest(BaseModel):
    name: str
    spreadsheet_id: str
    oauth_token: dict


@router.get("/", response_model=list[DataSourceResponse])
async def list_data_sources(auth: CurrentUser, session: SessionDep) -> list[DataSourceResponse]:
    user, tenant = auth
    repo = TenantScopedRepository(session, tenant.id)
    sources = await repo.list(DataSource)
    return [DataSourceResponse(id=s.id, name=s.name, source_type=s.source_type, status=s.status)
            for s in sources]


@router.post("/csv", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def connect_csv(
    name: str,
    file: UploadFile,
    auth: CurrentUser,
    session: SessionDep,
) -> DataSourceResponse:
    user, tenant = auth
    file_bytes = await file.read()
    ds_id = uuid.uuid4()

    # Upload to Supabase Storage
    file_key = f"{tenant.id}/{ds_id}/{file.filename}"
    await _upload_to_storage(file_key, file_bytes)

    config = {"file_key": file_key, "file_name": file.filename}
    ds = DataSource(
        id=ds_id,
        tenant_id=tenant.id,
        name=name,
        source_type="csv",
        encrypted_config=encrypt_config(json.dumps(config)),
    )
    session.add(ds)
    await session.flush()

    llm = get_llm_provider()
    await refresh_embeddings(session, llm, ds, file_bytes=file_bytes)

    return DataSourceResponse(id=ds.id, name=ds.name, source_type=ds.source_type, status=ds.status)


@router.post("/sql", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def connect_sql(
    body: ConnectSQLRequest,
    auth: CurrentUser,
    session: SessionDep,
) -> DataSourceResponse:
    user, tenant = auth
    if body.source_type not in ("postgres", "mysql"):
        raise HTTPException(status_code=400, detail="source_type must be 'postgres' or 'mysql'")

    config = {
        "host": body.host,
        "port": body.port,
        "dbname": body.dbname,
        "user": body.user,
        "password": body.password,
    }

    # Test connectivity before saving
    from app.connectors.base import ConnectorFactory
    connector = ConnectorFactory.create(body.source_type, config)
    ok = await connector.test_connection()
    await connector.close()
    if not ok:
        raise HTTPException(status_code=400, detail="Could not connect to the database")

    ds = DataSource(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name=body.name,
        source_type=body.source_type,
        encrypted_config=encrypt_config(json.dumps(config)),
    )
    session.add(ds)
    await session.flush()

    llm = get_llm_provider()
    await refresh_embeddings(session, llm, ds)
    return DataSourceResponse(id=ds.id, name=ds.name, source_type=ds.source_type, status=ds.status)


@router.post("/sheets", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def connect_sheets(
    body: ConnectSheetsRequest,
    auth: CurrentUser,
    session: SessionDep,
) -> DataSourceResponse:
    user, tenant = auth
    config = {"spreadsheet_id": body.spreadsheet_id, "oauth_token": body.oauth_token}
    ds = DataSource(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name=body.name,
        source_type="google_sheets",
        encrypted_config=encrypt_config(json.dumps(config)),
    )
    session.add(ds)
    await session.flush()

    llm = get_llm_provider()
    await refresh_embeddings(session, llm, ds)
    return DataSourceResponse(id=ds.id, name=ds.name, source_type=ds.source_type, status=ds.status)


@router.get("/suggested-prompts")
async def suggested_prompts(
    ids: list[uuid.UUID] = Query(...),
    auth: CurrentUser = ...,
    session: SessionDep = ...,
) -> list[dict]:
    user, tenant = auth
    result = await session.execute(
        select(DataSource).where(
            DataSource.id.in_(ids),
            DataSource.tenant_id == tenant.id,
        )
    )
    sources = result.scalars().all()
    if not sources:
        return []

    # Build compact schema text for the LLM
    schema_lines: list[str] = []
    for ds in sources:
        cache = ds.schema_cache or {}
        for tbl in cache.get("tables", []):
            cols = ", ".join(c["name"] for c in tbl.get("columns", []))
            schema_lines.append(f'Table "{ds.name}": {cols}')
    schema_text = "\n".join(schema_lines)

    llm = get_llm_provider()
    system = (
        "You are a data analyst. Given database schemas, generate exactly 4 short, practical "
        "business questions a non-technical user would want answered. "
        "Return ONLY a JSON array — no markdown, no explanation — with exactly 4 objects: "
        '[{"label":"2-4 word title","question":"Natural language question?","icon":"single emoji"}]. '
        "Pick relevant emojis from: 📈 📊 🏆 🔍 📦 👥 💰 📅 🗺️ ⚡ 🏠 🤝 📋 🔄 🎯"
    )
    user_msg = f"Schemas:\n{schema_text}"
    try:
        resp = await llm.complete(system=system, user=user_msg)
        import json as _json
        raw = resp.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        prompts = _json.loads(raw.strip())
        if isinstance(prompts, list):
            return prompts[:4]
    except Exception:
        pass
    return []


@router.delete("/{ds_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_data_source(ds_id: uuid.UUID, auth: CurrentUser, session: SessionDep) -> None:
    user, tenant = auth
    repo = TenantScopedRepository(session, tenant.id)
    ds = await repo.require(DataSource, ds_id)
    if ds.source_type == "csv":
        try:
            config = json.loads(decrypt_config(ds.encrypted_config))
            await _delete_from_storage(config["file_key"])
        except Exception:
            pass
    await session.delete(ds)
    await session.commit()


async def _delete_from_storage(file_key: str) -> None:
    from supabase import acreate_client
    client = await acreate_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    bucket = os.environ.get("SUPABASE_STORAGE_BUCKET", "csv-uploads")
    await client.storage.from_(bucket).remove([file_key])


async def _upload_to_storage(file_key: str, data: bytes) -> None:
    from supabase import acreate_client
    client = await acreate_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    bucket = os.environ.get("SUPABASE_STORAGE_BUCKET", "csv-uploads")
    await client.storage.from_(bucket).upload(file_key, data)
