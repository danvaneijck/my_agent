"""Tests for module manifests — ensure all modules have valid tool definitions.

These tests import each module's manifest and verify structural correctness:
tool names follow conventions, required fields are present, and parameter
types are valid.
"""

from __future__ import annotations

import importlib

import pytest

# All modules that have a manifest.py with a MANIFEST object.
# Add new modules here when they're created.
MODULE_MANIFESTS = [
    "modules.location.manifest",
    "modules.research.manifest",
    "modules.file_manager.manifest",
    "modules.code_executor.manifest",
    "modules.knowledge.manifest",
    "modules.scheduler.manifest",
    "modules.atlassian.manifest",
    "modules.claude_code.manifest",
    "modules.deployer.manifest",
    "modules.garmin.manifest",
    "modules.renpho_biometrics.manifest",
    "modules.injective.manifest",
]

VALID_PARAM_TYPES = {"string", "integer", "number", "boolean", "array", "object"}
VALID_PERMISSION_LEVELS = {"guest", "user", "admin", "owner"}


def _load_manifest(module_path: str):
    """Import a module and return its MANIFEST."""
    mod = importlib.import_module(module_path)
    return mod.MANIFEST


def _all_manifests():
    """Load all manifests, skipping those that fail to import."""
    results = []
    for path in MODULE_MANIFESTS:
        try:
            manifest = _load_manifest(path)
            results.append((path, manifest))
        except ImportError:
            # Module may not be installed in test environment — skip
            pass
    return results


# ===================================================================
# Parametrized tests
# ===================================================================


@pytest.mark.parametrize(
    "module_path,manifest",
    _all_manifests(),
    ids=[p for p, _ in _all_manifests()],
)
class TestManifestStructure:
    """Structural validation for module manifests."""

    def test_module_name_is_set(self, module_path, manifest):
        """Manifest must have a non-empty module_name."""
        assert manifest.module_name, f"{module_path}: module_name is empty"

    def test_has_description(self, module_path, manifest):
        """Manifest must have a description."""
        assert manifest.description, f"{module_path}: description is empty"

    def test_has_tools(self, module_path, manifest):
        """Manifest must define at least one tool."""
        assert len(manifest.tools) > 0, f"{module_path}: no tools defined"

    def test_tool_names_prefixed_with_module(self, module_path, manifest):
        """All tool names must start with 'module_name.'."""
        for tool in manifest.tools:
            assert tool.name.startswith(f"{manifest.module_name}."), (
                f"{module_path}: tool '{tool.name}' doesn't start with "
                f"'{manifest.module_name}.'"
            )

    def test_tool_names_have_two_parts(self, module_path, manifest):
        """Tool names must be 'module.action' format."""
        for tool in manifest.tools:
            parts = tool.name.split(".")
            assert len(parts) == 2, (
                f"{module_path}: tool '{tool.name}' should have exactly "
                f"one dot (module.action)"
            )

    def test_tools_have_descriptions(self, module_path, manifest):
        """Each tool must have a description."""
        for tool in manifest.tools:
            assert tool.description, (
                f"{module_path}: tool '{tool.name}' has empty description"
            )

    def test_parameter_types_are_valid(self, module_path, manifest):
        """Tool parameters must use valid type strings."""
        for tool in manifest.tools:
            for param in tool.parameters:
                assert param.type in VALID_PARAM_TYPES, (
                    f"{module_path}: tool '{tool.name}' param '{param.name}' "
                    f"has invalid type '{param.type}', expected one of "
                    f"{VALID_PARAM_TYPES}"
                )

    def test_parameters_have_descriptions(self, module_path, manifest):
        """Each parameter must have a description."""
        for tool in manifest.tools:
            for param in tool.parameters:
                assert param.description, (
                    f"{module_path}: tool '{tool.name}' param "
                    f"'{param.name}' has empty description"
                )

    def test_permission_levels_are_valid(self, module_path, manifest):
        """Tool permission levels must be recognized values."""
        for tool in manifest.tools:
            assert tool.required_permission in VALID_PERMISSION_LEVELS, (
                f"{module_path}: tool '{tool.name}' has invalid permission "
                f"'{tool.required_permission}', expected one of "
                f"{VALID_PERMISSION_LEVELS}"
            )

    def test_no_duplicate_tool_names(self, module_path, manifest):
        """No two tools in the same manifest should share a name."""
        names = [t.name for t in manifest.tools]
        assert len(names) == len(set(names)), (
            f"{module_path}: duplicate tool names found: "
            f"{[n for n in names if names.count(n) > 1]}"
        )

    def test_no_duplicate_parameter_names(self, module_path, manifest):
        """No tool should have duplicate parameter names."""
        for tool in manifest.tools:
            param_names = [p.name for p in tool.parameters]
            assert len(param_names) == len(set(param_names)), (
                f"{module_path}: tool '{tool.name}' has duplicate params: "
                f"{[n for n in param_names if param_names.count(n) > 1]}"
            )
