"""
Abstract base class for ALL data collectors in the Dubai Digital Twin.

Every collector (weather, traffic, energy, etc.) inherits from this class
and MUST implement the fetch() method. The run() method is the only
method external code should ever call — it handles the full pipeline:
    fetch() → validate() → save() → return

Design Decisions:
    1. ABC enforces the contract — missing fetch() = immediate crash
    2. Retry logic lives here — all collectors get it for free
    3. Logging is pre-configured — consistent format across all collectors
    4. save() writes CSV — simple, human-readable for debugging
    5. validate() catches bad data at the boundary — not 3 steps later

Teaching Note:
    This pattern is called the "Template Method" design pattern.
    The base class defines the skeleton of the algorithm (run),
    and subclasses fill in the specific step (fetch).
"""

import abc
import time
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)
import logging

from dubaidigitaltwin.config import settings


class BaseCollector(abc.ABC):
    """
    Abstract base class for all data collectors.

    Subclasses MUST implement:
        fetch(self) -> pd.DataFrame

    Subclasses get for FREE:
        save()      → saves DataFrame to CSV
        validate()  → checks DataFrame is not empty and has 'timestamp'
        run()       → fetch + validate + save + return
        self.logger → pre-configured logger with collector name
    """

    def __init__(
        self,
        name: str,
        output_dir: Optional[Path] = None,
        is_synthetic: bool = False,
    ):
        """
        Args:
            name        : Short identifier e.g. "weather", "traffic"
            output_dir  : Override the default save directory
            is_synthetic: True = data is generated, not from a real API
        """
        self.name = name
        self.is_synthetic = is_synthetic

        # ── Choose output directory ───────────────────────────────────────────
        # Synthetic data goes to data/synthetic/<name>/
        # Real data goes to data/raw/<name>/
        if output_dir is not None:
            self.output_dir = output_dir
        elif is_synthetic:
            self.output_dir = settings.synthetic_data_dir / name
        else:
            self.output_dir = settings.raw_data_dir / name

        # Create the directory now — so save() never fails on a missing folder
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # ── Logger setup ──────────────────────────────────────────────────────
        # bind() attaches extra context to every log message from this collector
        # Log output will look like: "weather | Fetching data..."
        self.logger = logger.bind(collector=self.name)

        # ── Warn clearly if synthetic ─────────────────────────────────────────
        # We always want synthetic data to be visible in logs
        if self.is_synthetic:
            self.logger.warning(
                f" SYNTHETIC DATA — [{self.name.upper()}] "
                f"This is generated data, not real sensor readings."
            )

    # ── Abstract Method ───────────────────────────────────────────────────────
    # The @abc.abstractmethod decorator makes this method REQUIRED.
    # Any class that inherits from BaseCollector and doesn't implement fetch()
    # will raise: TypeError: Can't instantiate abstract class ... with abstract method fetch
    @abc.abstractmethod
    def fetch(self) -> pd.DataFrame:
        """
        Fetch or generate data.

        MUST be implemented by every subclass.

        Returns:
            pd.DataFrame with at minimum these columns:
                - timestamp  (datetime)
                - source     (str, e.g. "open-meteo" or "synthetic")
                - data_type  (str, either "REAL" or "SYNTHETIC")
        """
        raise NotImplementedError(
            f"Subclass '{self.__class__.__name__}' must implement fetch()"
        )

    # ── Concrete Methods (free for all subclasses) ────────────────────────────

    def validate(self, df: pd.DataFrame) -> bool:
        """
        Validate that the fetched DataFrame meets minimum requirements.

        Checks:
            1. DataFrame is not None and not empty
            2. Has a 'timestamp' column
            3. Has a 'data_type' column (REAL or SYNTHETIC)

        Why validate here?
            Catching bad data at the source is much cheaper than
            discovering it 3 steps later during model training.

        Args:
            df: DataFrame to validate

        Returns:
            True if valid

        Raises:
            ValueError: with a clear message describing what's wrong
        """
        # Check 1 — not empty
        if df is None or df.empty:
            raise ValueError(
                f"[{self.name}] fetch() returned an empty DataFrame. "
                f"Check the API connection or synthetic generator."
            )

        # Check 2 — has timestamp column
        if "timestamp" not in df.columns:
            raise ValueError(
                f"[{self.name}] Missing required column: 'timestamp'. "
                f"Columns present: {list(df.columns)}"
            )

        # Check 3 — has data_type column (REAL or SYNTHETIC)
        if "data_type" not in df.columns:
            raise ValueError(
                f"[{self.name}] Missing required column: 'data_type'. "
                f"Every collector must label data as REAL or SYNTHETIC."
            )

        # Check 4 — no completely empty timestamp values
        null_ts = df["timestamp"].isnull().sum()
        if null_ts > 0:
            self.logger.warning(
                f"[{self.name}] {null_ts} null timestamps found — "
                f"these rows will cause issues in ML training."
            )

        self.logger.debug(
            f"[{self.name}] Validation passed — "
            f"{len(df):,} rows, {len(df.columns)} columns"
        )
        return True

    def save(
        self,
        df: pd.DataFrame,
        filename: Optional[str] = None,
    ) -> Path:
        """
        Save DataFrame to a CSV file in the output directory.

        Why CSV for raw data?
            - Human readable — open in Excel for quick checks
            - No schema required (unlike Parquet or databases)
            - Universal — any tool can read it
            In production, you would use Parquet on S3/Blob storage
            for performance. We use CSV here for learning clarity.

        Args:
            df      : DataFrame to save
            filename: Optional custom name.
                      Default: "<name>_YYYYMMDD_HHMMSS.csv"

        Returns:
            Path: Absolute path of the saved file
        """
        if filename is None:
            # Timestamp in filename = never accidentally overwrite old data
            ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.name}_{ts}.csv"

        filepath = self.output_dir / filename

        # index=False → don't write the DataFrame row numbers as a column
        df.to_csv(filepath, index=False)

        self.logger.success(
            f"Saved {len(df):,} rows → {filepath}"
        )
        return filepath

    def run(self) -> pd.DataFrame:
        """
        Execute the full data collection pipeline.

        Pipeline:
            1. fetch()    → get data from API or generate it
            2. validate() → check it meets minimum requirements
            3. save()     → write to CSV
            4. return df  → so caller can use data immediately

        This is the ONLY method external code should call:
            df = WeatherCollector().run()

        Returns:
            pd.DataFrame: The collected/generated data

        Raises:
            Any exception from fetch() or validate() propagates up
        """
        self.logger.info(f"Starting [{self.name}] collector...")

        # Record start time to measure how long collection takes
        start = time.time()

        try:
            # Step 1 — Fetch
            df = self.fetch()

            # Step 2 — Validate
            self.validate(df)

            # Step 3 — Save
            self.save(df)

            # Step 4 — Report and return
            elapsed = time.time() - start
            self.logger.info(
                f"[{self.name}] done in {elapsed:.1f}s — "
                f"{len(df):,} records collected"
            )
            return df

        except Exception as e:
            elapsed = time.time() - start
            self.logger.error(
                f"[{self.name}] FAILED after {elapsed:.1f}s: {e}"
            )
            # Re-raise so the caller knows something went wrong
            raise

    def __repr__(self) -> str:
        """
        String representation — useful when debugging in a Python shell.
        e.g. print(collector) → WeatherCollector(name=weather, synthetic=False)
        """
        return (
            f"{self.__class__.__name__}("
            f"name={self.name}, "
            f"synthetic={self.is_synthetic}, "
            f"output_dir={self.output_dir})"
        )