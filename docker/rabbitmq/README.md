# RabbitMQ Local Dev Setup

## Start
```bash
docker compose up -d rabbitmq
```

## Verify health
```bash
poetry run python scripts/check_rabbitmq.py
```

## Management UI
http://localhost:15672  (user: clinicai / pass: clinicai_dev_pass)

## Topology
- Exchange `events.topic` (topic): main event routing
- Exchange `events.dlx` (fanout): dead letter
- Queue `events.audit` (TTL 7d): catch-all audit log
- Queue `events.dead_letter`: failed messages

## Reset (nuke data)
```bash
docker compose down rabbitmq
sudo rm -rf docker/rabbitmq/data docker/rabbitmq/log
docker compose up -d rabbitmq
```

## Persistence
Data + logs bind-mounted to `docker/rabbitmq/data/` and `docker/rabbitmq/log/`
(gitignored). Survives container restart, lost on `docker compose down -v`.
