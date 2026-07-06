"""
schemas.py — Pydantic models for request and response validation.

Implements strict boundaries, whitelists (Literal types), and custom
validators to prevent SQL Injection, XSS, and out-of-bounds parameter abuse.
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


# ── Whitelist Constants ──

# The 20 states from the training dataset.
# Odisha is mapped to Orissa (the dataset spelling) via a validator.
VALID_STATES = [
    "Andhra Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Orissa",
    "Punjab",
    "Rajasthan",
    "Tamil Nadu",
    "Telangana",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
]

StateName = Literal[
    "Andhra Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Orissa",
    "Odisha",  # Allowed in request, mapped to Orissa
    "Punjab",
    "Rajasthan",
    "Tamil Nadu",
    "Telangana",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
]

# The 11 soil type categories from the training dataset.
VALID_SOILS = [
    "ALFISOLS",
    "ARIDISOLS",
    "ENTISOLS",
    "INCEPTISOLS",
    "PSAMMENTS",
    "UDALFS",
    "UDUPTS/UDALFS",
    "UNKNOWN",
    "USTALF/USTOLLS",
    "VERTISOLS",
    "VRTIC SOILS",
]

SoilType = Literal[
    "ALFISOLS",
    "ARIDISOLS",
    "ENTISOLS",
    "INCEPTISOLS",
    "PSAMMENTS",
    "UDALFS",
    "UDUPTS/UDALFS",
    "UNKNOWN",
    "USTALF/USTOLLS",
    "VERTISOLS",
    "VRTIC SOILS",
]

# The 19 crops from the training dataset.
VALID_CROPS = [
    "BARLEY",
    "CASTOR",
    "CHICKPEA",
    "COTTON",
    "FINGER MILLET",
    "GROUNDNUT",
    "LINSEED",
    "MAIZE",
    "PEARL MILLET",
    "PIGEONPEA",
    "RAPESEED AND MUSTARD",
    "RICE",
    "SAFFLOWER",
    "SESAMUM",
    "SORGHUM",
    "SOYABEAN",
    "SUGARCANE",
    "SUNFLOWER",
    "WHEAT",
]

CropName = Literal[
    "BARLEY",
    "CASTOR",
    "CHICKPEA",
    "COTTON",
    "FINGER MILLET",
    "GROUNDNUT",
    "LINSEED",
    "MAIZE",
    "PEARL MILLET",
    "PIGEONPEA",
    "RAPESEED AND MUSTARD",
    "RICE",
    "SAFFLOWER",
    "SESAMUM",
    "SORGHUM",
    "SOYABEAN",
    "SUGARCANE",
    "SUNFLOWER",
    "WHEAT",
]


# ── Shared Models ──


class CropRecommendation(BaseModel):
    crop: str = Field(..., description="Crop name")
    expected_yield_kg_per_ha: float = Field(..., description="Expected crop yield in Kg/ha")
    max_potential_yield: float = Field(
        ..., description="Historical 95th percentile yield baseline in Kg/ha"
    )
    suitability_percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Weighted ecological suitability score (0-100%)"
    )


# ── Consumer API Models (/recommend) ──


class RecommendRequest(BaseModel):
    state: StateName = Field(..., description="Indian state name")
    district: Optional[str] = Field(
        None,
        max_length=100,
        description="District name (optional, if omitted historical state averages are used)",
    )
    soil_type: str = Field(..., description="Soil classification type")
    explain: bool = Field(False, description="Whether to call the LLM for advisory explanation")

    @field_validator("state")
    @classmethod
    def normalize_state(cls, v: str) -> str:
        # Standardize spelling of Odisha
        if v.strip().upper() == "ODISHA":
            return "Orissa"
        return v

    @field_validator("soil_type")
    @classmethod
    def validate_soil_type(cls, v: str) -> str:
        val = v.strip().upper()
        if val not in VALID_SOILS:
            raise ValueError(f"Invalid soil type. Must be one of: {', '.join(VALID_SOILS)}")
        return val

    @field_validator("district")
    @classmethod
    def sanitize_district(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        # Keep only letters, spaces, and hyphens
        val = "".join(char for char in v if char.isalpha() or char.isspace() or char == "-").strip()
        # Compress multiple spaces
        val = " ".join(val.split())
        if not val:
            return None
        return val


class RecommendResponse(BaseModel):
    status: str = "success"
    state: str
    district: Optional[str] = None
    recommendations: List[CropRecommendation]
    climate_source: str = Field(
        ..., description="Where rainfall data came from ('open-meteo' or 'historical')"
    )
    explanation: Optional[str] = None
    cached: bool
    latency_ms: float


# ── Integration API Models (/predict) ──


class PredictRequest(BaseModel):
    N: float = Field(..., ge=0.0, le=500.0, description="Nitrogen content (Kg/ha)")
    P: float = Field(..., ge=0.0, le=500.0, description="Phosphorus content (Kg/ha)")
    K: float = Field(..., ge=0.0, le=500.0, description="Potassium content (Kg/ha)")
    annual_rainfall: float = Field(..., ge=0.0, le=5000.0, description="Annual rainfall (mm)")
    kharif_rainfall: float = Field(
        ..., ge=0.0, le=5000.0, description="Kharif season rainfall (mm)"
    )
    rabi_rainfall: float = Field(..., ge=0.0, le=5000.0, description="Rabi season rainfall (mm)")
    irrigation_ratio: float = Field(..., ge=0.0, le=1.0, description="Irrigation ratio (0.0 - 1.0)")
    soil_type: str = Field(..., description="Soil classification type")
    state: StateName = Field(..., description="Indian state name")
    crop: Optional[str] = Field(
        None,
        description="Optional crop name. If specified, returns single crop yield. If None, runs full 19-crop simulation.",
    )
    explain: bool = Field(False, description="Whether to call the LLM for advisory explanation")

    @field_validator("state")
    @classmethod
    def normalize_state(cls, v: str) -> str:
        if v.strip().upper() == "ODISHA":
            return "Orissa"
        return v

    @field_validator("soil_type")
    @classmethod
    def validate_soil_type(cls, v: str) -> str:
        val = v.strip().upper()
        if val not in VALID_SOILS:
            raise ValueError(f"Invalid soil type. Must be one of: {', '.join(VALID_SOILS)}")
        return val

    @field_validator("crop")
    @classmethod
    def validate_crop(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        val = v.strip().upper()
        if val not in VALID_CROPS:
            raise ValueError(f"Invalid crop name. Must be one of: {', '.join(VALID_CROPS)}")
        return val


class PredictResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    predicted_yield: Optional[float] = Field(
        None, description="Predicted crop yield in Kg/ha (only set in single-crop mode)"
    )
    recommendations: Optional[List[CropRecommendation]] = Field(
        None, description="Scored recommendations (set when crop=None in request)"
    )
    unit: str = "Kg/ha"
    explanation: Optional[str] = None
    cached: bool
    latency_ms: float
    model_backend: str


# ── Ops API Models (/health) ──


class HealthResponse(BaseModel):
    status: str
    onnx_loaded: bool
    redis_connected: bool
    llm_available: bool

