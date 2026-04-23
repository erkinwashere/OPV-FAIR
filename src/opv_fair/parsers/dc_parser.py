"""DC Degradation Chamber Parser."""
import re
import pandas as pd
from pathlib import Path

from opv_fair.parsers.base_parser import IV7Parser, RE_ANGLE, RE_SPECTRUM

RE_TILT = re.compile(r"(\d+)deg(?:ree)?", re.IGNORECASE)


class DCParser(IV7Parser):
    """
    Parses IV7 files from the degradation chamber (DC) system.
    Filenames encode tilt angle: deg_chamb_1sun_2_60deg.txt
    """
    SYSTEM = "DC"

    def parse_file(self, filepath, **kwargs):
        filepath = Path(filepath)
        measurements = super().parse_file(filepath)

        # Enrich: extract tilt angle from filename
        tilt_match = RE_TILT.search(filepath.stem)
        tilt_deg = int(tilt_match.group(1)) if tilt_match else None

        for m in measurements:
            if tilt_deg is not None:
                m.conditions.spectrum += f" | tilt={tilt_deg}°"

        return measurements


class DegradationTempParser:
    """
    Parser for temperature tracking CSV files.

    Format (DegradationTemp_27.01.csv):
      ,id,start,temp1..temp8
    """
    RE_TEMP_COL = re.compile(r"^temp\d+$")

    def parse_file(self, filepath: str | Path) -> pd.DataFrame:
        df = pd.read_csv(filepath, index_col=0)

        if "start" in df.columns:
            df["start"] = pd.to_datetime(df["start"], errors="coerce")

        temp_cols = [c for c in df.columns if self.RE_TEMP_COL.match(c)]

        if temp_cols:
            df["temp_mean_C"] = df[temp_cols].mean(axis=1)
            df["temp_std_C"]  = df[temp_cols].std(axis=1)
            df["temp_min_C"]  = df[temp_cols].min(axis=1)
            df["temp_max_C"]  = df[temp_cols].max(axis=1)

        return df


# NOMAD plugin hook
try:
    from nomad.parsing import MatchingParser

    class DCNomadParser(MatchingParser):
        def __init__(self):
            super().__init__(
                name="opv_fair/DCParser",
                code_name="OPV-DC",
                code_homepage="https://github.com/your-org/opv-fair",
                mainfile_mime_re=r"text/.*",
                mainfile_name_re=r".*deg_chamb.*\.txt$",
            )

        def parse(self, mainfile, archive, logger):
            parser = DCParser()
            measurements = parser.parse_file(mainfile)
            archive.m_setdefault("data")
            archive.data = {"measurements": [m.to_dict() for m in measurements[:100]]}

    m_parser = DCNomadParser()

except ImportError:
    m_parser = None
