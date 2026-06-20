"""
Every price source adapter implements this interface, so the orchestrator
never needs to know which source it's talking to. Adding a new working
source means writing one of these and registering it in
config/sources.yaml — nothing else in the pipeline changes.
"""
from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd

REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


class SourceAdapter(ABC):
    name: str = "unnamed"

    @abstractmethod
    def fetch(self, ticker, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """
        ticker: a TickerConfig (pipeline.config.TickerConfig)

        Must return either None (no data / failure) or a DataFrame indexed
        by Date with at least REQUIRED_COLUMNS, dtypes float32, and no
        normalization left for the caller to do.
        """
        raise NotImplementedError

    def validate_schema(self, df: pd.DataFrame) -> None:
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(
                f"{self.name} adapter returned a dataframe missing columns: {missing}. "
                f"Every adapter must normalize to {REQUIRED_COLUMNS} before returning."
            )
