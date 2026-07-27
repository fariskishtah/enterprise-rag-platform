# Deployment overview

Local development is intentionally open. The public AWS profile is a single-container,
single-instance demo behind Nginx and HTTPS.

```text
Internet :443 → Nginx/Certbot → 127.0.0.1:7860 → React + FastAPI
                                                ├── SQLite/data volume
                                                └── Hugging Face cache volume
```

Use [`aws-cpu-deployment.md`](aws-cpu-deployment.md) for the exact build, authentication,
DNS, firewall, HTTPS, backup, cleanup, rollback, snapshot, and monitoring procedure.

The release does not yet provide multi-tenant authorization, durable distributed jobs,
managed PostgreSQL/object storage, malware scanning, or independently scalable workers.
Those are explicit future boundaries, not claims about the public demo.
