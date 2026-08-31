"""Shared fixtures. The sample spreadsheets in this folder are longitudinal
olive-oil chemistry data (harvest campaigns 1992/93-1994/95 plus stored
"atrojado" oils); we use them as realistic inputs for every test."""

from __future__ import annotations

import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DATA_DIR = Path(__file__).parent


def _fix_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Transliterate accented Spanish column names to ASCII so downstream code
    can reference stable identifiers (e.g. ``CAMPAÑA`` -> ``CAMPANA``,
    ``DÍAS`` -> ``DIAS``)."""
    new = []
    for c in df.columns:
        if isinstance(c, str):
            c = unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode("ascii")
            c = " ".join(c.split()).strip()
        new.append(str(c))
    df = df.copy()
    df.columns = new
    return df


def load(name: str, sheet: str | int = 0) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        pytest.skip(f"sample data {name} not present")
    return _fix_headers(pd.read_excel(path, sheet_name=sheet))


@pytest.fixture(scope="session")
def ceras() -> pd.DataFrame:
    """29 x 18, has a 4-level CAMPANA factor and many numeric wax fractions."""
    return load("CERAS.XLS", "ceras")


@pytest.fixture(scope="session")
def fame() -> pd.DataFrame:
    """29 x 18 fatty-acid methyl esters; CAMPANA factor, SFA/MUFA/PUFA totals."""
    return load("FAME.XLS", "fame")


@pytest.fixture(scope="session")
def alcoholes() -> pd.DataFrame:
    return load("alcoholes.xls", "alcoholes")


@pytest.fixture(scope="session")
def esteroles() -> pd.DataFrame:
    return load("esteroles.xls", "esteroles")


@pytest.fixture(scope="session")
def hidrocarburos() -> pd.DataFrame:
    return load("hidrocarburos.xls", "hidrocarburos")


@pytest.fixture(scope="session")
def trigliceridos() -> pd.DataFrame:
    return load("trigliceridos.xls", "trigliceridos")


@pytest.fixture(scope="session")
def campaign_col(ceras) -> str:
    return next(c for c in ceras.columns if c.upper().startswith("CAMPA"))


@pytest.fixture(scope="session")
def two_group_ceras(ceras, campaign_col) -> pd.DataFrame:
    """CERAS restricted to the two largest campaigns -> a clean 2-level factor."""
    top2 = ceras[campaign_col].astype(str).value_counts().index[:2].tolist()
    return ceras[ceras[campaign_col].astype(str).isin(top2)].copy()


@pytest.fixture(scope="session")
def fame2(fame) -> pd.DataFrame:
    """FAME with a second crossed factor SEASON (early/late by median harvest
    day) so it supports a two-way ANOVA and a 2-D contingency table."""
    df = fame.copy()
    df["SEASON"] = np.where(df["TIME"] <= df["TIME"].median(), "early", "late")
    return df


@pytest.fixture(scope="session")
def rng() -> np.random.Generator:
    return np.random.default_rng(20260831)


@pytest.fixture(scope="session")
def normal_frame(rng) -> pd.DataFrame:
    """Deterministic normal data for exact-ish assertions."""
    return pd.DataFrame(
        {
            "x": rng.normal(10, 2, 200),
            "y": rng.normal(0, 1, 200),
            "g": rng.choice(["A", "B", "C"], 200),
            "g2": rng.choice(["yes", "no"], 200),
        }
    )
