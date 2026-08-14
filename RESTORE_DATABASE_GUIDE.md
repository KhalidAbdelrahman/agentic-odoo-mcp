# Restore the known-good Odoo database

This guide restores the current known-good Odoo/PostgreSQL state without re-running the seed script.

## Current known-good backup

The database backup was created from the live environment and saved here:

- `backups/agentic-crm-demo-known-good.sql`

The database name is:

- `agentic-crm-demo`

## 1) Confirm the environment is running

From the project root:

```bash
cd /Users/khalid/agentic-crm-demo

docker-compose ps
```

You should see both the Postgres container and the Odoo container as `Up`.

## 2) Stop Odoo before restoring

This avoids any write activity while the database is being reset:

```bash
docker-compose stop odoo
```

## 3) Drop and recreate the database

```bash
docker-compose exec -T db dropdb -U odoo --if-exists agentic-crm-demo
docker-compose exec -T db createdb -U odoo -O odoo agentic-crm-demo
```

## 4) Restore the backup file

```bash
docker-compose exec -T db psql -U odoo -d agentic-crm-demo < backups/agentic-crm-demo-known-good.sql
```

## 5) Restart Odoo

```bash
docker-compose start odoo
```

## 6) Verify the environment

Open:

```text
http://localhost:8069
```

Then log in using the standard Odoo credentials from the project:

- Database: `agentic-crm-demo`
- User: `admin@demo.locla`
- Password: `khalid12`

## Optional: create a fresh backup at any time

If you want to save the current state again later:

```bash
cd /Users/khalid/agentic-crm-demo
mkdir -p backups
docker-compose exec -T db pg_dump -U odoo -d agentic-crm-demo --clean --if-exists > backups/agentic-crm-demo-known-good.sql
```

## Notes

- This backup is intended as a quick restore point before rehearsals or interviews.
- It preserves the dataset as it exists right now without re-running `seed_demo_data.py`.
- If the Postgres container is restarted or the Odoo database is intentionally changed, rerun the backup command above to refresh the snapshot.
