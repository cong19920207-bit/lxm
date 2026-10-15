"""Exact-resource S15 adapters; uncertain commands are reconciled, never resent."""
import asyncio
import hashlib
import json
import os
import re
from pathlib import Path
from backend.services.memory_reset_policy import redis_action
from backend.services.memory_reset_service import digest
from backend.services.memory_runtime_service import MemoryControlError


class RedisResetAdapter:
    def __init__(self,client,*,database_identity,namespace=''):
        self.client,self.identity,self.namespace=client,database_identity,namespace

    def _target(self,target):
        if target!={'database_identity':self.identity,'namespace':self.namespace}:raise MemoryControlError(20127,'redis_target_mismatch')

    async def prepare(self,target,run_id):
        self._target(target);items=[]
        async for raw in self.client.scan_iter(match=self.namespace+'*'):
            key=raw.decode() if isinstance(raw,bytes) else raw
            logical=key[len(self.namespace):]
            if redis_action(logical)!='delete':continue
            data=await self.client.dump(key)
            if data is None:raise MemoryControlError(20126,'redis_baseline_changed')
            typ=await self.client.type(key);typ=typ.decode() if isinstance(typ,bytes) else typ
            if typ not in {'string','list','set','zset','hash'}:raise MemoryControlError(20126,'redis_type_unverified')
            command={'string':'strlen','list':'llen','set':'scard','zset':'zcard','hash':'hlen'}[typ]
            count=await getattr(self.client,command)(key)
            items.append({'key':key,'type':typ,'count':count,'dump_sha1':hashlib.sha1(data).hexdigest()})
        return {'items':sorted(items,key=lambda r:r['key']),'marker':self.namespace+'memory:s15:'+run_id}

    async def execute(self,target,scope,run_id):
        self._target(target)
        # Lua freezes comparison+deletion+receipt atomically on the same Redis
        # instance. Lost responses can be verified by the original marker.
        script="""
        if redis.call('GET',KEYS[1]) == ARGV[1] then return 1 end
        for i=2,#KEYS do
          local value=redis.call('DUMP',KEYS[i])
          if not value or redis.sha1hex(value) ~= ARGV[i] then return -1 end
        end
        for i=2,#KEYS do redis.call('DEL',KEYS[i]) end
        redis.call('SET',KEYS[1],ARGV[1])
        return 1
        """
        keys=[scope['marker']]+[r['key'] for r in scope['items']]
        args=[digest(scope).hex()]+[r['dump_sha1'] for r in scope['items']]
        result=await self.client.eval(script,len(keys),*keys,*args)
        if result!=1:raise MemoryControlError(20126,'redis_t0_changed')
        return await self.reconcile(target,scope,run_id)

    async def reconcile(self,target,scope,run_id):
        self._target(target);marker=await self.client.get(scope['marker'])
        if isinstance(marker,bytes):marker=marker.decode()
        confirmed=marker==digest(scope).hex() and not any([await self.client.exists(r['key']) for r in scope['items']])
        return {'state':'confirmed' if confirmed else 'unknown','count':len(scope['items'])}


class FileArchiveAdapter:
    def __init__(self,*,online_root,archive_root):
        self.online=Path(online_root).resolve();self.archive=Path(archive_root).resolve()
        if self.online==self.archive or self.online in self.archive.parents:raise ValueError('archive_must_be_offline')

    def _paths(self,target):
        if set(target)!={'paths'}:raise ValueError('exact_file_paths_required')
        paths=[]
        for value in target['paths']:
            p=Path(value)
            if p.is_symlink() or not p.is_absolute() or self.online not in p.resolve().parents:
                raise MemoryControlError(20127,'file_target_mismatch')
            if p.name not in {'system.log','error.log'} and not p.name.startswith(('system.log.','error.log.')):
                raise MemoryControlError(20126,'log_path_not_allowlisted')
            paths.append(p)
        return paths

    async def prepare(self,target,run_id):
        records=[]
        for p in self._paths(target):
            st=p.stat();records.append({'path':str(p),'inode':st.st_ino,'device':st.st_dev,'size':st.st_size,
                'digest':hashlib.sha256(p.read_bytes()).hexdigest(),'archive':str(self.archive/run_id/p.name)})
        return {'files':records,'mixed_nonbody_logs_archived':True}

    async def execute(self,target,scope,run_id):
        self._paths(target)
        destination=self.archive/run_id;destination.mkdir(mode=0o700,parents=True,exist_ok=True)
        for record in scope['files']:
            source=Path(record['path']);target_path=Path(record['archive'])
            if target_path.exists():
                if source.exists():raise MemoryControlError(20126,'archive_collision')
                continue
            st=source.stat()
            if (st.st_ino!=record['inode'] or st.st_dev!=record['device'] or st.st_size!=record['size']
                    or hashlib.sha256(source.read_bytes()).hexdigest()!=record['digest']):raise MemoryControlError(20126,'log_t0_changed')
            os.rename(source,target_path);target_path.chmod(0o600)
        return await self.reconcile(target,scope,run_id)

    async def reconcile(self,target,scope,run_id):
        self._paths(target)
        ok=all(not Path(r['path']).exists() and Path(r['archive']).is_file()
            and hashlib.sha256(Path(r['archive']).read_bytes()).hexdigest()==r['digest'] for r in scope['files'])
        return {'state':'confirmed' if ok else 'unknown','mixed_nonbody_logs_archived':True}


class DockerResetAdapter:
    """Exact stopped ID, protected offline config/logs, equivalent create only.

    Config (including Env) is never returned or persisted in SQL. The private
    material must be retained for same-run recovery after removal of the old ID.
    """
    def __init__(self,*,archive_root,config_override_path=None):
        self.config_override_path=Path(config_override_path) if config_override_path else None
        self.archive=Path(archive_root)
        if not self.archive.is_absolute() or self.archive.is_symlink():raise ValueError('private_archive_required')
        self.archive.mkdir(mode=0o700,parents=True,exist_ok=True)
        if self.archive.stat().st_mode & 0o077:raise ValueError('private_archive_permissions_required')

    async def _docker(self,*args):
        p=await asyncio.create_subprocess_exec('docker',*args,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        stdout,_=await asyncio.wait_for(p.communicate(),30)
        if p.returncode:raise MemoryControlError(20129,'docker_command_failed')
        return stdout.decode().strip()

    async def _inspect(self,identity):
        try:return json.loads(await self._docker('inspect',identity))[0]
        except MemoryControlError:return None

    def _directory(self,run_id):
        from uuid import UUID
        if str(UUID(run_id))!=run_id:raise ValueError('canonical_run_id_required')
        directory=self.archive/run_id
        if directory.is_symlink():raise ValueError('private_archive_required')
        directory.mkdir(mode=0o700,exist_ok=True)
        if directory.stat().st_mode & 0o077:raise ValueError('private_archive_permissions_required')
        return directory

    @staticmethod
    def _mounts(old):
        mounts=[]
        for m in old['Mounts']:
            if m['Type']!='bind' or m['RW']:raise MemoryControlError(20126,'container_mount_preservation_unverified')
            mounts.append({'source':m['Source'],'destination':m['Destination'],'read_only':True})
        return sorted(mounts,key=lambda m:m['destination'])

    @staticmethod
    def _config(old,target,run_id):
        config=json.loads(json.dumps(old['Config']))
        config.update(Image=target['image'],Cmd=target['command'])
        if config.get('Env') is not None:config['Env']=sorted(config['Env'])
        config['Labels']={**(config.get('Labels') or {}),'memory.s15.run':run_id}
        host=json.loads(json.dumps(old['HostConfig']));host['OomKillDisable']=bool(host.get('OomKillDisable'));host['RestartPolicy']={'Name':'no','MaximumRetryCount':0}
        # Engine-generated endpoint identities/addresses must not be reused.
        networks={name:{k:v for k,v in endpoint.items() if k in {'IPAMConfig','Links','Aliases','DriverOpts','MacAddress'} and v is not None}
            for name,endpoint in old['NetworkSettings']['Networks'].items()}
        for endpoint in networks.values():
            if 'Aliases' in endpoint:endpoint['Aliases']=[v for v in endpoint['Aliases'] if v not in {old['Id'][:12],old['Name'].lstrip('/')}]
            endpoint.pop('MacAddress',None) # Assigned by daemon, not static configuration.
        return {**config,'HostConfig':host,'NetworkingConfig':{'EndpointsConfig':networks}}

    def _load(self,scope,run_id):
        path=self._directory(run_id)/'recreate.json'
        if path.is_symlink() or path.stat().st_mode & 0o077:raise MemoryControlError(20126,'container_material_unprotected')
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=scope['material_digest']:raise MemoryControlError(20126,'container_material_changed')
        return json.loads(data)

    @staticmethod
    def _private_write(path,data):
        if path.is_symlink():raise MemoryControlError(20126,'archive_collision')
        if path.exists():
            if path.stat().st_mode & 0o077 or path.read_bytes()!=data:raise MemoryControlError(20126,'archive_collision')
            return
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'wb') as f:f.write(data)

    async def prepare(self,target,run_id):
        if (set(target)!={'container_id','new_name','image','command','readonly_mounts','log_paths','config_override_digest'}
                or not __import__('re').fullmatch('[0-9a-f]{64}',target['container_id'])):
            raise ValueError('exact_container_manifest_required')
        old=await self._inspect(target['container_id'])
        if not old or old['Id']!=target['container_id'] or old['State']['Running'] or old['HostConfig']['RestartPolicy']['Name'] not in {'no',''}:
            raise MemoryControlError(20126,'container_not_sealed')
        mounts=self._mounts(old)
        if mounts!=sorted(target['readonly_mounts'],key=lambda m:m['destination']):raise MemoryControlError(20126,'container_mount_manifest_mismatch')
        if not target['image'].startswith('sha256:'):raise ValueError('frozen_image_id_required')
        if await self._inspect(target['new_name']):raise MemoryControlError(20126,'container_name_collision')
        directory=self._directory(run_id)
        override={}
        if self.config_override_path:
            path=self.config_override_path
            if (not path.is_absolute() or path.is_symlink() or path.stat().st_mode & 0o077
                    or path.parent.stat().st_mode & 0o077):raise ValueError('private_override_required')
            data=path.read_bytes()
            if hashlib.sha256(data).hexdigest()!=target['config_override_digest']:raise ValueError('override_digest_mismatch')
            override=json.loads(data)
            if not isinstance(override,dict) or set(override)-{'Env','Entrypoint','User','WorkingDir','Healthcheck','ExposedPorts'}:
                raise ValueError('invalid_target_config_override')
        elif target['config_override_digest'] is not None:raise ValueError('protected_config_override_required')
        if any(Path(m['source']).resolve()==self.archive.resolve() or Path(m['source']).resolve() in self.archive.resolve().parents for m in mounts):
            raise MemoryControlError(20126,'archive_visible_to_application')
        # Enumerate the exact stopped container layer. An omitted rotated log
        # must fail before rm; archive every known system/error log in that root.
        log_data={}
        if not target['log_paths']:raise ValueError('complete_container_log_manifest_required')
        if target['log_paths']:
            import io,tarfile
            p=await asyncio.create_subprocess_exec('docker','cp',old['Id']+':/app/logs/.','-',stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
            raw,_=await asyncio.wait_for(p.communicate(),30)
            if p.returncode:raise MemoryControlError(20126,'container_log_inventory_unverified')
            with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
                for member in archive.getmembers():
                    name=member.name.removeprefix('./')
                    if member.isdir():continue
                    if (not member.isfile() or '/' in name or name not in {'system.log','error.log'}
                            and not name.startswith(('system.log.','error.log.'))):raise MemoryControlError(20126,'container_log_inventory_unverified')
                    log_data['/app/logs/'+name]=archive.extractfile(member).read()
            if set(log_data)!=set(target['log_paths']):raise MemoryControlError(20126,'container_log_inventory_changed')
        logs=[]
        for value in target['log_paths']:
            p=Path(value)
            if (str(p)!=value or p.parent!=Path('/app/logs') or p.name not in {'system.log','error.log'}
                    and not p.name.startswith(('system.log.','error.log.'))):raise ValueError('container_log_not_allowlisted')
            if any(str(p)==m['destination'] or str(p).startswith(m['destination'].rstrip('/')+'/') for m in mounts):
                raise MemoryControlError(20126,'container_log_mount_unverified')
            data=log_data[value];self._private_write(directory/p.name,data)
            logs.append({'name':p.name,'digest':hashlib.sha256(data).hexdigest()})
        # Daemon logs may also contain body text. Archive before docker rm.
        daemon=directory/'daemon.log'
        p=await asyncio.create_subprocess_exec('docker','logs',old['Id'],stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        stdout,stderr=await asyncio.wait_for(p.communicate(),30)
        if p.returncode:raise MemoryControlError(20126,'daemon_log_archive_unverified')
        self._private_write(daemon,stdout+stderr)
        logs.append({'name':daemon.name,'digest':hashlib.sha256(daemon.read_bytes()).hexdigest()})
        material=self._config(old,target,run_id);material.update(override)
        if 'Env' in override:
            image=json.loads(await self._docker('image','inspect',target['image']))[0]
            env={v.split('=',1)[0]:v for v in image['Config'].get('Env') or []}
            if not isinstance(override['Env'],list) or any(not isinstance(v,str) or '=' not in v for v in override['Env']):raise ValueError('invalid_target_environment')
            if len({v.split('=',1)[0] for v in override['Env']})!=len(override['Env']):raise ValueError('duplicate_target_environment')
            env.update({v.split('=',1)[0]:v for v in override['Env']});material['Env']=sorted(env.values())
        data=json.dumps(material,sort_keys=True,separators=(',',':')).encode()
        path=directory/'recreate.json';self._private_write(path,data)
        return {'old_id':old['Id'],'old_config_digest':digest({'config':old['Config'],'host':old['HostConfig'],'mounts':mounts,
            'networks':old['NetworkSettings']['Networks']}).hex(),'material_digest':hashlib.sha256(data).hexdigest(),
            'target_digest':digest(target).hex(),'logs':logs,'run_id':run_id,'old_state_digest':digest(old['State']).hex()}

    def _verify_archive(self,scope,run_id):
        self._load(scope,run_id)
        for item in scope['logs']:
            p=self._directory(run_id)/item['name']
            if p.is_symlink() or p.stat().st_mode & 0o077 or hashlib.sha256(p.read_bytes()).hexdigest()!=item['digest']:
                raise MemoryControlError(20126,'container_archive_changed')

    async def _create(self,target,scope,run_id):
        material=self._load(scope,run_id)
        context=json.loads(await self._docker('context','inspect'))[0]['Endpoints']['docker']['Host']
        if not context.startswith('unix://'):raise MemoryControlError(20126,'local_docker_socket_required')
        # Send protected Config directly to the local daemon: never argv/logs.
        import http.client,socket
        from urllib.parse import quote
        class UnixConnection(http.client.HTTPConnection):
            def connect(conn):
                conn.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);conn.sock.settimeout(30);conn.sock.connect(context[7:])
        def create():
            conn=UnixConnection('localhost');body=json.dumps(material).encode()
            try:
                conn.request('POST','/containers/create?name='+quote(target['new_name'],safe=''),body,{'Content-Type':'application/json'})
                response=conn.getresponse();response.read()
                if response.status!=201:raise MemoryControlError(20129,'container_create_failed')
            finally:conn.close()
        await asyncio.to_thread(create)

    async def execute(self,target,scope,run_id):
        if digest(target).hex()!=scope['target_digest'] or scope['run_id']!=run_id:raise ValueError('container_target_changed')
        self._verify_archive(scope,run_id)
        old=await self._inspect(scope['old_id'])
        if (not old or old['State']['Running'] or digest(old['State']).hex()!=scope['old_state_digest'] or digest({'config':old['Config'],'host':old['HostConfig'],
                'mounts':self._mounts(old),'networks':old['NetworkSettings']['Networks']}).hex()!=scope['old_config_digest']):
            raise MemoryControlError(20126,'container_t0_changed')
        await self._docker('rm',scope['old_id']) # No -v; mounts are preserved.
        await self._create(target,scope,run_id)
        return await self.reconcile(target,scope,run_id)

    async def reconcile(self,target,scope,run_id):
        if digest(target).hex()!=scope['target_digest'] or scope['run_id']!=run_id:raise ValueError('container_target_changed')
        self._verify_archive(scope,run_id)
        if await self._inspect(scope['old_id']):return {'state':'unknown'}
        new=await self._inspect(target['new_name'])
        if new is None:
            await self._create(target,scope,run_id);new=await self._inspect(target['new_name'])
        expected=self._load(scope,run_id)
        actual=self._config(new,target,run_id) if new else None
        ok=bool(new and new['State']['Status']=='created' and new['Image']==target['image']
            and new['Config']['Cmd']==target['command'] and new['Config']['Image']==target['image']
            and new['Config']['Labels'].get('memory.s15.run')==run_id
            and new['HostConfig']['RestartPolicy']=={'Name':'no','MaximumRetryCount':0}
            and self._mounts(new)==sorted(target['readonly_mounts'],key=lambda m:m['destination']) and actual==expected)
        return {'state':'confirmed' if ok else 'unknown','old_removed':True,'new_id':new['Id'] if new else None,
            'started':False,'logs_archived':True,'config_verified':ok}

class VectorResetAdapter:
    """Exact collection+partition adapter; zero count alone never closes unknown."""
    def __init__(self,*,target,delete_all,count,retirement_evidence=None,partitions=None,completion_evidence=None):
        self.target,self.delete_all,self.count=target,delete_all,count
        self.retirement_evidence=retirement_evidence
        # Trusted internal read-only verifiers authenticate facts before returning
        # them. Neither caller JSON nor a local signed assertion is a verifier.
        self.completion_evidence=completion_evidence
        self.partitions=partitions

    @staticmethod
    def valid_receipt(value):
        return (isinstance(value,dict) and set(value)=={'protocol','operation','code','request_id','mode','outcome'}
            and value['protocol']=='dashvector-delete-sync-v1' and value['operation']=='delete_all'
            and type(value['code']) is int and -(2**31)<=value['code']<2**31
            and isinstance(value['request_id'],str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}',value['request_id']) is not None
            and value['mode']=='sync' and value['outcome']==('request_completed' if value['code']==0 else 'failed'))

    @staticmethod
    def valid_binding(value,target,run_id):
        return (isinstance(value,dict) and set(value)=={'protocol','run_id','resource_key','target_digest','revision','origin'}
            and value['protocol']=='s15-vector-receipt-v1' and value['run_id']==run_id
            and isinstance(value['resource_key'],str) and 0<len(value['resource_key'])<=191
            and value['target_digest']==digest(target).hex() and type(value['revision']) is int and value['revision']>0
            and value['origin'] in {'registered_dispatch','legacy_read'})

    @staticmethod
    def valid_evidence(value,binding,kind):
        extra={'kind','operation','source','evidence_digest','request_id'}
        if kind=='target_retired':extra.add('late_delete_isolated')
        return (isinstance(value,dict) and set(value)==set(binding)|extra
            and all(value[k]==v for k,v in binding.items()) and value['kind']==kind
            and value['operation']=='delete_all'
            and value['source']==('provider_request_status' if kind=='request_completed' else 'independent_target_isolation')
            and isinstance(value['evidence_digest'],str) and re.fullmatch(r'[0-9a-f]{64}',value['evidence_digest']) is not None
            and isinstance(value['request_id'],str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}',value['request_id']) is not None
            and (kind!='target_retired' or value['late_delete_isolated'] is True))

    def _identity(self,target,scope,run_id,binding):
        if target!=self.target or digest(target).hex()!=scope['target_digest']:
            raise MemoryControlError(20127,'vector_target_changed')
        if binding is not None and not self.valid_binding(binding,target,run_id):
            raise MemoryControlError(20127,'vector_receipt_identity_changed')

    async def prepare(self,target,run_id):
        if target!=self.target or set(target)!={'cluster_fingerprint','collection','partition'}:
            raise MemoryControlError(20127,'vector_target_mismatch')
        return {'target_digest':digest(target).hex(),'before_count':await self.count(target)}

    async def inventory(self,target):
        if target!=self.target or self.partitions is None:raise MemoryControlError(20126,'vector_inventory_unverified')
        return await self.partitions()

    async def execute(self,target,scope,run_id,*,binding=None,checkpoint=None):
        self._identity(target,scope,run_id,binding)
        if binding is None or binding['origin']!='registered_dispatch' or checkpoint is None:
            return {'state':'unknown','reason':'vector_dispatch_unregistered'}
        receipt=await self.delete_all(target,run_id)
        if not self.valid_receipt(receipt):return {'state':'unknown','reason':'delete_receipt_unverified'}
        await checkpoint('receipt',receipt)  # Durable before any count/postcondition.
        return await self.reconcile(target,scope,run_id,binding=binding,receipt=receipt,checkpoint=checkpoint)

    async def reconcile(self,target,scope,run_id,*,binding=None,receipt=None,evidence=None,checkpoint=None):
        # Supplier late-deletion has no application tag/CAS. Only independent
        # exact request completion or target retirement can certify it now.
        self._identity(target,scope,run_id,binding)
        if binding is None:return {'state':'unknown','reason':'delete_acknowledgement_unverified'}
        proof=None
        if self.valid_receipt(receipt) and receipt['outcome']=='request_completed' and binding['origin']=='registered_dispatch':
            proof=('receipt',receipt)
        elif evidence is not None:
            for kind in ('request_completed','target_retired'):
                if (self.valid_evidence(evidence,binding,kind)
                        and (kind!='request_completed' or receipt is None or evidence['request_id']==receipt.get('request_id'))):
                    proof=('evidence',evidence)
        if proof is None and checkpoint is not None:
            for kind,reader in (('request_completed',self.completion_evidence),('target_retired',self.retirement_evidence)):
                if reader is None:continue
                value=await reader(target,run_id,dict(binding))
                if not self.valid_evidence(value,binding,kind):continue
                if receipt and kind=='request_completed' and value['request_id']!=receipt['request_id']:continue
                await checkpoint('evidence',value);proof=('evidence',value);break
        if proof is None:return {'state':'unknown','reason':'delete_acknowledgement_unverified'}
        if proof[1].get('kind')=='target_retired':
            return {'state':'confirmed','retired':True,'proof_digest':digest(proof[1]).hex()}
        try:count=await self.count(target)
        except Exception:return {'state':'unknown','reason':'vector_count_unverified'}
        if type(count) is not int or not 0<=count<2**64:return {'state':'unknown','reason':'vector_count_unverified'}
        return {'state':'confirmed' if count==0 else 'unknown','count':count,'proof_digest':digest(proof[1]).hex()}


class LocalObjectsResetAdapter:
    """Exact inventoried local audio/export files, with no recursive deletion."""
    def __init__(self,*,root):self.root=Path(root).resolve()

    def _paths(self,target):
        if set(target)!={'paths'}:raise ValueError('exact_object_paths_required')
        result=[]
        for value in target['paths']:
            p=Path(value)
            if not p.is_absolute() or p.is_symlink() or self.root not in p.resolve().parents:
                raise MemoryControlError(20127,'object_target_mismatch')
            result.append(p)
        return result

    async def prepare(self,target,run_id):
        files=[]
        for p in self._paths(target):
            st=p.stat()
            files.append({'path':str(p),'inode':st.st_ino,'device':st.st_dev,'digest':hashlib.sha256(p.read_bytes()).hexdigest()})
        return {'files':files}

    async def execute(self,target,scope,run_id):
        self._paths(target)
        for row in scope['files']:
            p=Path(row['path'])
            if not p.exists():continue
            st=p.stat()
            if st.st_ino!=row['inode'] or st.st_dev!=row['device'] or hashlib.sha256(p.read_bytes()).hexdigest()!=row['digest']:
                raise MemoryControlError(20127,'object_t0_changed')
            p.unlink()
        return await self.reconcile(target,scope,run_id)

    async def reconcile(self,target,scope,run_id):
        self._paths(target)
        # Local unlink finished before this read; no remote late-delete request.
        return {'state':'confirmed' if all(not Path(r['path']).exists() for r in scope['files']) else 'unknown'}


def dashvector_reset_adapter(*,endpoint,credential,collection,partition):
    """Explicit SDK target. No client defaults or old-to-new copying."""
    import dashvector
    from urllib.parse import urlsplit
    if urlsplit(endpoint).scheme!='https':raise ValueError('https_target_required')
    target={'cluster_fingerprint':hashlib.sha256(endpoint.rstrip('/').encode()).hexdigest(),
            'collection':collection,'partition':partition}
    client=dashvector.Client(api_key=credential,endpoint=urlsplit(endpoint).netloc)
    async def get():
        value=await asyncio.to_thread(client.get,collection)
        if not value:raise MemoryControlError(20129,'vector_target_unavailable')
        return value
    async def count(unused):
        value=await get();result=await asyncio.to_thread(value.stats)
        if not result:raise MemoryControlError(20129,'vector_count_unverified')
        output=result.output
        partitions=output.get('partitions') if isinstance(output,dict) else getattr(output,'partitions',None)
        item=partitions.get(partition) if isinstance(partitions,dict) else None
        value=item.get('total_doc_count') if isinstance(item,dict) else getattr(item,'total_doc_count',None)
        if type(value) is not int or value<0:raise MemoryControlError(20129,'vector_partition_count_unverified')
        return value
    async def partitions():
        value=await get();result=await asyncio.to_thread(value.list_partitions)
        if not result or not isinstance(result.output,list) or any(not isinstance(p,str) for p in result.output):
            raise MemoryControlError(20129,'vector_inventory_unverified')
        return result.output
    async def remove(unused,run_id):
        # SDK 1.0.23 sync Response construction waits for get(); code 0 is
        # synchronous completion, never inferred from truthiness or stats.
        value=await get();result=await asyncio.to_thread(value.delete,delete_all=True,partition=partition,async_req=False)
        code=getattr(result,'code',None);request_id=getattr(result,'request_id',None)
        receipt={'protocol':'dashvector-delete-sync-v1','operation':'delete_all','code':code,
            'request_id':request_id,'mode':'sync','outcome':'request_completed' if type(code) is int and code==0 else 'failed'}
        if not VectorResetAdapter.valid_receipt(receipt) or (credential and credential in request_id):return None
        return receipt
    return VectorResetAdapter(target=target,delete_all=remove,count=count,partitions=partitions)
