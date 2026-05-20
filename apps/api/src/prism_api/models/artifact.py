"""Artifact + derived-artifact models."""

import enum
import uuid
from typing import Any

from sqlalchemy import BigInteger, Enum, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from prism_api.models.base import Base, TimestampMixin


class ArtifactKind(enum.StrEnum):
    JUNIT_XML = "junit_xml"
    WAVEFORM_CSV = "waveform_csv"
    WAVEFORM_HDF5 = "waveform_hdf5"
    WAVEFORM_NPY = "waveform_npy"
    SPECTRUM_CSV = "spectrum_csv"
    SPECTRUM_TOUCHSTONE = "spectrum_touchstone"
    SPECTROGRAM = "spectrogram"
    WAV_AUDIO = "wav_audio"
    IMAGE_PNG = "image_png"
    LOG_TEXT = "log_text"
    OTHER_BINARY = "other_binary"


class DerivedKind(enum.StrEnum):
    FFT = "fft"
    THUMBNAIL = "thumbnail"


# Use JSONB on postgres, JSON elsewhere (tests run against SQLite)
_JSON = JSONB().with_variant(JSON(), "sqlite")


class Artifact(Base, TimestampMixin):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_type: Mapped[str] = mapped_column(
        String(16), nullable=False, index=True
    )  # run|suite|case
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[ArtifactKind] = mapped_column(
        Enum(ArtifactKind, native_enum=False), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False, default=dict)
    manifest_kind: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)


class DerivedArtifact(Base, TimestampMixin):
    __tablename__ = "derived_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_artifact_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[DerivedKind] = mapped_column(Enum(DerivedKind, native_enum=False), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    params_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
