"""Dormant protected-human-console eligibility for one exact dynamic A.

No issuer, dispatcher, credential store or alternate Owner. The existing trusted
issuer is called only by ProductStandardControl after these predicates. Production
qualification reads a fixed administrator-controlled manifest and kernel identity;
ordinary IPC cannot supply a callback, SID assertion or approval boolean.
"""

import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from .models import canonical_json, digest, fields, integer, now, require
from .paths import no_reparse

SCHEMA = "protected-rod-a-only-v1"
CODE_ROOT = Path("C:/Program Files/GDCAE Operator")
STATE_ROOT = Path("C:/ProgramData/GDCAE Operator")
MANIFEST = STATE_ROOT / "config/rod-a-only.json"
ADMIN = "S-1-5-32-544"
SYSTEM = "S-1-5-18"
WRITE = 0x500D0156  # generic write/all + write/append/EA/attributes/delete/DACL/owner


def dynamic(plan):
    return plan.get("plan_schema") == "standard-managed-rod-single-v1"


def _bounded(path, maximum=65536):
    no_reparse(path)
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    current = path.stat()
    require(len(raw) == before.st_size <= maximum and all(
        getattr(before, k) == getattr(after, k) == getattr(current, k)
        for k in ("st_dev", "st_ino", "st_size", "st_mtime_ns")),
        "HIL_DEPLOYMENT_UNQUALIFIED", "Protected source changed or exceeded its bound")
    return raw


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "HIL_DEPLOYMENT_UNQUALIFIED", "Duplicate manifest field")
            result[key] = value
        return result
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)


def validate_manifest(value, context, plan, config):
    """Strict data check alone is never proof of protected identity/custody."""
    fields(value, ("schema", "context_digest", "project_instance_id", "plan_id", "plan_digest",
                   "scope_digest", "standard_config_digest", "issuer_sid", "research_sid",
                   "not_before", "expires_at", "code_files", "python_digest"))
    from .product_standard import scope
    require(dynamic(plan) and plan["rod_contract"]["phase"] == "A"
            and value["schema"] == SCHEMA
            and value["context_digest"] == context.context_digest
            and value["project_instance_id"] == context.project_instance_id
            and value["plan_id"] == plan["plan_id"] and value["plan_digest"] == plan["plan_digest"]
            and value["scope_digest"] == digest(scope(plan))
            and value["standard_config_digest"] == digest(config.value()),
            "HIL_SCOPE_MISMATCH", "Protected A manifest must bind the exact current Plan")
    for key in ("issuer_sid", "research_sid"):
        require(type(value[key]) is str and re.fullmatch(r"S-1-5-21-(?:[0-9]+-){3}[0-9]+", value[key]),
                "HIL_DEPLOYMENT_UNQUALIFIED", "Exact local principal required")
    require(value["issuer_sid"] != value["research_sid"], "HIL_DEPLOYMENT_UNQUALIFIED",
            "Agent and protected human issuer cannot share a principal")
    for key in ("not_before", "expires_at"):
        integer(value[key], 1)
    require(value["not_before"] <= now() < value["expires_at"] <= plan["expires_at"],
            "HIL_APPROVAL_EXPIRED", "Protected deployment window has expired")
    require(type(value["code_files"]) is dict, "HIL_DEPLOYMENT_UNQUALIFIED", "Code map required")
    for value_digest in (value["python_digest"], *value["code_files"].values()):
        require(type(value_digest) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", value_digest),
                "HIL_DEPLOYMENT_UNQUALIFIED", "Exact code byte digest required")
    return value


class WindowsCustody:
    """Read-only current-process token and effective access, never impersonates."""

    def __enter__(self):
        require(os.name == "nt", "HIL_DEPLOYMENT_UNQUALIFIED", "Windows qualification required")
        import win32api
        import win32con
        import win32security as security
        self.security = security
        try:
            thread = security.OpenThreadToken(win32api.GetCurrentThread(), win32con.TOKEN_QUERY, True)
        except Exception as exc:
            require(getattr(exc, "winerror", None) == 1008, "HIL_DEPLOYMENT_UNQUALIFIED",
                    "Cannot establish unimpersonated issuer context")
        else:
            thread.Close()
            require(False, "HIL_DEPLOYMENT_UNQUALIFIED", "Impersonated contexts are unsupported")
        self.token = security.OpenProcessToken(win32api.GetCurrentProcess(),
                                               win32con.TOKEN_QUERY | win32con.TOKEN_DUPLICATE)
        try:
            self.duplicate = security.DuplicateToken(self.token, security.SecurityImpersonation)
            user = security.GetTokenInformation(self.token, security.TokenUser)
            self.sid = security.ConvertSidToStringSid(user[0] if isinstance(user, tuple) else user)
            groups = security.GetTokenInformation(self.token, security.TokenGroups)
            self.administrator = (security.GetTokenInformation(self.token, security.TokenElevation)
                or security.GetTokenInformation(self.token, security.TokenElevationType) in (2, 3)
                or any(security.ConvertSidToStringSid(group) == ADMIN for group, _ in groups))
        except BaseException:
            if hasattr(self, "duplicate"):
                self.duplicate.Close()
            self.token.Close()
            raise
        return self

    def __exit__(self, *_args):
        self.duplicate.Close()
        self.token.Close()

    def check(self, path, writers, desired, *, private=False, write_mask=WRITE):
        no_reparse(path)
        s = self.security
        sd = s.GetNamedSecurityInfo(str(path), s.SE_FILE_OBJECT,
            s.OWNER_SECURITY_INFORMATION | s.GROUP_SECURITY_INFORMATION | s.DACL_SECURITY_INFORMATION)
        require(s.ConvertSidToStringSid(sd.GetSecurityDescriptorOwner()) in writers,
                "HIL_DEPLOYMENT_UNQUALIFIED", "Protected object owner is unqualified")
        acl = sd.GetSecurityDescriptorDacl()
        require(acl is not None, "HIL_DEPLOYMENT_UNQUALIFIED", "NULL DACL is forbidden")
        for i in range(acl.GetAceCount()):
            ace = acl.GetAce(i)
            require(ace[0][0] in (0, 1), "HIL_DEPLOYMENT_UNQUALIFIED", "Unsupported ACE type")
            if ace[0][0] == 0:
                sid = s.ConvertSidToStringSid(ace[-1])
                require(not (ace[1] & write_mask) or sid in writers,
                        "HIL_DEPLOYMENT_UNQUALIFIED", "Untrusted principal can change protected state")
                require(not private or sid in writers | {self.sid},
                        "HIL_DEPLOYMENT_UNQUALIFIED", "Protected capability/config readable by another principal")
        class Mapping(ctypes.Structure):
            _fields_ = [(key, wintypes.DWORD) for key in ("read", "write", "execute", "all")]
        mapping = Mapping(0x120089, 0x120116, 0x1200A0, 0x1F01FF)
        descriptor = ctypes.create_string_buffer(memoryview(sd).tobytes())
        privileges = ctypes.create_string_buffer(4096)
        length, granted, status = wintypes.DWORD(len(privileges)), wintypes.DWORD(), wintypes.BOOL()
        check = ctypes.WinDLL("advapi32", use_last_error=True).AccessCheck
        check.argtypes = [ctypes.c_void_p, wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(Mapping),
                          ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD),
                          ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.BOOL)]
        check.restype = wintypes.BOOL
        require(check(descriptor, int(self.duplicate), desired, ctypes.byref(mapping), privileges,
                      ctypes.byref(length), ctypes.byref(granted), ctypes.byref(status)) and status.value,
                "HIL_DEPLOYMENT_UNQUALIFIED", "Issuer effective access is not qualified")


def protected_context(context, plan, config):
    """Future protected deployment only. No caller-supplied qualification provider."""
    require(sys.flags.isolated == 1 and sys.dont_write_bytecode,
            "HIL_DEPLOYMENT_UNQUALIFIED", "Isolated no-bytecode protected Python required")
    no_reparse(MANIFEST)
    with WindowsCustody() as token:
        require(not token.administrator, "HIL_DEPLOYMENT_UNQUALIFIED", "Nonadministrator issuer required")
        for path in (CODE_ROOT, STATE_ROOT / "config", MANIFEST):
            token.check(path, {ADMIN, SYSTEM}, 0x120089, private=path != CODE_ROOT)
        trusted_installer = token.security.ConvertSidToStringSid(
            token.security.LookupAccountName(None, "NT SERVICE\\TrustedInstaller")[0])
        for parent in set(CODE_ROOT.parents) | set(STATE_ROOT.parents):
            token.check(parent, {ADMIN, SYSTEM, trusted_installer}, 0x120089,
                        write_mask=0x500D0040)
        value = validate_manifest(_json(_bounded(MANIFEST, 1048576)), context, plan, config)
        require(token.sid == value["issuer_sid"] and token.sid != value["research_sid"],
                "HIL_DEPLOYMENT_UNQUALIFIED", "Current kernel identity is not protected issuer")
        package = Path(__file__).resolve().parents[1]
        require(package.is_relative_to(CODE_ROOT)
                and Path(sys.executable).is_relative_to(CODE_ROOT)
                and all(Path(p).is_absolute() and Path(p).is_relative_to(CODE_ROOT)
                        for p in sys.path), "HIL_DEPLOYMENT_UNQUALIFIED", "Untrusted import/runtime root")
        for name in sys.path:
            path = Path(name)
            token.check(path if path.exists() else path.parent, {ADMIN, SYSTEM}, 0x120089)
        # Include Python, DLL/PYD/stdlib/dependencies and any bytecode, not merely
        # our package. Every directory is checked to prevent DELETE_CHILD swaps.
        for module in tuple(sys.modules.values()):
            origin = getattr(module, "__file__", None)
            if origin is not None:
                require(Path(origin).is_absolute() and Path(origin).is_relative_to(CODE_ROOT),
                        "HIL_DEPLOYMENT_UNQUALIFIED", "Loaded module outside protected runtime")
        paths = list(CODE_ROOT.rglob("*"))
        require(len(paths) <= 20000, "HIL_DEPLOYMENT_UNQUALIFIED", "Bounded complete runtime closure required")
        sources = {p.relative_to(CODE_ROOT).as_posix(): p for p in paths if p.is_file()}
        require(set(value["code_files"]) == set(sources),
                "HIL_DEPLOYMENT_UNQUALIFIED", "Exact complete installed source set required")
        for path in paths:
            token.check(path, {ADMIN, SYSTEM}, 0x120089)
        total = 0
        for name, path in sources.items():
            total += path.stat().st_size
            require(total <= 1073741824, "HIL_DEPLOYMENT_UNQUALIFIED", "Bounded runtime closure required")
            require("sha256:" + hashlib.sha256(_bounded(path, 67108864)).hexdigest()
                    == value["code_files"][name], "HIL_DEPLOYMENT_UNQUALIFIED", "Trusted code changed")
        token.check(Path(sys.executable), {ADMIN, SYSTEM}, 0x1200A9)
        require("sha256:" + hashlib.sha256(_bounded(Path(sys.executable), 33554432)).hexdigest()
                == value["python_digest"], "HIL_DEPLOYMENT_UNQUALIFIED", "Trusted runtime changed")
        for path in (Path(context.test_root), Path(plan["engineering"]), Path(plan["scratch"])):
            require(path.is_relative_to(STATE_ROOT), "HIL_DEPLOYMENT_UNQUALIFIED", "Protected state root required")
            token.check(path, {ADMIN, SYSTEM, token.sid}, 0x12019F, private=True)
            for parent in path.parents:
                if parent == STATE_ROOT:
                    token.check(parent, {ADMIN, SYSTEM, token.sid}, 0x120089, private=True)
                    break
                token.check(parent, {ADMIN, SYSTEM, token.sid}, 0x120089, private=True)
        token.check(STATE_ROOT, {ADMIN, SYSTEM}, 0x120089, private=True)
        state_paths = list(Path(context.test_root).rglob("*"))
        require(len(state_paths) <= 5000, "HIL_DEPLOYMENT_UNQUALIFIED", "Bounded protected state required")
        for path in state_paths:
            token.check(path, {ADMIN, SYSTEM, token.sid}, 0x120089, private=True)
        capability = Path(context.test_root) / "private/standard-operator.json"
        if capability.exists():
            token.check(capability, {ADMIN, SYSTEM, token.sid}, 0x120089, private=True)
        return {"manifest_digest": digest(value), "issuer_sid": token.sid,
                "not_before": value["not_before"], "expires_at": value["expires_at"]}


def qualified(service, plan, binding):
    value = protected_context(service.context, plan, service._standard_backend.config)
    require(binding.get("authority_digest") == value["manifest_digest"],
            "HIL_DEPLOYMENT_UNQUALIFIED", "Exact protected provisioning required")
    return value


def decision_namespace(context, plan):
    return canonical_json([context.project_instance_id, "protected_rod_A_decision", plan["plan_id"]])


def require_decision(service, conn, plan, binding):
    qualification = qualified(service, plan, binding)
    row = conn.execute("SELECT request_digest,body FROM management_receipts WHERE namespace=? LIMIT 2",
                       (decision_namespace(service.context, plan),)).fetchall()
    require(len(row) == 1, "HIL_DECISION_REQUIRED", "One exact protected human decision required")
    value = json.loads(row[0][1])
    from .product_standard import scope
    require(row[0][0] == digest(value) and value["schema"] == "protected-rod-A-decision-v1"
            and value["decision"] == "APPROVE_EXACT"
            and value["plan_digest"] == plan["plan_digest"]
            and value["scope_digest"] == digest(scope(plan))
            and value["authority_digest"] == qualification["manifest_digest"]
            and value["issuer_sid"] == qualification["issuer_sid"]
            and value["owner_id"] == service.store._session.owner_id
            and value["not_before"] <= now() < value["expires_at"],
            "HIL_DECISION_DENIED", "Human decision is denied, expired or inconsistent")
    return value
