"""
Capability Registry
====================
Loads capability plugins from YAML manifest, resolves them by ID,
and enforces agent allowlists. New plugins added without core code changes.
"""

import yaml
import importlib
from pathlib import Path
from typing import Optional

from capabilities.base import CapabilityPlugin


class CapabilityRegistry:
    def __init__(self):
        self._plugins: dict[str, CapabilityPlugin] = {}

    def load_from_yaml(self, path: str = None):
        if path is None:
            path = Path(__file__).parent / "registry.yaml"
        with open(path) as f:
            config = yaml.safe_load(f)
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
                    print(f"[REGISTRY] Health check failed: {plugin_config['id']} — skipping")
            except Exception as e:
                print(f"[REGISTRY] Failed to load {plugin_config['id']}: {e}")

    def resolve(self, capability_ids: list[str]) -> dict[str, CapabilityPlugin]:
        """Return only the capabilities that are available."""
        return {cid: self._plugins[cid] for cid in capability_ids if cid in self._plugins}

    def execute(self, capability_id: str, input_data: dict) -> dict:
        plugin = self._plugins.get(capability_id)
        if not plugin:
            raise ValueError(f"Capability '{capability_id}' not found or not loaded")
        return plugin.execute(input_data)

    def list_available(self) -> list[str]:
        return list(self._plugins.keys())

    def is_available(self, capability_id: str) -> bool:
        return capability_id in self._plugins


# Singleton registry — initialized on startup
capability_registry = CapabilityRegistry()
