"""Explicit production transition: retain old vectors and create no data backup.

This is an opt-in maintenance policy, never an application startup hook. The
normal S15 deletion/acknowledgement protocol is not weakened or impersonated.
"""
import asyncio
import hashlib
import json
import re
from pathlib import Path

from backend.services.memory_reset_service import MemoryResetService, REQUIRED_SEALS, digest
from backend.services.memory_runtime_service import MemoryControlError

PRODUCTION_POLICY = {"old_vectors": "preserve", "data_backup": "none"}
PRODUCTION_SEALS = tuple(k for k in REQUIRED_SEALS if k != "old_credentials_revoked") + ("old_runtime_target_isolated",)


class ReadOnlyVectorTransition:
    """There is deliberately no vector mutation capability on this adapter."""

    def __init__(self, target, other_target, *, policy, count, partitions):
        keys = {"cluster_fingerprint", "collection", "partition"}
        if set(target) != keys or set(other_target) != keys or policy not in {"preserve", "require_empty"}:
            raise ValueError("explicit_vector_transition_required")
        if target["collection"] == other_target["collection"]:
            raise ValueError("distinct_collections_required")
        if target["cluster_fingerprint"] != other_target["cluster_fingerprint"]:
            raise ValueError("same_cluster_required")
        self.target, self.policy, self.count, self.partitions = dict(target), policy, count, partitions

    async def inventory(self, target):
        if target != self.target:
            raise MemoryControlError(20127, "vector_target_changed")
        result = await self.partitions()
        if not isinstance(result, list) or any(not isinstance(x, str) for x in result) or len(set(result)) != len(result):
            raise MemoryControlError(20129, "vector_inventory_unverified")
        return result

    async def prepare(self, target, run_id):
        partitions = await self.inventory(target)
        if target["partition"] not in partitions:
            raise MemoryControlError(20127, "vector_partition_missing")
        count = await self.count(target)
        if type(count) is not int or not 0 <= count < 2**64:
            raise MemoryControlError(20129, "vector_count_unverified")
        if self.policy == "require_empty" and count != 0:
            raise MemoryControlError(20126, "new_collection_not_empty")
        return {"target_digest": digest(target).hex(), "run_id": run_id, "policy": self.policy,
                "partitions": sorted(partitions), "before_count": count}

    async def execute(self, target, scope, run_id):
        return await self.reconcile(target, scope, run_id)

    async def reconcile(self, target, scope, run_id):
        if (target != self.target or scope.get("target_digest") != digest(target).hex()
                or scope.get("run_id") != run_id or scope.get("policy") != self.policy):
            raise MemoryControlError(20127, "vector_transition_scope_changed")
        if sorted(await self.inventory(target)) != scope["partitions"]:
            return {"state": "unknown"}
        count = await self.count(target)
        if type(count) is not int or count != scope["before_count"]:
            return {"state": "unknown"}
        if self.policy == "require_empty":
            # An acknowledged read of an already empty, distinct collection,
            # not a fabricated deletion receipt. This is the baseline DTO used
            # by the existing actual-backfill verifier.
            return {"state": "confirmed", "count": 0, "acknowledged": True} if count == 0 else {"state": "unknown"}
        return {"state": "confirmed", "action": "preserved", "count": count}


class ProductionResetService(MemoryResetService):
    def _resources(self, manifest):
        old, new = [], []
        for resource in manifest["resources"]:
            kind = resource["key"].split(":")[0]
            if kind not in {"vector-old", "vector-new"}:
                continue
            adapter = self.adapters.get(resource["adapter"])
            policy = "preserve" if kind == "vector-old" else "require_empty"
            if not isinstance(adapter, ReadOnlyVectorTransition) or adapter.policy != policy or adapter.target != resource["target"]:
                raise MemoryControlError(20126, "read_only_vector_adapter_required")
            (old if kind == "vector-old" else new).append(resource["target"])
        if (not old or not new or len({x["collection"] for x in old}) != 1
                or len({x["collection"] for x in new}) != 1
                or old[0]["collection"] == new[0]["collection"]
                or len({x["cluster_fingerprint"] for x in old + new}) != 1):
            raise MemoryControlError(20126, "explicit_distinct_vector_inventory_required")

    async def preview(self, *, resources):
        manifest = await super().preview(resources=resources)
        self._resources(manifest)
        manifest["production_policy"] = dict(PRODUCTION_POLICY)
        manifest["manifest_hash"] = digest({k: v for k, v in manifest.items() if k != "manifest_hash"}).hex()
        return manifest

    def _authorize(self, manifest, auth):
        if manifest.get("production_policy") != PRODUCTION_POLICY:
            raise MemoryControlError(20126, "production_policy_required")
        if (digest({k: v for k, v in manifest.items() if k != "manifest_hash"}).hex() != manifest.get("manifest_hash")
                or manifest["environment_id"] != self.environment_id or manifest["target_fingerprint"] != self.target.hex()
                or auth.get("environment_id") != self.environment_id or auth.get("manifest_hash") != manifest["manifest_hash"]
                or not auth.get("run_id") or not auth.get("operator_id")):
            raise MemoryControlError(20127, "reset_authorization_mismatch")
        seals = auth.get("seals", {})
        if set(seals) != set(PRODUCTION_SEALS) or any(not isinstance(v, str) or re.fullmatch(r"[0-9a-f]{64}", v) is None for v in seals.values()):
            raise MemoryControlError(20126, "production_seals_incomplete")
        self._resources(manifest)


class NoBackupContainerTransition:
    """Remove only the frozen stopped backend; Compose creates but never starts.

    Old configuration is represented by digests only. Credentials, container
    logs and application files are never copied into a recovery archive.
    """

    async def _command(self, *args):
        process = await asyncio.create_subprocess_exec("docker", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(process.communicate(), 60)
        return process.returncode, stdout, stderr

    async def _docker(self, *args):
        code, stdout, _ = await self._command(*args)
        if code:
            raise MemoryControlError(20129, "docker_command_failed")
        return stdout.decode().strip()

    async def _inspect(self, identity):
        code, stdout, stderr = await self._command("container", "inspect", identity)
        if code == 0:
            value = json.loads(stdout)
            if not isinstance(value, list) or len(value) != 1:
                raise MemoryControlError(20129, "docker_inspect_unverified")
            return value[0]
        if code == 1 and (b"No such container" in stderr or b"No such object" in stderr):
            return None
        raise MemoryControlError(20129, "docker_inspect_unavailable")

    @staticmethod
    def _compose(target):
        return ("compose", "--project-directory", target["project_directory"], "-p", target["project"],
                *(arg for path in target["compose_files"] for arg in ("-f", path)))

    async def _compose_digest(self, target):
        value = json.loads(await self._docker(*self._compose(target), "config", "--format", "json"))
        service = value["services"][target["service"]]
        if service.get("image") != target["image_id"] or service.get("restart") != "no":
            raise MemoryControlError(20126, "stopped_pinned_compose_required")
        return digest(value).hex()

    @staticmethod
    def _old_digest(old):
        return digest({**{k: old[k] for k in ("Id", "State", "Image", "Config", "HostConfig", "Mounts")},
                       "networks": old["NetworkSettings"]["Networks"]}).hex()

    @staticmethod
    def _mounts(value):
        if any(x["Type"] != "bind" or x["RW"] for x in value["Mounts"]):
            raise MemoryControlError(20126, "container_mount_scope_unverified")
        return sorted(({"source": x["Source"], "destination": x["Destination"], "readonly": True} for x in value["Mounts"]),
                      key=lambda x: x["destination"])

    async def prepare(self, target, run_id):
        public_keys = {"DASHVECTOR_COLLECTION_NAME", "MEMORY_RUNTIME_ENVIRONMENT_ID", "ALIYUN_EMBEDDING_MODEL",
                       "ALIYUN_EMBEDDING_DIMENSION", "ALIYUN_RERANK_MODEL"}
        if (not re.fullmatch(r"[0-9a-f]{64}", target["old_id"]) or not re.fullmatch(r"sha256:[0-9a-f]{64}", target["image_id"])
                or not target["compose_files"] or any(not Path(p).is_absolute() for p in target["compose_files"])
                or target["service"] != "backend" or not target["expected_public_env"]
                or set(target["expected_public_env"]) - public_keys):
            raise ValueError("explicit_backend_target_required")
        if any(not x.get("readonly") or x.get("destination") not in {"/app/admin", "/app/frontend"}
               or not Path(x["source"]).is_absolute() or Path(x["source"]).name != Path(x["destination"]).name
               for x in target["expected_mounts"]):
            raise ValueError("explicit_static_mounts_required")
        old = await self._inspect(target["old_id"])
        if not old or old["State"]["Running"] or old["HostConfig"]["RestartPolicy"]["Name"] != "no":
            raise MemoryControlError(20126, "old_backend_not_sealed")
        mounts = self._mounts(old)
        if any(x["destination"] not in {"/app/admin", "/app/frontend"} for x in mounts):
            raise MemoryControlError(20126, "persistent_object_inventory_required")
        return {"target_digest": digest(target).hex(), "run_id": run_id, "old_digest": self._old_digest(old),
                "compose_digest": await self._compose_digest(target), "ports": old["HostConfig"]["PortBindings"],
                "networks": sorted(old["NetworkSettings"]["Networks"]), "backup_created": False}

    def _scope(self, target, scope, run_id):
        if scope.get("target_digest") != digest(target).hex() or scope.get("run_id") != run_id or scope.get("backup_created") is not False:
            raise MemoryControlError(20127, "container_transition_scope_changed")

    async def execute(self, target, scope, run_id):
        self._scope(target, scope, run_id)
        old = await self._inspect(target["old_id"])
        if not old or old["State"]["Running"] or self._old_digest(old) != scope["old_digest"]:
            raise MemoryControlError(20126, "container_t0_changed")
        if await self._compose_digest(target) != scope["compose_digest"]:
            raise MemoryControlError(20127, "release_compose_changed")
        await self._docker("rm", target["old_id"])
        return await self.reconcile(target, scope, run_id)

    async def reconcile(self, target, scope, run_id):
        self._scope(target, scope, run_id)
        if await self._inspect(target["old_id"]) is not None:
            return {"state": "unknown"}
        if await self._compose_digest(target) != scope["compose_digest"]:
            raise MemoryControlError(20127, "release_compose_changed")
        new = await self._inspect(target["new_name"])
        if new is None:
            # compose create has no --no-deps. Never recreate its already
            # existing database/cache dependencies or rebuild/pull an image.
            await self._docker(*self._compose(target), "create", "--no-recreate", "--no-build", "--pull", "never", target["service"])
            new = await self._inspect(target["new_name"])
        env = dict(x.split("=", 1) for x in (new or {}).get("Config", {}).get("Env", []))
        labels = (new or {}).get("Config", {}).get("Labels", {}) or {}
        ok = bool(new and new["State"]["Status"] == "created" and not new["State"]["Running"]
                  and new["Image"] == target["image_id"] and new["HostConfig"]["RestartPolicy"]["Name"] == "no"
                  and new["HostConfig"]["PortBindings"] == scope["ports"]
                  and sorted(new["NetworkSettings"]["Networks"]) == scope["networks"]
                  and self._mounts(new) == sorted(target["expected_mounts"], key=lambda x: x["destination"])
                  and labels.get("com.docker.compose.project") == target["project"]
                  and labels.get("com.docker.compose.service") == target["service"]
                  and all(env.get(k) == v for k, v in target["expected_public_env"].items()))
        return {"state": "confirmed" if ok else "unknown", "old_removed": True, "started": False,
                "backup_created": False, "new_id": new["Id"] if new else None}


class RemovedContainerArtifacts:
    """Read-only proof for old logs/PCM/exports confined to its writable layer.

    Writable host mounts are rejected by the container adapter. Preserved OSS
    feed images are outside this explicit container-layer resource scope.
    """

    def __init__(self, docker, container_target):
        self.docker, self.container_target = docker, container_target

    async def prepare(self, target, run_id):
        if target.get("container_id") != self.container_target["old_id"] or target.get("scope") not in {"logs", "transient_objects"}:
            raise MemoryControlError(20127, "container_artifact_target_changed")
        old = await self.docker._inspect(target["container_id"])
        if old is None or old["State"]["Running"]:
            raise MemoryControlError(20126, "old_backend_not_sealed")
        self.docker._mounts(old)
        return {"target_digest": digest(target).hex(), "run_id": run_id, "backup_created": False}

    async def execute(self, target, scope, run_id):
        return await self.reconcile(target, scope, run_id)

    async def reconcile(self, target, scope, run_id):
        if scope.get("target_digest") != digest(target).hex() or scope.get("run_id") != run_id:
            raise MemoryControlError(20127, "container_artifact_scope_changed")
        old = await self.docker._inspect(target["container_id"])
        new = await self.docker._inspect(self.container_target["new_name"])
        ok = old is None and new is not None and new["State"]["Status"] == "created" and new["Image"] == self.container_target["image_id"]
        return {"state": "confirmed" if ok else "unknown", "scope": target["scope"], "backup_created": False}


def readonly_dashvector_adapter(*, endpoint, credential, collection, partition, other_collection, policy):
    import dashvector
    from urllib.parse import urlsplit
    parsed = urlsplit(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("https_target_required")
    cluster = hashlib.sha256(endpoint.rstrip("/").encode()).hexdigest()
    target = {"cluster_fingerprint": cluster, "collection": collection, "partition": partition}
    other = {**target, "collection": other_collection}
    client = dashvector.Client(api_key=credential, endpoint=parsed.netloc)

    async def get():
        value = await asyncio.to_thread(client.get, collection)
        if not value:
            raise MemoryControlError(20129, "vector_target_unavailable")
        return value

    async def count(unused):
        value = await get()
        result = await asyncio.to_thread(value.stats)
        if not result:
            raise MemoryControlError(20129, "vector_count_unverified")
        output = result.output
        partitions = output.get("partitions") if isinstance(output, dict) else getattr(output, "partitions", None)
        item = partitions.get(partition) if isinstance(partitions, dict) else None
        total = item.get("total_doc_count") if isinstance(item, dict) else getattr(item, "total_doc_count", None)
        if type(total) is not int or total < 0:
            raise MemoryControlError(20129, "vector_partition_count_unverified")
        return total

    async def partitions():
        value = await get()
        result = await asyncio.to_thread(value.list_partitions)
        if not result:
            raise MemoryControlError(20129, "vector_inventory_unverified")
        return result.output

    return ReadOnlyVectorTransition(target, other, policy=policy, count=count, partitions=partitions)
