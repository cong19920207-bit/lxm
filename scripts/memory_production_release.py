"""Opt-in production S15 with old vectors retained and no body/log backup.

Default action is read-only preview. Bootstrap creates only an inactive fence;
apply/open require the exact persisted manifest, run and external seal evidence.
Run in a dedicated maintenance environment, never from application startup.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path


def read_json(path):
    return json.loads(Path(path).read_text())


async def run(args):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    import backend.models
    from backend.config import get_mysql_url, get_redis_url
    from backend.models.memory_control import MemoryRuntimeFence
    from backend.services.memory_effective_config import resolve_effective_memory_config
    from backend.services.memory_runtime_service import MemoryControlError
    from backend.services.memory_production_release import (
        ProductionResetService, NoBackupContainerTransition, RemovedContainerArtifacts,
        readonly_dashvector_adapter,
    )
    from backend.services.memory_reset_resources import RedisResetAdapter

    cfg = read_json(args.config)
    environment = cfg["environment_id"]
    if not environment or environment != os.getenv("MEMORY_RUNTIME_ENVIRONMENT_ID", "").strip():
        raise MemoryControlError(20127, "production_environment_mismatch")
    url = os.environ[cfg["database_url_env"]] if cfg.get("database_url_env") else get_mysql_url()
    engine = create_async_engine(url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    close = []
    try:
        if args.action in {"info", "bootstrap"}:
            async with sessions() as db:
                effective = await resolve_effective_memory_config(db)
                fingerprint = bytes.fromhex(effective.target_fingerprint)
                if cfg.get("target_fingerprint") and cfg["target_fingerprint"] != fingerprint.hex():
                    raise MemoryControlError(20127, "explicit_target_mismatch")
                if args.action == "bootstrap":
                    if not cfg.get("target_fingerprint"):
                        raise ValueError("explicit_target_required")
                    db.info["s15_maintenance"] = "production-fence-bootstrap"
                    fence = await db.get(MemoryRuntimeFence, environment)
                    if fence is None:
                        db.add(MemoryRuntimeFence(environment_id=environment, target_epoch=1,
                                                  target_fingerprint=fingerprint, mode="maintenance"))
                        await db.commit()
                    elif fence.target_fingerprint != fingerprint or fence.mode != "maintenance" or fence.reset_run_id:
                        raise MemoryControlError(20127, "existing_fence_requires_original_run")
                return {"environment_id": environment, "target_fingerprint": fingerprint.hex(),
                        "providers": {key: value.public() for key, value in effective.providers.items()},
                        "action": args.action, "activated": False}
        target = bytes.fromhex(cfg["target_fingerprint"])
        adapters = {}
        docker = NoBackupContainerTransition()
        for name, definition in cfg["adapters"].items():
            spec = dict(definition)
            kind = spec.pop("kind")
            if kind == "vector_readonly":
                spec["endpoint"] = os.environ[spec.pop("endpoint_env")]
                spec["credential"] = os.environ[spec.pop("credential_env")]
                adapters[name] = readonly_dashvector_adapter(**spec)
            elif kind == "redis":
                from redis.asyncio import Redis
                url_env = spec.pop("url_env", None)
                client = Redis.from_url(os.environ[url_env] if url_env else get_redis_url())
                close.append(client.aclose)
                adapters[name] = RedisResetAdapter(client, **spec)
            elif kind == "container_no_backup":
                if spec:
                    raise ValueError("unexpected_container_settings")
                adapters[name] = docker
            elif kind == "removed_container_artifacts":
                adapters[name] = RemovedContainerArtifacts(docker, spec["container_target"])
            else:
                raise ValueError("production_adapter_not_allowlisted")
        runner = ProductionResetService(sessions, environment, target, adapters=adapters)
        if args.action == "read":
            if not args.run_id:
                raise ValueError("run_id_required")
            return await runner.read(args.run_id)
        if args.action == "preview":
            return await runner.preview(resources=cfg["resources"])
        if not args.manifest or not args.authorization:
            raise ValueError("manifest_and_authorization_required")
        manifest, auth = read_json(args.manifest), read_json(args.authorization)
        if manifest["resources"] != cfg["resources"]:
            raise MemoryControlError(20127, "configured_resources_changed")
        runner._authorize(manifest, auth)
        if args.action == "apply":
            return await runner.execute(manifest, auth)
        if args.action == "open":
            return await runner.open(auth["run_id"], auth)
        raise ValueError("invalid_action")
    finally:
        for callback in close:
            await callback()
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--action", choices=["info", "bootstrap", "preview", "read", "apply", "open"], default="preview")
    for key in ("output", "manifest", "authorization", "run-id"):
        parser.add_argument("--" + key)
    args = parser.parse_args()
    try:
        result = asyncio.run(run(args))
    except Exception as error:
        from backend.services.memory_runtime_service import MemoryControlError
        print(json.dumps({"ok": False, "reason": error.reason if isinstance(error, MemoryControlError) else type(error).__name__}))
        return 1
    body = json.dumps(result, ensure_ascii=False, indent=2, default=lambda value: value.isoformat()) + "\n"
    if args.output:
        fd = os.open(args.output, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as output:
            output.write(body)
    else:
        print(body, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
