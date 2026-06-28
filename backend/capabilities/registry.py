"""
Capability Registry
===================
Loads capability plugins from the YAML manifest, resolves them by ID,
and enforces agent allowlists.
"""

import importlib
from pathlib import Path

import yaml

from capabilities.base import CapabilityPlugin


class CapabilityRegistry:
    def __init__(self):
        self._plugins: dict[str, CapabilityPlugin] = {}

    def _ensure_loaded(self):
        """Lazily load capabilities if startup has not populated the registry yet."""
        if not self._plugins:
            self.load_from_yaml()

    def load_from_yaml(self, path: str | None = None):
        if path is None:
            path = Path(__file__).parent / "registry.yaml"

        with open(path, encoding="utf-8") as file:
            config = yaml.safe_load(file)

        for plugin_config in config.get("plugins", []):
            if not plugin_config.get("enabled", True):
                continue

            try:
                module = importlib.import_module(plugin_config["module"])
                cls = getattr(module, plugin_config["class"])
                instance = cls()
                if instance.health_check():
                    self._plugins[plugin_config["id"]] = instance
                    print(f"[REGISTRY] Loaded: {plugin_config['id']}")
                else:
                    print(f"[REGISTRY] Health check failed: {plugin_config['id']} - skipping")
            except Exception as exc:
                print(f"[REGISTRY] Failed to load {plugin_config['id']}: {exc}")

    def resolve(self, capability_ids: list[str]) -> dict[str, CapabilityPlugin]:
        self._ensure_loaded()
        return {cap_id: self._plugins[cap_id] for cap_id in capability_ids if cap_id in self._plugins}

    def execute(self, capability_id: str, input_data: dict) -> dict:
        self._ensure_loaded()
        plugin = self._plugins.get(capability_id)
        if not plugin:
            raise ValueError(f"Capability '{capability_id}' not found or not loaded")
        return plugin.execute(input_data)

    def list_available(self) -> list[str]:
        self._ensure_loaded()
        return list(self._plugins.keys())

    def is_available(self, capability_id: str) -> bool:
        self._ensure_loaded()
        return capability_id in self._plugins

    def get_catalogue(self) -> list[dict]:
        """Return a structured catalogue of all loaded capabilities."""
        self._ensure_loaded()
        catalogue = []
        for cap_id, plugin in self._plugins.items():
            category = cap_id.split(".")[0] if "." in cap_id else "general"
            catalogue.append({
                "id": cap_id,
                "display_name": plugin.display_name,
                "description": plugin.description,
                "category": category,
            })
        catalogue.sort(key=lambda item: (item["category"], item["id"]))
        return catalogue

    def list_by_category(self, category: str) -> list[str]:
        self._ensure_loaded()
        return [cap_id for cap_id in self._plugins if cap_id.startswith(f"{category}.")]

    def get_catalogue_text(self) -> str:
        catalogue = self.get_catalogue()
        if not catalogue:
            return "No capabilities currently loaded."

        lines = []
        current_category = None
        for item in catalogue:
            if item["category"] != current_category:
                current_category = item["category"]
                lines.append(f"\n[{current_category.upper()}]")
            lines.append(f"  - {item['id']}: {item['description']}")
        return "\n".join(lines)


capability_registry = CapabilityRegistry()
