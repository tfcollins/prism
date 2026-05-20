"""Artifact endpoints: metadata, download, waveform JSON, FFT JSON."""

from __future__ import annotations

import io
from pathlib import PurePosixPath

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from prism_api.config import Settings
from prism_api.deps import current_user, get_settings_dep, session_dep
from prism_api.dsp.downsample import downsample_for_plot
from prism_api.dsp.fft import FFTParams, compute_fft, params_hash
from prism_api.dsp.spectrum_metrics import channel_metrics, find_spurs
from prism_api.models import ArtifactKind, DerivedKind
from prism_api.models.artifact import Artifact
from prism_api.models.user import User
from prism_api.parsers.spectrogram import load_spectrogram
from prism_api.parsers.spectrum import Spectrum, load_spectrum
from prism_api.parsers.touchstone import load_touchstone
from prism_api.parsers.waveform import load_waveform
from prism_api.repos.artifacts import ArtifactRepo, DerivedRepo
from prism_api.schemas.artifact import (
    ArtifactOut,
    ChannelMetricsResponse,
    FFTResponse,
    SpectrogramResponse,
    SpectrumResponse,
    SpurOut,
    SpursResponse,
    WaveformResponse,
)
from prism_api.storage import build_storage

router = APIRouter(prefix="/api/v1/artifacts", tags=["artifacts"])

_WAVEFORM_KINDS = {ArtifactKind.WAVEFORM_CSV, ArtifactKind.WAVEFORM_NPY, ArtifactKind.WAVEFORM_HDF5}
_SPECTRUM_KINDS = {ArtifactKind.SPECTRUM_CSV, ArtifactKind.SPECTRUM_TOUCHSTONE}


def _parse_spectrum(kind: ArtifactKind, data: bytes) -> Spectrum:
    if kind == ArtifactKind.SPECTRUM_TOUCHSTONE:
        return load_touchstone(data)
    return load_spectrum(data)


def _fetch_artifact_or_404(session: Session, artifact_id: str) -> Artifact:
    a = ArtifactRepo(session).get_by_id(artifact_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "artifact not found")
    return a


@router.get("/{artifact_id}", response_model=ArtifactOut)
def get_artifact(
    artifact_id: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> ArtifactOut:
    a = _fetch_artifact_or_404(session, artifact_id)
    return ArtifactOut(
        id=a.id,
        owner_type=a.owner_type,
        owner_id=a.owner_id,
        kind=a.kind.value,
        filename=a.filename,
        size_bytes=a.size_bytes,
        content_hash=a.content_hash,
    )


_INLINE_CONTENT_TYPES = {
    ".json": "application/json",
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".log": "text/plain; charset=utf-8",
    ".csv": "text/csv",
    ".svg": "image/svg+xml",
    ".png": "image/png",
}


@router.get("/{artifact_id}/raw")
def raw_artifact(
    artifact_id: str,
    _: User = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> Response:
    """Stream the artifact bytes inline with a sensible Content-Type.

    Unlike `/download` (which 307s to a presigned MinIO URL with
    `Content-Type: binary/octet-stream`), this endpoint proxies the
    bytes through the API and labels them by extension, so a UI can
    fetch a JSON figure or render an HTML blob without iframe/CORS
    gymnastics. Intended for small inline payloads (figure JSON,
    metrics JSON, log text) — not large blobs.
    """
    a = _fetch_artifact_or_404(session, artifact_id)
    storage = build_storage(settings)
    data = storage.get_bytes(a.storage_key)
    suffix = PurePosixPath(a.filename).suffix.lower()
    media_type = _INLINE_CONTENT_TYPES.get(suffix, "application/octet-stream")
    return Response(content=data, media_type=media_type)


@router.get("/{artifact_id}/download")
def download_artifact(
    artifact_id: str,
    _: User = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> RedirectResponse:
    a = _fetch_artifact_or_404(session, artifact_id)
    storage = build_storage(settings)
    url = storage.presigned_url(a.storage_key, expires_in=300)
    return RedirectResponse(url, status_code=307)


@router.get("/{artifact_id}/waveform", response_model=WaveformResponse)
def get_waveform(
    artifact_id: str,
    downsample: int = Query(default=2000, ge=100, le=50_000),
    _: User = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> WaveformResponse:
    a = _fetch_artifact_or_404(session, artifact_id)
    if a.kind not in _WAVEFORM_KINDS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"artifact kind {a.kind.value} is not a waveform"
        )
    storage = build_storage(settings)
    data = storage.get_bytes(a.storage_key)
    wf = load_waveform(a.kind, data, filename=a.filename)
    ds = downsample_for_plot(wf.samples, target=downsample)
    return WaveformResponse(
        samples=ds.samples.tolist(),
        sample_rate=wf.sample_rate,
        stride=ds.stride,
        total_samples=int(wf.samples.size),
    )


@router.get("/{artifact_id}/spectrum", response_model=SpectrumResponse)
def get_spectrum(
    artifact_id: str,
    _: User = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> SpectrumResponse:
    a = _fetch_artifact_or_404(session, artifact_id)
    if a.kind not in _SPECTRUM_KINDS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"artifact kind {a.kind.value} is not a spectrum"
        )
    storage = build_storage(settings)
    data = storage.get_bytes(a.storage_key)
    spec = _parse_spectrum(a.kind, data)
    return SpectrumResponse(
        frequencies=[float(x) for x in spec.frequencies],
        powers=[float(x) for x in spec.powers],
        unit=spec.unit,
        metadata=spec.metadata,
    )


@router.get("/{artifact_id}/spectrogram", response_model=SpectrogramResponse)
def get_spectrogram(
    artifact_id: str,
    _: User = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> SpectrogramResponse:
    a = _fetch_artifact_or_404(session, artifact_id)
    if a.kind != ArtifactKind.SPECTROGRAM:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"artifact kind {a.kind.value} is not a spectrogram"
        )
    data = build_storage(settings).get_bytes(a.storage_key)
    sg = load_spectrogram(data)
    return SpectrogramResponse(
        frequencies=[float(x) for x in sg.frequencies],
        times=[float(x) for x in sg.times],
        powers=[[float(v) for v in row] for row in sg.powers],
        unit=sg.unit,
        metadata=sg.metadata,
    )


def _load_spectrum_or_400(session: Session, settings: Settings, artifact_id: str):  # type: ignore[no-untyped-def]
    a = _fetch_artifact_or_404(session, artifact_id)
    if a.kind not in _SPECTRUM_KINDS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"artifact kind {a.kind.value} is not a spectrum"
        )
    data = build_storage(settings).get_bytes(a.storage_key)
    return _parse_spectrum(a.kind, data)


@router.get("/{artifact_id}/channel-power", response_model=ChannelMetricsResponse)
def get_channel_power(
    artifact_id: str,
    center: float = Query(...),
    channel_bw: float = Query(..., gt=0),
    offset: float | None = Query(default=None, gt=0),
    adjacent_bw: float | None = Query(default=None, gt=0),
    _: User = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> ChannelMetricsResponse:
    spec = _load_spectrum_or_400(session, settings, artifact_id)
    m = channel_metrics(
        spec.frequencies,
        spec.powers,
        center=center,
        channel_bw=channel_bw,
        offset=offset,
        adjacent_bw=adjacent_bw,
    )
    return ChannelMetricsResponse(
        channel_power_dbm=m.channel_power_dbm,
        acpr_lower_dbc=m.acpr_lower_dbc,
        acpr_upper_dbc=m.acpr_upper_dbc,
        obw_hz=m.obw_hz,
        channel_band=m.channel_band,
        lower_band=m.lower_band,
        upper_band=m.upper_band,
    )


@router.get("/{artifact_id}/spurs", response_model=SpursResponse)
def get_spurs(
    artifact_id: str,
    margin_db: float = Query(default=20.0, ge=0),
    _: User = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> SpursResponse:
    spec = _load_spectrum_or_400(session, settings, artifact_id)
    floor = float(np.median(spec.powers)) if spec.powers.size else 0.0
    spurs = find_spurs(spec.frequencies, spec.powers, margin_db=margin_db)
    return SpursResponse(
        margin_db=margin_db,
        noise_floor_dbm=floor,
        spurs=[SpurOut(frequency=s.frequency, power=s.power) for s in spurs],
    )


@router.get("/{artifact_id}/fft", response_model=FFTResponse)
def get_fft(
    artifact_id: str,
    window: str = Query(default="hann"),
    nfft: int = Query(default=1024, ge=64, le=65536),
    overlap: float = Query(default=0.5, ge=0.0, le=0.9),
    _: User = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> FFTResponse:
    a = _fetch_artifact_or_404(session, artifact_id)
    if a.kind not in _WAVEFORM_KINDS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"artifact kind {a.kind.value} is not a waveform"
        )
    params = FFTParams(window=window, nfft=nfft, overlap=overlap)  # type: ignore[arg-type]
    ph = params_hash(params)
    storage = build_storage(settings)
    derived_repo = DerivedRepo(session)
    cached = derived_repo.find(source_artifact_id=a.id, kind=DerivedKind.FFT, params_hash=ph)
    if cached is not None:
        payload = storage.get_bytes(cached.storage_key)
        loaded = np.load(io.BytesIO(payload), allow_pickle=False)
        freqs, mags = loaded["freqs"], loaded["mags"]
        sample_rate = float(loaded["fs"][0])
    else:
        raw = storage.get_bytes(a.storage_key)
        wf = load_waveform(a.kind, raw, filename=a.filename)
        result = compute_fft(wf.samples, sample_rate=wf.sample_rate, params=params)
        freqs, mags, sample_rate = result.frequencies, result.magnitudes, result.sample_rate
        # Cache to MinIO
        buf = io.BytesIO()
        np.savez_compressed(buf, freqs=freqs, mags=mags, fs=np.array([sample_rate]))
        key = f"derived/fft/{a.content_hash}-{ph}.npz"
        storage.put_at(key, buf.getvalue(), content_type="application/octet-stream")
        derived_repo.create(
            source_artifact_id=a.id, kind=DerivedKind.FFT, storage_key=key, params_hash=ph
        )
        session.commit()
    return FFTResponse(
        frequencies=[float(x) for x in freqs],
        magnitudes=[float(x) for x in mags],
        sample_rate=float(sample_rate),
        params={"window": window, "nfft": nfft, "overlap": overlap},
    )
