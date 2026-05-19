## старт

```bash
cp .env.example .env
docker compose up -d
```
```bash
docker compose run --rm etl python export_to_minio.py
docker compose run --rm etl python build_marts.py
```
## Доступ к сервисам

| Jupyter | http://localhost:8888 | Token: `oilhomework`|
| MinIO Console | http://localhost:9001 | `minioadmin` / `minioadmin` |
| Superset | http://localhost:8088 | `admin` / `admin` |
| PostgreSQL | `localhost:5432` | `oiluser` / `oilpass`, БД `oildb` |
