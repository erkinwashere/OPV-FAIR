"""
OPV Degradation MetaInfo Schema
--------------------------------
Defines NOMAD Section + Quantity objects for OPV IV parameters.
Units follow SI via Pint (NOMAD built-in).
"""

try:
    from nomad.metainfo import (
        Package, Section, Quantity, SubSection, MEnum
    )
    from nomad.datamodel import EntryArchive
    NOMAD_AVAILABLE = True
except ImportError:
    NOMAD_AVAILABLE = False

# ── Standalone dataclasses (work without nomad-lab installed) ──────────────
from dataclasses import dataclass, field
import numpy as np


@dataclass
class IVCurveData:
    voltage_V: np.ndarray = field(default_factory=lambda: np.array([]))
    current_density_mA_cm2: np.ndarray = field(default_factory=lambda: np.array([]))


@dataclass
class PVParameters:
    """Photovoltaic performance parameters — standard OPV quantities."""
    Jsc_mA_cm2: float = float("nan")   # Short-circuit current density
    Voc_V: float = float("nan")         # Open-circuit voltage
    FF: float = float("nan")            # Fill factor (dimensionless, 0–1)
    PCE_percent: float = float("nan")   # Power conversion efficiency
    Pmax_mW: float = float("nan")       # Maximum power
    Vmpp_V: float = float("nan")        # Voltage at max power point
    Rs_ohm_cm2: float = float("nan")   # Series resistance
    Rp_ohm_cm2: float = float("nan")   # Parallel (shunt) resistance
    area_cm2: float = float("nan")      # Active area


@dataclass
class MeasurementConditions:
    temperature_C: float = float("nan")
    humidity_percent: float = float("nan")
    spectrum: str = ""                  # e.g. "AM1.5", "5sun"
    sweep_direction: str = ""           # "forward" / "reverse"
    illumination_intensity: float = float("nan")  # sun equivalents


@dataclass
class OPVMeasurement:
    """
    Single IV sweep of one OPV pixel.

    Identifiers
    -----------
    barcode : device barcode (persistent ID in lab)
    pixel   : pixel index on substrate
    system  : 'L1' (solar simulator) | 'DC' (degradation chamber)
    """
    barcode: str = ""
    pixel: str = ""
    system: str = ""                    # "L1" | "DC"
    timestamp_s: float = float("nan")   # seconds since epoch or relative
    source_file: str = ""

    pv: PVParameters = field(default_factory=PVParameters)
    conditions: MeasurementConditions = field(default_factory=MeasurementConditions)
    iv_curve: IVCurveData = field(default_factory=IVCurveData)

    def uid(self) -> str:
        """Persistent identifier: barcode + pixel + timestamp + sweep."""
        import hashlib
        raw = f"{self.barcode}_{self.pixel}_{self.timestamp_s}_{self.conditions.sweep_direction}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "uid": self.uid(),
            "barcode": self.barcode,
            "pixel": self.pixel,
            "system": self.system,
            "timestamp_s": self.timestamp_s,
            "source_file": self.source_file,
            "pv": {
                "Jsc_mA_cm2": self.pv.Jsc_mA_cm2,
                "Voc_V": self.pv.Voc_V,
                "FF": self.pv.FF,
                "PCE_percent": self.pv.PCE_percent,
                "Pmax_mW": self.pv.Pmax_mW,
                "Vmpp_V": self.pv.Vmpp_V,
                "Rs_ohm_cm2": self.pv.Rs_ohm_cm2,
                "Rp_ohm_cm2": self.pv.Rp_ohm_cm2,
                "area_cm2": self.pv.area_cm2,
            },
            "conditions": {
                "temperature_C": self.conditions.temperature_C,
                "humidity_percent": self.conditions.humidity_percent,
                "spectrum": self.conditions.spectrum,
                "sweep_direction": self.conditions.sweep_direction,
            },
            "iv_curve": {
                "voltage_V": self.iv_curve.voltage_V.tolist(),
                "current_density_mA_cm2": self.iv_curve.current_density_mA_cm2.tolist(),
            },
        }


# ── NOMAD MetaInfo (only when nomad-lab is installed) ─────────────────────
if NOMAD_AVAILABLE:
    m_package = Package(name="opv_fair")

    class NomadPVParameters(Section):
        m_def = Section(label="PV Parameters")
        Jsc = Quantity(type=float, unit="mA/cm^2",   description="Short-circuit current density")
        Voc = Quantity(type=float, unit="V",          description="Open-circuit voltage")
        FF  = Quantity(type=float,                    description="Fill factor (0–1)")
        PCE = Quantity(type=float, unit="",           description="Power conversion efficiency (%)")
        Pmax = Quantity(type=float, unit="mW",        description="Maximum power output")
        Vmpp = Quantity(type=float, unit="V",         description="Voltage at max power point")
        Rs  = Quantity(type=float, unit="ohm*cm^2",  description="Series resistance")
        Rp  = Quantity(type=float, unit="ohm*cm^2",  description="Shunt resistance")
        area = Quantity(type=float, unit="cm^2",     description="Active area")

    class NomadOPVEntry(Section):
        m_def = Section(label="OPV IV Measurement")
        barcode   = Quantity(type=str,   description="Device barcode (persistent lab ID)")
        pixel     = Quantity(type=str,   description="Pixel index")
        system    = Quantity(type=MEnum("L1", "DC"), description="Measurement system")
        timestamp = Quantity(type=float, unit="s",   description="Timestamp")
        spectrum  = Quantity(type=str,               description="Illumination spectrum")
        temperature = Quantity(type=float, unit="°C", description="Cell temperature")
        humidity    = Quantity(type=float, unit="",   description="Relative humidity (%)")
        sweep_direction = Quantity(type=MEnum("forward", "reverse", "unknown"))

        pv_params = SubSection(sub_section=NomadPVParameters)

    m_package.__init_metainfo__()
else:
    m_package = None  # fallback: schema only used as dataclass
