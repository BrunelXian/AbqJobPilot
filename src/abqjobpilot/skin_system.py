"""Safe, data-only ttk Skin loader. Skin directories never become Python code."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import tempfile
import re
import tkinter as tk
from tkinter import ttk

SKIN_API_VERSION = "1.0.0"
_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_SKIN_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
_COLORS = frozenset({"background", "surface", "foreground", "muted", "accent", "accent_foreground", "border", "selected_background", "selected_foreground"})
_LAYOUT = frozenset({"compact_toolbar", "toolbar_button_pad", "toolbar_button_width"})


class SkinError(ValueError):
    """A user-actionable error in a declarative Skin package."""


@dataclass(frozen=True)
class Skin:
    skin_id: str
    version: str
    api_version: str
    theme: dict[str, str]
    resources: dict[str, object]
    layout: dict[str, object]
    manifest_path: Path


DEFAULT_THEME = {
    "background": "#f4f7fb", "surface": "#ffffff", "foreground": "#172033",
    "muted": "#64748b", "accent": "#2563eb", "accent_foreground": "#ffffff",
    "border": "#d9e2ef", "selected_background": "#2563eb", "selected_foreground": "#ffffff",
}


def _version(value: object, label: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not _VERSION.fullmatch(value):
        raise SkinError(f"{label} must use numeric X.Y.Z version syntax")
    return tuple(int(part) for part in value.split("."))


def _inside(root: Path, relative: object, label: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise SkinError(f"{label} must be a relative resource path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise SkinError(f"{label} escapes the Skin directory")
    return path


class SkinLoader:
    """Loads JSON manifests and bounded built-in resource types only."""
    def __init__(self, skins_root: str | Path, *, extra_roots=(), api_version: str = SKIN_API_VERSION):
        self.skins_root = Path(skins_root).resolve()
        self.extra_roots = tuple(Path(root).resolve() for root in extra_roots)
        self.api_version = api_version
        _version(api_version, "skin API version")

    def load(self, skin_id: str) -> Skin:
        if not isinstance(skin_id, str) or not _SKIN_ID.fullmatch(skin_id):
            raise SkinError("skin_id contains unsupported characters")
        roots = self.extra_roots + (self.skins_root,)
        root = next(((base / skin_id).resolve() for base in roots
                     if (base / skin_id).resolve().is_relative_to(base) and (base / skin_id).is_dir()), None)
        if root is None:
            raise SkinError(f"Skin '{skin_id}' is missing")
        manifest_path = root / "manifest.json"
        try:
            raw = manifest_path.read_bytes()
            if len(raw) > 65536:
                raise SkinError("manifest.json exceeds 64 KiB")
            data = json.loads(raw.decode("utf-8"))
        except SkinError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SkinError(f"cannot read manifest.json: {exc.__class__.__name__}") from exc
        required = {"skin_id", "skin_version", "skin_api_version", "theme", "resources", "compatibility"}
        if not isinstance(data, dict) or set(data) != required and set(data) != required | {"layout"}:
            raise SkinError("manifest must contain the documented keys only")
        if data["skin_id"] != skin_id:
            raise SkinError("manifest skin_id does not match its directory")
        _version(data["skin_version"], "skin_version")
        if data["skin_api_version"] != self.api_version:
            raise SkinError(f"Skin API mismatch: requires {data['skin_api_version']}, host provides {self.api_version}")
        compatibility = data["compatibility"]
        if not isinstance(compatibility, dict) or set(compatibility) != {"minimum", "maximum"}:
            raise SkinError("compatibility must declare minimum and maximum Skin API versions")
        minimum = _version(compatibility["minimum"], "compatibility.minimum")
        maximum = _version(compatibility["maximum"], "compatibility.maximum")
        current = _version(self.api_version, "Skin API version")
        if minimum > maximum or not minimum <= current <= maximum:
            raise SkinError("Skin API is outside the declared compatibility range")
        theme = data["theme"]
        if not isinstance(theme, dict) or not set(theme) <= _COLORS:
            raise SkinError("theme may define only supported color tokens")
        merged_theme = {**DEFAULT_THEME, **theme}
        for name, color in merged_theme.items():
            if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                raise SkinError(f"theme.{name} must be a six-digit hex color")
        resources = data["resources"]
        if not isinstance(resources, dict) or set(resources) - {"icon_pack", "font_family", "font_size"}:
            raise SkinError("resources may define only icon_pack, font_family, and font_size")
        resources = {"icon_pack": "default", "font_family": "Segoe UI", "font_size": 10, **resources}
        if resources["icon_pack"] != "default":
            icon_dir = _inside(root, resources["icon_pack"], "resources.icon_pack")
            if not icon_dir.is_dir() or not all(p.is_file() and p.suffix.lower() in {".png", ".gif"} for p in icon_dir.iterdir()):
                raise SkinError("icon_pack must be a directory containing only PNG or GIF files")
        if not isinstance(resources["font_family"], str) or not 1 <= len(resources["font_family"]) <= 64:
            raise SkinError("resources.font_family is invalid")
        if isinstance(resources["font_size"], bool) or not isinstance(resources["font_size"], int) or not 8 <= resources["font_size"] <= 24:
            raise SkinError("resources.font_size must be an integer from 8 to 24")
        layout = data.get("layout", {})
        if not isinstance(layout, dict) or set(layout) - _LAYOUT:
            raise SkinError("layout contains unsupported keys")
        if "compact_toolbar" in layout and not isinstance(layout["compact_toolbar"], bool):
            raise SkinError("layout.compact_toolbar must be boolean")
        for name in ("toolbar_button_pad", "toolbar_button_width"):
            if name in layout and (isinstance(layout[name], bool) or not isinstance(layout[name], int) or not 0 <= layout[name] <= 32):
                raise SkinError(f"layout.{name} must be an integer from 0 to 32")
        # No Python, Tcl, scripts, or executable callbacks are read or imported.
        return Skin(skin_id, data["skin_version"], self.api_version, merged_theme, resources, dict(layout), manifest_path)

    def load_or_default(self, requested: str) -> tuple[Skin, str | None]:
        try:
            return self.load(requested), None
        except SkinError as exc:
            if requested == "default":
                raise
            return self.load("default"), f"Skin '{requested}' unavailable ({exc}); using default."

    def available_skin_ids(self) -> list[str]:
        """List manifest-bearing ids from user installs first, then bundled defaults."""
        found = []
        for base in self.extra_roots + (self.skins_root,):
            if not base.is_dir():
                continue
            for child in base.iterdir():
                if child.is_dir() and _SKIN_ID.fullmatch(child.name) and (child / "manifest.json").is_file():
                    try:
                        self.load(child.name)
                    except SkinError:
                        continue
                    if child.name not in found:
                        found.append(child.name)
        return found


def install_skin(source_dir: str | Path, destination_root: str | Path) -> str:
    """Install only a validated manifest and optional image pack."""
    source = Path(source_dir)
    if source.is_symlink() or not source.is_dir():
        raise SkinError("Skin source must be a regular directory")
    source = source.resolve()
    skin_id = source.name
    SkinLoader(source.parent).load(skin_id)
    target_root = Path(destination_root).resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    target = target_root / skin_id
    if target.exists():
        raise SkinError(f"Skin '{skin_id}' is already installed")
    stage = Path(tempfile.mkdtemp(prefix=".skin-install-", dir=target_root))
    total = 0
    try:
        manifest = source / "manifest.json"
        if manifest.is_symlink():
            raise SkinError("manifest.json cannot be a link")
        shutil.copyfile(manifest, stage / "manifest.json")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        icon_pack = data.get("resources", {}).get("icon_pack", "default")
        if icon_pack != "default":
            icon_source = _inside(source, icon_pack, "resources.icon_pack")
            for path in icon_source.rglob("*"):
                if path.is_symlink():
                    raise SkinError("Skin resources cannot contain links")
                if path.is_dir():
                    continue
                if path.suffix.lower() not in {".png", ".gif"}:
                    raise SkinError("Only PNG/GIF Skin image assets can be installed")
                total += path.stat().st_size
                if total > 10 * 1024 * 1024:
                    raise SkinError("Skin image assets exceed 10 MiB")
                relative = path.relative_to(source)
                destination = stage / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
        os.replace(stage, target)
        return skin_id
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def apply_skin(root: tk.Misc, skin: Skin, *, appearance: str = "light") -> None:
    """Apply supported ttk palette tokens. Dark mode is an app-level palette transform."""
    if appearance not in {"light", "dark"}:
        raise ValueError("appearance must be light or dark")
    palette = dict(skin.theme)
    if appearance == "dark":
        palette.update({"background": "#171a21", "surface": "#222733", "foreground": "#e8edf5",
                        "muted": "#a5b0c0", "border": "#384150", "selected_background": palette["accent"],
                        "selected_foreground": "#ffffff"})
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(".", background=palette["background"], foreground=palette["foreground"],
                    font=(skin.resources["font_family"], skin.resources["font_size"]))
    style.configure("TFrame", background=palette["background"])
    style.configure("TLabel", background=palette["background"], foreground=palette["foreground"])
    style.configure("TLabelframe", background=palette["background"], foreground=palette["foreground"])
    style.configure("TLabelframe.Label", background=palette["background"], foreground=palette["foreground"])
    style.configure("TButton", background=palette["surface"], foreground=palette["foreground"],
                    padding=(skin.layout.get("toolbar_button_pad", 6), 3))
    style.map("TButton", background=[("disabled", palette["background"]), ("active", palette["border"])],
              foreground=[("disabled", palette["muted"])])
    style.configure("TMenubutton", background=palette["surface"], foreground=palette["foreground"],
                    arrowcolor=palette["foreground"])
    style.map("TMenubutton", background=[("active", palette["border"])])
    style.configure("TCombobox", fieldbackground=palette["surface"], background=palette["surface"],
                    foreground=palette["foreground"], arrowcolor=palette["foreground"])
    style.map("TCombobox", fieldbackground=[("readonly", palette["surface"])],
              foreground=[("disabled", palette["muted"])])
    style.configure("TEntry", fieldbackground=palette["surface"], foreground=palette["foreground"])
    style.configure("Treeview", background=palette["surface"], fieldbackground=palette["surface"],
                    foreground=palette["foreground"], bordercolor=palette["border"])
    style.configure("Treeview.Heading", background=palette["background"], foreground=palette["foreground"])
    style.map("Treeview", background=[("selected", palette["selected_background"])],
              foreground=[("selected", palette["selected_foreground"])])
    style.configure("Cockpit.Treeview", background=palette["surface"], fieldbackground=palette["surface"],
                    foreground=palette["foreground"], rowheight=27)
    style.configure("Cockpit.Treeview.Heading", background=palette["background"], foreground=palette["foreground"])
    style.map("Cockpit.Treeview", background=[("selected", palette["selected_background"])],
              foreground=[("selected", palette["selected_foreground"])])

    def recolor_text(parent):
        for child in parent.winfo_children():
            if child.winfo_class() == "Canvas":
                child.configure(background=palette["background"],
                                highlightbackground=palette["background"])
            if child.winfo_class() in {"Text", "Entry", "Listbox"}:
                try:
                    child.configure(background=palette["surface"], foreground=palette["foreground"],
                                    insertbackground=palette["foreground"])
                except tk.TclError:
                    pass
            recolor_text(child)
    try:
        recolor_text(root)
    except tk.TclError:
        pass
