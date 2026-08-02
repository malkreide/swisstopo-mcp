# tests/test_deploy_manifests.py
"""The deployment artefacts are consistent with each other (audit SCALE-002/003).

`deploy/haproxy.cfg` was a complete, parseable, plausible-looking config that
would not have worked. Two independent reasons, and a reviewer would have caught
neither by reading it:

1. `stick on <pattern>` is shorthand for `stick match` + `stick store-REQUEST`.
   The MCP session id is minted by the *server* and returned in the response to
   `initialize`; that request carries no `Mcp-Session-Id`, so nothing was ever
   stored. The first request that did carry the header missed the empty table,
   got round-robined, and was then pinned to a possibly-wrong replica for an
   hour.
2. The `server` lines named `swisstopo-mcp-1` and `swisstopo-mcp-2` — hosts
   nothing in this repository creates. With no `resolvers` section HAProxy
   resolves once at startup and refuses to start on an unresolvable name.

Both are cross-file properties: the config is only correct *relative to* the
manifests, and nothing checked that. These tests do. They cannot prove HAProxy
routes correctly — that needs a running cluster, and the manual procedure is in
docs/deployment.md — but they hold every property that was actually wrong.
"""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

DEPLOY = pathlib.Path(__file__).resolve().parent.parent / "deploy"


@pytest.fixture(scope="module")
def haproxy_cfg() -> str:
    return (DEPLOY / "haproxy.cfg").read_text(encoding="utf-8")


def _load(name: str) -> list[dict]:
    return [d for d in yaml.safe_load_all((DEPLOY / name).read_text(encoding="utf-8")) if d]


def _by_kind(docs: list[dict], kind: str) -> dict:
    matches = [d for d in docs if d.get("kind") == kind]
    assert matches, f"no {kind} in the manifest"
    return matches[0]


class TestAffinityIsActuallyLearned:
    """The defect that made the whole stick-table inert."""

    def test_session_id_is_stored_from_the_response(self, haproxy_cfg):
        assert re.search(
            r"^\s*stick\s+store-response\s+res\.hdr\(Mcp-Session-Id\)",
            haproxy_cfg,
            re.M | re.I,
        ), (
            "no `stick store-response res.hdr(Mcp-Session-Id)`. The session id "
            "is minted in the response to initialize, so without this the "
            "stick-table is never populated and affinity never happens."
        )

    def test_session_id_is_matched_on_requests(self, haproxy_cfg):
        assert re.search(
            r"^\s*stick\s+match\s+req\.hdr\(Mcp-Session-Id\)", haproxy_cfg, re.M | re.I
        )

    def test_no_bare_stick_on(self, haproxy_cfg):
        """`stick on` is the shorthand that caused this: it stores from the
        request, which for a server-generated id is always empty."""
        assert not re.search(r"^\s*stick\s+on\s+", haproxy_cfg, re.M | re.I), (
            "`stick on` stores from the request. Use explicit `stick "
            "store-response` + `stick match` for a server-minted identifier."
        )

    def test_stick_table_is_sized_and_expires(self, haproxy_cfg):
        match = re.search(
            r"^\s*stick-table\s+type\s+string\s+len\s+(\d+)\s+size\s+(\d+)k\s+expire\s+(\S+)",
            haproxy_cfg,
            re.M,
        )
        assert match, "no stick-table declaration"
        assert int(match.group(2)) >= 100, "stick-table below the 100k floor"
        assert match.group(3), "no explicit TTL"


class TestBackendsResolveToSomethingThisRepoShips:
    """The second defect: server names nothing created."""

    def test_a_resolvers_section_exists(self, haproxy_cfg):
        assert re.search(r"^resolvers\s+\S+", haproxy_cfg, re.M), (
            "no resolvers section — HAProxy resolves server names once at "
            "startup and refuses to start on an unresolvable name, which is "
            "exactly what happens while a StatefulSet is scaling up."
        )

    def test_backends_use_the_headless_service(self, haproxy_cfg):
        headless = _by_kind(_load("statefulset.yaml"), "Service")
        name = headless["metadata"]["name"]
        assert name in haproxy_cfg, (
            f"haproxy.cfg does not reference {name}; the backend addresses must "
            "point at something this repository actually creates"
        )

    def test_the_headless_service_is_headless(self):
        headless = _by_kind(_load("statefulset.yaml"), "Service")
        assert headless["spec"].get("clusterIP") == "None", (
            "a ClusterIP Service hides individual pods behind one virtual IP, "
            "which defeats per-pod affinity"
        )

    def test_the_statefulset_matches_the_service_name(self):
        docs = _load("statefulset.yaml")
        sts = _by_kind(docs, "StatefulSet")
        headless = _by_kind(docs, "Service")
        assert sts["spec"]["serviceName"] == headless["metadata"]["name"], (
            "a StatefulSet only gets stable per-pod DNS from the Service named in spec.serviceName"
        )

    def test_no_invented_hostnames_remain(self, haproxy_cfg):
        """The exact strings that were wrong before."""
        for ghost in ("swisstopo-mcp-1:", "swisstopo-mcp-2:", "10.0.0.1", "10.0.0.2"):
            assert ghost not in haproxy_cfg, f"invented backend address: {ghost}"


class TestTheStatefulSetKeepsTheDeploymentsHardening:
    """Copying a manifest is how security context quietly diverges."""

    @staticmethod
    def _container(docs: list[dict], kind: str) -> dict:
        workload = _by_kind(docs, kind)
        return workload["spec"]["template"]["spec"]["containers"][0]

    def test_container_security_context_matches(self):
        deployment = self._container(_load("kubernetes.yaml"), "Deployment")
        stateful = self._container(_load("statefulset.yaml"), "StatefulSet")
        assert stateful["securityContext"] == deployment["securityContext"], (
            "the StatefulSet's container securityContext drifted from the "
            "Deployment's — SEC-007's hardening applies to both"
        )

    def test_required_env_vars_are_present(self):
        stateful = self._container(_load("statefulset.yaml"), "StatefulSet")
        names = {e["name"] for e in stateful["env"]}
        for required in (
            "SWISSTOPO_HTTP_HOST",
            "SWISSTOPO_ALLOWED_HOSTS",
            "SWISSTOPO_ALLOWED_ORIGINS",
            "SWISSTOPO_SESSION_IDLE_TIMEOUT",
        ):
            assert required in names, f"{required} missing from the StatefulSet"

    def test_pod_security_context_matches(self):
        d = _by_kind(_load("kubernetes.yaml"), "Deployment")
        s = _by_kind(_load("statefulset.yaml"), "StatefulSet")
        assert (
            s["spec"]["template"]["spec"]["securityContext"]
            == d["spec"]["template"]["spec"]["securityContext"]
        )


class TestTheHaproxyDeploymentIsCoherent:
    def test_configmap_name_matches_the_documented_command(self):
        docs = _load("haproxy-deployment.yaml")
        deployment = _by_kind(docs, "Deployment")
        volume = deployment["spec"]["template"]["spec"]["volumes"][0]
        configmap = volume["configMap"]["name"]
        header = (DEPLOY / "haproxy-deployment.yaml").read_text(encoding="utf-8")
        assert "--from-file=deploy/haproxy.cfg" in header
        assert configmap in header, (
            "the ConfigMap the Deployment mounts is not the one the documented "
            "create command builds — the same defect SEC-021 had in "
            "egress-proxy.yaml"
        )

    def test_mount_path_matches_the_config_header(self, haproxy_cfg):
        deployment = _by_kind(_load("haproxy-deployment.yaml"), "Deployment")
        mount = deployment["spec"]["template"]["spec"]["containers"][0]["volumeMounts"][0]
        assert mount["mountPath"] in haproxy_cfg, (
            "haproxy.cfg documents a different mount path than the Deployment uses"
        )

    def test_frontend_port_matches_the_container_port(self, haproxy_cfg):
        bind = re.search(r"^\s*bind\s+:(\d+)", haproxy_cfg, re.M)
        assert bind, "no bind directive"
        deployment = _by_kind(_load("haproxy-deployment.yaml"), "Deployment")
        ports = deployment["spec"]["template"]["spec"]["containers"][0]["ports"]
        assert int(bind.group(1)) in {p["containerPort"] for p in ports}

    def test_service_targets_the_haproxy_port(self, haproxy_cfg):
        service = _by_kind(_load("haproxy-deployment.yaml"), "Service")
        bind = int(re.search(r"^\s*bind\s+:(\d+)", haproxy_cfg, re.M).group(1))
        assert service["spec"]["ports"][0]["targetPort"] == bind


class TestTheEgressProxySidecarMountsWhatItReads:
    """The defect SEC-021 found second, and the one nothing guarded against.

    The sidecar passed `--config-file=/etc/smokescreen/config.yaml`, but the
    documented ConfigMap is built `--from-file=deploy/smokescreen-acl.yaml`
    alone, so that path would not exist at the mount and Smokescreen would exit
    before serving anything. The flag was dropped; these tests are what stops an
    equivalent one from being added back.

    Deliberately generic: it asserts that *every* file the args name under the
    mount path is one the documented create command actually supplies, rather
    than blacklisting the single string that was wrong.
    """

    @staticmethod
    def _manifest() -> str:
        return (DEPLOY / "egress-proxy.yaml").read_text(encoding="utf-8")

    @staticmethod
    def _sidecar() -> dict:
        deployment = _by_kind(_load("egress-proxy.yaml"), "Deployment")
        containers = deployment["spec"]["template"]["spec"]["containers"]
        matches = [c for c in containers if c["name"] == "smokescreen"]
        assert matches, "no smokescreen sidecar in egress-proxy.yaml"
        return matches[0]

    def test_configmap_name_matches_the_documented_command(self):
        deployment = _by_kind(_load("egress-proxy.yaml"), "Deployment")
        volume = deployment["spec"]["template"]["spec"]["volumes"][0]
        assert volume["configMap"]["name"] in self._manifest(), (
            "the Deployment mounts a ConfigMap the documented create command does not build"
        )

    def test_every_file_the_args_name_is_supplied_by_the_configmap(self):
        sidecar = self._sidecar()
        mount = sidecar["volumeMounts"][0]["mountPath"].rstrip("/")
        supplied = {
            pathlib.PurePosixPath(p).name
            for p in re.findall(r"--from-file=(\S+)", self._manifest())
        }
        assert supplied, "the manifest header documents no --from-file source"

        for arg in sidecar["args"]:
            _, _, value = arg.partition("=")
            if not value.startswith(f"{mount}/"):
                continue
            requested = pathlib.PurePosixPath(value).name
            assert requested in supplied, (
                f"the sidecar reads {value!r}, but the documented ConfigMap is "
                f"built from {sorted(supplied)} only — that file would be absent "
                "from the mount and the container would fail to start. Either "
                "add it to the create command in the manifest header, or drop "
                "the flag (audit SEC-021)."
            )

    def test_the_acl_the_sidecar_reads_is_the_generated_one(self):
        """A sidecar pointed at a hand-written ACL would silently escape the
        `render_egress_acl.py --check` gate."""
        sidecar = self._sidecar()
        assert any("smokescreen-acl.yaml" in arg for arg in sidecar["args"]), (
            "the sidecar does not read smokescreen-acl.yaml, which is the file "
            "generated from ALLOWED_HOSTS and gated in CI"
        )


class TestTheDocumentationPointsAtTheRealFiles:
    """`docs/deployment.md` linked only to ingress-sticky-sessions.yaml, so the
    config that was supposed to be the deployable one went unreferenced."""

    @staticmethod
    def _doc() -> str:
        return (DEPLOY.parent / "docs" / "deployment.md").read_text(encoding="utf-8")

    @pytest.mark.parametrize(
        "artefact",
        ["deploy/haproxy.cfg", "deploy/statefulset.yaml", "deploy/haproxy-deployment.yaml"],
    )
    def test_artefact_is_referenced(self, artefact):
        assert artefact in self._doc(), (
            f"{artefact} is not mentioned in docs/deployment.md — an unreferenced "
            "deployment artefact is one nobody applies"
        )

    def test_the_manual_verification_procedure_exists(self):
        """These tests cannot prove HAProxy routes correctly; that needs a
        cluster. The check requires the behaviour to be verified, so the
        procedure has to be written down."""
        doc = self._doc()
        assert "Verifying affinity" in doc
        assert "Mcp-Session-Id" in doc


# ---------------------------------------------------------------------------
# The constraint that makes affinity necessary (audit SCALE-002)
#
# The finding notes that nothing tested session affinity in any form. A unit
# test cannot exercise HAProxy, but it can pin the property that *creates* the
# requirement: a Streamable-HTTP session lives in the process that minted it.
# If that ever stops being true — a shared session store, an SDK change — the
# single-replica default and the whole HAProxy arrangement are obsolete, and
# this test failing is how anyone would find out.
# ---------------------------------------------------------------------------

MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "affinity-test", "version": "0"},
    },
}
PING = {"jsonrpc": "2.0", "id": 2, "method": "ping"}


def _asgi(manager):
    async def app(scope, receive, send):
        await manager.handle_request(scope, receive, send)

    return app


class TestSessionsAreConfinedToOneProcess:
    """Two independent session managers over the same server — which is what
    two replicas are."""

    @staticmethod
    async def _two_replicas():
        from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

        # mcp 2.x: transport_security is no longer a setting on the server, so
        # the replicas read the same builder the real app is given.
        from swisstopo_mcp.server import _transport_security, mcp

        return [
            StreamableHTTPSessionManager(
                app=mcp._lowlevel_server,
                security_settings=_transport_security(),
            )
            for _ in range(2)
        ]

    async def test_a_session_from_one_replica_is_unknown_to_the_other(self):
        import httpx

        from swisstopo_mcp.server import server_resources

        replica_a, replica_b = await self._two_replicas()
        async with server_resources(), replica_a.run(), replica_b.run():
            async with (
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=_asgi(replica_a)),
                    base_url="http://localhost",
                ) as client_a,
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=_asgi(replica_b)),
                    base_url="http://localhost",
                ) as client_b,
            ):
                opened = await client_a.post("/mcp", headers=MCP_HEADERS, json=INITIALIZE)
                session_id = opened.headers.get("mcp-session-id")
                assert session_id, "no session id was minted"

                headers = {**MCP_HEADERS, "Mcp-Session-Id": session_id}
                on_a = await client_a.post("/mcp", headers=headers, json=PING)
                on_b = await client_b.post("/mcp", headers=headers, json=PING)

        assert on_a.status_code == 200, "the minting replica must still serve it"
        assert on_b.status_code == 404, (
            "a session resolved on a second replica — sessions are no longer "
            "per-process, which would make the single-replica default and the "
            "HAProxy affinity arrangement obsolete. Verify deliberately before "
            "relaxing either."
        )

    async def test_each_replica_tracks_only_its_own_sessions(self):
        import httpx

        from swisstopo_mcp.server import server_resources

        replica_a, replica_b = await self._two_replicas()
        async with server_resources(), replica_a.run(), replica_b.run():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=_asgi(replica_a)),
                base_url="http://localhost",
            ) as client_a:
                await client_a.post("/mcp", headers=MCP_HEADERS, json=INITIALIZE)
            assert len(replica_a._server_instances) == 1
            assert replica_b._server_instances == {}, "state leaked between replicas"


class TestTheDeploymentStaysAtOneReplica:
    """A reader who raises `replicas` on the plain Deployment gets sessions that
    break on their second request — intermittently, which reads like flaky
    clients rather than a misconfiguration. The multi-replica path is the
    StatefulSet."""

    def test_the_base_deployment_is_single_replica(self):
        deployment = _by_kind(_load("kubernetes.yaml"), "Deployment")
        assert deployment["spec"]["replicas"] == 1, (
            "deploy/kubernetes.yaml raises replicas above 1 without affinity. "
            "Use deploy/statefulset.yaml behind deploy/haproxy-deployment.yaml, "
            "which is the path docs/deployment.md documents."
        )

    def test_the_statefulset_is_the_multi_replica_path(self):
        sts = _by_kind(_load("statefulset.yaml"), "StatefulSet")
        assert sts["spec"]["replicas"] > 1, (
            "the StatefulSet exists to run more than one replica; at 1 it is "
            "just a more complicated Deployment"
        )


class TestTheAffinityFallbackAndItsLimits:
    """`sessionAffinity: ClientIP` is a fallback for the raise-replicas case,
    not the mechanism. Both facts need to stay true."""

    def test_the_base_service_sets_client_ip_affinity(self):
        service = _by_kind(_load("kubernetes.yaml"), "Service")
        assert service["spec"].get("sessionAffinity") == "ClientIP"

    def test_the_fallback_has_an_explicit_timeout(self):
        service = _by_kind(_load("kubernetes.yaml"), "Service")
        timeout = service["spec"]["sessionAffinityConfig"]["clientIP"]["timeoutSeconds"]
        assert timeout > 0

    def test_its_limits_are_documented_at_the_manifest(self):
        """A fallback presented without its failure mode gets mistaken for the
        solution — behind an ingress it pins every client to one pod."""
        manifest = (DEPLOY / "kubernetes.yaml").read_text(encoding="utf-8")
        assert "ingress" in manifest.lower()
        assert "statefulset" in manifest.lower()


class TestHaproxyDoesNotReintroduceTheSameDefect:
    """Each HAProxy process holds its own stick-table. Two of them behind a
    round-robin Service learn different halves of the session map — the same
    defect SCALE-003 was about, one layer up."""

    def test_haproxy_runs_a_single_replica(self):
        deployment = _by_kind(_load("haproxy-deployment.yaml"), "Deployment")
        assert deployment["spec"]["replicas"] == 1, (
            "more than one HAProxy replica without a `peers` section means two "
            "independent stick-tables; a client whose initialize lands on one "
            "instance and whose next request lands on the other misses the map"
        )

    def test_the_peers_requirement_is_documented(self):
        manifest = (DEPLOY / "haproxy-deployment.yaml").read_text(encoding="utf-8")
        assert "peers" in manifest, (
            "scaling HAProxy needs stick-table replication; say so where "
            "somebody would otherwise just raise the number"
        )
