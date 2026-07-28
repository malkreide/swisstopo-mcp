## Finding: SEC-021 — Egress-Allow-List: Code-Layer und Network-Layer

**Severity:** high
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** SEC-021
**PDF-Reference:** Anhang B5 + B12
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
The code-layer allow-list is correct and non-mutable: a frozenset of ten hosts built
from literals (`api_client.py:55-68`), enforced before every request, with
`check_host=False` never passed anywhere in `src/`. Documentation and the update
procedure exist and are test-enforced in both directions
(`tests/test_egress_allowlist.py:122-143`). The generation claim is true —
`scripts/render_egress_acl.py` renders the ACL from `ALLOWED_HOSTS` and CI runs
`--check` on every push; executed, it reports "up to date (10 hosts)".

**The generated ACL does not work.** `render_egress_acl.py:25` emits host entries at
two-space indent while the `allowed_domains:` key sits at four. Parsing
`deploy/smokescreen-acl.yaml` with `yaml.safe_load` yields
`services[0].allowed_domains == null`, with the ten hostnames promoted to bare strings
as *siblings of the service object*. The per-host network-layer allow-list therefore
does not exist in any loadable form.

The CI gate cannot see this: `render_egress_acl.py:44` compares the committed file
byte-for-byte against the output of the same buggy renderer. It gates staleness, not
validity, and no test parses the file. A second defect: `deploy/egress-proxy.yaml:30`
passes `--config-file=/etc/smokescreen/config.yaml`, but the ConfigMap
(`egress-proxy.yaml:13`) is created from `smokescreen-acl.yaml` only, so the sidecar
would fail to start.

### Expected Behavior
- Per-host egress allow-list at the network layer
- Documented and enforced

### Evidence
- Code-layer allow-list is correct and non-mutable: src/swisstopo_mcp/api_client.py:55-68 declares ALLOWED_HOSTS as a frozenset of ten hosts, built from literals with an explicit comment that it is not loaded from env. No wildcards. Enforced by assert_host_allowed at src/swisstopo_mcp/api_client.py:121-137.
- The pre-request check runs on every outbound path — verified, not assumed. request_with_retry calls it before the first attempt (src/swisstopo_mcp/api_client.py:293-294) and `check_host=False` is never passed anywhere in src/; the two direct-client sites in oereb.py call it explicitly (src/swisstopo_mcp/oereb.py:91 and :183). The strongest case: src/swisstopo_mcp/geodata.py:426 takes a base URL out of the remote geodienste.ch catalogue and it still cannot escape the frozenset.
- Documentation and update procedure exist and are test-enforced in both directions: docs/network-egress.md tabulates all ten hosts with purpose and consuming tools, and lists a five-step update procedure. tests/test_egress_allowlist.py:122-127 fails if a code host is undocumented; tests/test_egress_allowlist.py:129-143 fails if a documented host left the code.
- The generation claim is TRUE: scripts/render_egress_acl.py:22-31 renders deploy/smokescreen-acl.yaml from ALLOWED_HOSTS, and .github/workflows/ci.yml:48-49 runs `--check` on every push and PR. I executed it — exit 0, 'smokescreen-acl.yaml is up to date (10 hosts)'. deploy/egress-proxy.yaml is shipped as claimed, with the Smokescreen sidecar (deploy/egress-proxy.yaml:27-45) and a replacement NetworkPolicy permitting DNS plus proxied HTTPS only (deploy/egress-proxy.yaml:64-95).
- BUT THE GENERATED ACL IS STRUCTURALLY BROKEN. scripts/render_egress_acl.py:25 emits the host entries at two-space indent (`f"  - {h}"`) while the `allowed_domains:` key it attaches them to sits at four-space indent (scripts/render_egress_acl.py:28, matching deploy/smokescreen-acl.yaml:22). Parsing deploy/smokescreen-acl.yaml with yaml.safe_load yields `services[0].allowed_domains == null` and the ten hostnames promoted to bare strings *as siblings of the service object* inside the `services` list. The per-host network-layer allow-list the check requires therefore does not exist in any loadable form — the file either fails Smokescreen's unmarshal or enforces an empty domain list.
- The CI gate cannot catch this: scripts/render_egress_acl.py:44 compares the committed file byte-for-byte against the output of the same buggy renderer. It gates staleness, not validity. There is no test anywhere that parses deploy/smokescreen-acl.yaml.
- A second defect in the same artefact: deploy/egress-proxy.yaml:30 passes `--config-file=/etc/smokescreen/config.yaml`, but the documented ConfigMap (deploy/egress-proxy.yaml:13) is created from smokescreen-acl.yaml only, so config.yaml would be absent from the mount at deploy/egress-proxy.yaml:38 and the sidecar would fail to start.

Gaps:
- deploy/smokescreen-acl.yaml is invalid as a Smokescreen ACL — allowed_domains parses as null and the ten hosts land as stray strings in `services`. Fix: emit the rules at six-space indent in scripts/render_egress_acl.py:25 (`f"      - {h}"`).
- No test parses the generated ACL; the CI gate only compares bytes against the same renderer, so the defect is invisible to the pipeline.
- deploy/egress-proxy.yaml:30 references a config.yaml the documented ConfigMap does not contain.
- The NetworkPolicy actually shipped in deploy/kubernetes.yaml:100-131 is CIDR+port only (443 out, private ranges excepted, DNS to kube-system) — correctly and explicitly described as such in docs/network-egress.md, but it means that until the proxy manifest is applied AND fixed, the network layer has no per-host control at all.
- docs/network-egress.md states the shipped NetworkPolicy 'permits DNS, ports 80/443'; deploy/kubernetes.yaml:112-115 permits TCP/443 only. Minor doc inaccuracy.

### Risk Description
This is the defence-in-depth layer that SEC-004 and SEC-005 both point at when their
own criteria fall short. It is shipped, generated, CI-gated and non-functional — the
worst combination, because every signal a reviewer would check says it works. An
operator applying `deploy/egress-proxy.yaml` gets a sidecar that either fails to
unmarshal the ACL or enforces an empty domain list, and in the meantime pinning is
disabled precisely because a proxy is configured (`api_client.py:158-164`). The net
effect of following the shipped manifests is *less* egress control than not following
them.

The shipped `deploy/kubernetes.yaml` NetworkPolicy is CIDR+port only, which is
correctly described as such in `docs/network-egress.md` — but it means that until the
proxy manifest is applied *and* fixed, the network layer has no per-host control at
all.

### Remediation
1. Fix the indentation at `render_egress_acl.py:25` — six spaces, so the entries nest
   under `allowed_domains`. Regenerate and commit.
2. Add a test that `yaml.safe_load`s the committed ACL and asserts
   `services[0]["allowed_domains"] == sorted(ALLOWED_HOSTS)`. A byte-comparison gate
   against the generator can only catch staleness; this is the class of bug it is
   structurally blind to.
3. Add the missing `config.yaml` to the ConfigMap, or drop the `--config-file` flag.
4. Correct `docs/network-egress.md`: it says the shipped NetworkPolicy permits ports
   80/443; `deploy/kubernetes.yaml:112-115` permits TCP/443 only.

### Effort Estimate
S (<1d)

### Relation to run `2026-07-27T125314-Z`
Recorded as closed. The generation pipeline is real; its output is invalid, and the gate is blind to that by construction.

### Auditor Notes
The brief asked me to verify the generation is real and the CI step exists.
Both are real — I ran the script and read the workflow. That is where a
surface reading would stop, and it is exactly what the file-level claim in
the previous remediation asserts.
Parsing the output tells a different story: the renderer emits the host list
at the wrong indent level, so the ACL that is supposed to carry the ten-host
network-layer allow-list parses with allowed_domains: null. The generation
pipeline is genuine but produces a non-functional artefact, and the CI gate
is structurally incapable of noticing because it diffs against its own
output. Combined with the missing config.yaml in the sidecar args, the
network-layer half of SEC-021 is not actually deliverable as shipped.
Code layer: solid pass. Network layer: present in intent, broken in fact.
Partial, with a one-line fix available.
