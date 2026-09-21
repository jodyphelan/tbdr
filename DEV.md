# TBDR Docker development setup

Use the normal `docker-compose.yml` together with `docker-compose.dev.yml` while developing locally.

## Start the development stack

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

The development override bind-mounts the local repository at `/opt/tbdr` inside the `web` and `worker` containers.

### Web application changes

Gunicorn runs with `--reload`, so changes to Python source files are picked up automatically.

Templates and static files are also read directly from the local checkout because the repository is bind-mounted into the container.

### Celery worker changes

The worker sees local source changes immediately, but the running Celery process does not automatically reload them. Restart it after changing code used by Celery tasks:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart worker
```

## When to rebuild

You normally do **not** need to rebuild for changes to application Python, templates, JavaScript, or CSS.

Rebuild when you change dependencies or image-level configuration, for example:

- `environment.yml`
- `Dockerfile`
- TBProfiler/pathogen-profiler dependencies
- system packages

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

## Stop the stack

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
```

Persistent Postgres, Redis, uploads, and results volumes are still provided by the base Compose configuration.
