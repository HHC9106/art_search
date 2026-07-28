from __future__ import annotations

import importlib

from scraper.models import Listing
from scraper.sources_config import SourceConfig


class CustomAdapter:
    """Dispatches to a bespoke scraper/adapters/custom/<source_name>.py module,
    for the rare site too irregular for the generic rss/html/playwright adapters
    to express via parser_options. Each such module must expose collect(config)."""

    def collect(self, config: SourceConfig) -> list[Listing]:
        try:
            module = importlib.import_module(f"scraper.adapters.custom.{config.name}")
        except ImportError as exc:
            raise ValueError(
                f"Source '{config.name}' uses adapter: custom but no "
                f"scraper/adapters/custom/{config.name}.py module was found"
            ) from exc
        return module.collect(config)
