"""L1 Solar Simulator Parser."""
from opv_fair.parsers.base_parser import IV7Parser


class L1Parser(IV7Parser):
    """
    Parses IV7 files from the L1 solar simulator system.
    Filenames typically contain: barcode_deg_IV7_YYMMDD-HHMMSS[_Nsuns].txt
    """
    SYSTEM = "L1"

    def parse_file(self, filepath, **kwargs):
        return super().parse_file(filepath)


# NOMAD plugin hook (used when installed as nomad.plugin entry point)
try:
    from nomad.parsing import MatchingParser

    class L1NomadParser(MatchingParser):
        def __init__(self):
            super().__init__(
                name="opv_fair/L1Parser",
                code_name="OPV-L1",
                code_homepage="https://github.com/your-org/opv-fair",
                mainfile_mime_re=r"text/.*",
                mainfile_name_re=r".*IV7.*\.txt$",
            )

        def parse(self, mainfile, archive, logger):
            parser = L1Parser()
            measurements = parser.parse_file(mainfile)
            # Attach to archive as raw JSON for now
            archive.m_setdefault("data")
            archive.data = {"measurements": [m.to_dict() for m in measurements[:100]]}

    m_parser = L1NomadParser()

except ImportError:
    m_parser = None  # standalone mode
