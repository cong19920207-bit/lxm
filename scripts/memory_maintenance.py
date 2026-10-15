"""Explicit STEP-008 command. No app startup hook; reset defaults to preview.

Examples (paths contain no credentials; values come from named environment vars):
 python -m scripts.memory_maintenance reset --config /secure/s15.json --output /secure/manifest.json
 python -m scripts.memory_maintenance reset --action apply --config /secure/s15.json --manifest /secure/manifest.json --authorization /secure/auth.json
 python -m scripts.memory_maintenance backfill --action create --config /secure/backfill.json --baseline /secure/baseline.json

Reset config: database_url_env, environment_id, target_fingerprint, adapters,
resources. Adapter definitions have kind redis/logs/container/local_objects/vector
and explicit targets matching the preview manifest. Redis uses url_env plus
database_identity/namespace; vector uses endpoint/credential_env/collection/partition;
logs use online_root/archive_root, local_objects root, container archive_root (private offline directory) and optional config_override_path
(private 0600 JSON Config overrides; parent 0700). Container targets include
container_id/new_name/image/command/readonly_mounts/log_paths/config_override_digest;
only the digest enters the manifest, never Env values. apply automatically
terminates durable never-dispatched jobs before taking the T0 baseline.
Backfill config: database_url_env, environment_id, target_fingerprint, partitions.
The published provider and local BM25 are resolved once and recorded per run.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path


def read(path):return json.loads(Path(path).read_text())

def parser():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('command',choices=['reset','backfill'])
    p.add_argument('--action',default=None)
    p.add_argument('--config',required=True)
    for name in ['output','manifest','authorization','baseline','run-id','operation-id']:p.add_argument('--'+name)
    p.add_argument('--after',type=int,default=0);p.add_argument('--limit',type=int,default=100)
    p.add_argument('--rate',type=float,default=20);p.add_argument('--max-items',type=int)
    return p


async def run(args):
    from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
    import backend.models
    from backend.services.memory_runtime_service import MemoryControlError
    cfg=read(args.config)
    engine=create_async_engine(os.environ[cfg['database_url_env']],pool_pre_ping=True)
    sessions=async_sessionmaker(engine,expire_on_commit=False);close=[]
    try:
        if args.command=='backfill':
            from backend.services.memory_effective_config import resolve_active_memory_config
            from backend.services.memory_bm25 import get_encoder
            from backend.services.memory_provider_service import embedding
            from backend.utils.memory_vector_client import MemoryVectorClient
            from backend.services.memory_backfill_service import MemoryBackfillService
            async with sessions() as db:config=await resolve_active_memory_config(db,cfg['environment_id'],allow_isolated=cfg['environment_id'].startswith('isolated:'))
            if config.target_fingerprint!=cfg['target_fingerprint']:raise MemoryControlError(20127,'explicit_target_mismatch')
            provider=config.providers['embedding']
            async def embed(value):return (await embedding(provider,[value],'document'))[0]
            version=provider.public()
            runner=MemoryBackfillService(sessions,MemoryVectorClient(config.providers['dashvector']),get_encoder(),embed,
                cfg['environment_id'],config.target_epoch,bytes.fromhex(config.target_fingerprint),
                provider_version=f"{version['profile_fingerprint']}:{provider.version}:{provider.revision}",
                allow_isolated=cfg['environment_id'].startswith('isolated:'))
            action=args.action or 'read'
            if action=='create':
                if not args.baseline:raise ValueError('baseline_required')
                return await runner.create(partitions=cfg['partitions'],baseline=read(args.baseline),
                    mode='isolated' if cfg['environment_id'].startswith('isolated:') else 'actual',run_id=args.run_id)
            if not args.run_id:raise ValueError('run_id_required')
            if action=='resume':return await runner.resume(args.run_id,max_items=args.max_items,rate_per_second=args.rate)
            if action=='read':return await runner.read(args.run_id)
            if action=='items':return await runner.items(args.run_id,after=args.after,limit=args.limit)
            raise ValueError('invalid_backfill_action')
        from backend.services.memory_reset_service import MemoryResetService
        from backend.services.memory_reset_resources import (RedisResetAdapter,FileArchiveAdapter,DockerResetAdapter,
            LocalObjectsResetAdapter,dashvector_reset_adapter)
        adapters={}
        for name,spec in cfg.get('adapters',{}).items():
            spec=dict(spec);kind=spec.pop('kind')
            if kind=='redis':
                from redis.asyncio import Redis
                client=Redis.from_url(os.environ[spec.pop('url_env')]);close.append(client.aclose)
                adapters[name]=RedisResetAdapter(client,**spec)
            elif kind=='logs':adapters[name]=FileArchiveAdapter(**spec)
            elif kind=='container':
                adapters[name]=DockerResetAdapter(**spec)
            elif kind=='local_objects':adapters[name]=LocalObjectsResetAdapter(**spec)
            elif kind=='vector':
                spec['credential']=os.environ[spec.pop('credential_env')]
                adapters[name]=dashvector_reset_adapter(**spec)
            else:raise ValueError('unverified_adapter_kind')
        runner=MemoryResetService(sessions,cfg['environment_id'],bytes.fromhex(cfg['target_fingerprint']),adapters=adapters)
        action=args.action or 'preview'
        if action=='preview':return await runner.preview(resources=cfg.get('resources',[]))
        if action=='read':return await runner.read(args.run_id)
        if not args.manifest or not args.authorization:raise ValueError('manifest_and_authorization_required')
        manifest,auth=read(args.manifest),read(args.authorization)
        if manifest['resources']!=cfg.get('resources',[]):raise ValueError('configured_resources_changed')
        if action=='apply':return await runner.execute(manifest,auth)
        if action=='reconcile-source':
            from backend.services.memory_effective_config import resolve_effective_memory_config
            from backend.utils.memory_vector_client import MemoryVectorClient
            from backend.services.memory_reset_drain import MemoryResetDrainer
            if not args.operation_id:raise ValueError('operation_id_required')
            async with sessions() as db:config=await resolve_effective_memory_config(db)
            if config.target_fingerprint!=cfg['target_fingerprint']:raise ValueError('source_target_changed')
            return await MemoryResetDrainer(runner).reconcile_operation(manifest,auth,operation_id=args.operation_id,
                remote=MemoryVectorClient(config.providers['dashvector']))

        if action=='open':
            runner._authorize(manifest,auth)
            return await runner.open(auth['run_id'],auth)
        raise ValueError('invalid_reset_action')
    finally:
        for fn in close:await fn()
        await engine.dispose()


def main():
    args=parser().parse_args()
    try:result=asyncio.run(run(args))
    except Exception as error:
        # Never print connection URLs, provider response bodies or credentials.
        from backend.services.memory_runtime_service import MemoryControlError
        result={'ok':False,'reason':error.reason if isinstance(error,MemoryControlError) else type(error).__name__}
        print(json.dumps(result));return 1
    content=json.dumps(result,ensure_ascii=False,indent=2,default=lambda x:x.isoformat())
    if args.output:
        fd=os.open(args.output,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w') as stream:stream.write(content+'\n')
    else:print(content)
    return 0

if __name__=='__main__':raise SystemExit(main())
