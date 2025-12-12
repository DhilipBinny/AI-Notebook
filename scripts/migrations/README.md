# Database Migrations

This folder contains SQL migration scripts for updating the database schema.

## Migration Naming Convention

```
{number}_{description}.sql
```

- `number`: 3-digit sequential number (001, 002, etc.)
- `description`: Brief description using snake_case

## Running Migrations

### Option 1: Direct MySQL
```bash
mysql -u root -p ainotebook < scripts/migrations/002_add_audit_logs_status.sql
```

### Option 2: Via Docker
```bash
docker exec -i ainotebook-mysql mysql -u root -p"$MYSQL_ROOT_PASSWORD" ainotebook < scripts/migrations/002_add_audit_logs_status.sql
```

> **Note:** Set `MYSQL_ROOT_PASSWORD` environment variable or replace with your actual password.

## Migration History

| # | File | Description | Date |
|---|------|-------------|------|
| 001 | (initial schema) | Base schema in init-db.sql | 2024-12 |
| 002 | `002_add_audit_logs_status.sql` | Add status column to activity_logs | 2024-12-12 |

## Notes

- All migrations are idempotent (safe to run multiple times)
- Each migration includes a rollback comment at the top
- Test migrations in development before running in production
- The `init-db.sql` includes the latest schema for fresh installs
