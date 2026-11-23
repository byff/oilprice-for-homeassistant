"""Tests for the entity IDs of the oilprice integration."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


def _load_module(name: str, file_name: str):
    """Load a module of the integration directly."""
    project_root = Path(__file__).resolve().parents[1]
    oilprice_dir = project_root / "custom_components" / "oilprice"

    if "custom_components" not in sys.modules:
        custom_components_pkg = types.ModuleType("custom_components")
        custom_components_pkg.__path__ = [str(project_root / "custom_components")]
        sys.modules["custom_components"] = custom_components_pkg

    if "custom_components.oilprice" not in sys.modules:
        oilprice_pkg = types.ModuleType("custom_components.oilprice")
        oilprice_pkg.__path__ = [str(oilprice_dir)]
        sys.modules["custom_components.oilprice"] = oilprice_pkg

    spec = importlib.util.spec_from_file_location(
        f"custom_components.oilprice.{name}", oilprice_dir / file_name
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load custom_components.oilprice.{name}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[f"custom_components.oilprice.{name}"] = module
    spec.loader.exec_module(module)
    return module


const = _load_module("const", "const.py")


class RegionSlugTests(unittest.TestCase):
    """Tests for the slugs used in the entity IDs."""

    def test_every_region_has_a_slug(self) -> None:
        """Each known region has a pinned slug."""
        for region in const.REGIONS:
            self.assertIn(region, const.REGION_SLUGS)

    def test_slugs_are_unique(self) -> None:
        """No two regions may share a slug.

        Slugifying the Chinese region names gives both 山西 and 陕西 the slug
        "shan_xi", which makes the two regions share one entity ID.
        """
        slugs = list(const.REGION_SLUGS.values())
        duplicates = {slug for slug in slugs if slugs.count(slug) > 1}
        self.assertEqual(duplicates, set())

    def test_slugs_are_ascii(self) -> None:
        """The slugs end up in the entity IDs, so they stay ASCII."""
        for region, slug in const.REGION_SLUGS.items():
            self.assertTrue(slug.isascii(), f"{region} -> {slug}")
            self.assertTrue(slug.islower(), f"{region} -> {slug}")

    def test_unknown_region_falls_back_to_the_region_code(self) -> None:
        """An unknown region keeps its own code as the slug."""
        self.assertEqual(const.region_slug("unknown"), "unknown")

    def test_slugs_match_the_previous_slugify_output(self) -> None:
        """The entity IDs stay the same as in the previous versions.

        The entity IDs end up in the dashboards of the users, so they may not
        change. Only the slug of 陕西 differs, because it used to collide
        with the slug of 山西.
        """
        from slugify import slugify

        for region, name in const.REGIONS.items():
            previous = slugify(name, separator="_")
            current = const.REGION_SLUGS[region]
            if region == "shanxisheng":
                self.assertNotEqual(current, previous)
            else:
                self.assertEqual(current, previous, f"{region} -> {current}")


if __name__ == "__main__":
    unittest.main()
