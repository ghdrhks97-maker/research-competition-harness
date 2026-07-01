"""Photo privacy curator (photo-privacy-curator-skill / `rch import-photos`).

Scans a photo folder and produces a manifest plus a privacy checklist.
The harness cannot see pixels, so every photo starts at the safe default:
`privacy_risk = "unreviewed"` with blur required until a human clears it.
Each photo gets a suggested placement (body / summary / appendix / exclude)
and the checklist blocks final use of any unreviewed or high-risk image.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".heic"}

# Filename hints that raise or lower the default risk. These are hints only;
# the human reviewer still confirms every image.
HIGH_RISK_HINTS = ("얼굴", "명단", "이름", "학번", "명찰", "id", "name", "face", "portrait")
LOW_RISK_HINTS = ("결과물", "산출물", "화면", "칠판", "board", "artifact", "result", "worksheet")

RISK_UNREVIEWED = "unreviewed"
RISK_HIGH = "high"
RISK_LOW = "low"
RISK_MISSING = "missing"
DEFAULT_REQUIRED_PHOTOS = 4
PHOTO_PLACEHOLDER_LABELS = (
    ("도입 활동", "body"),
    ("모둠 탐구 장면", "body"),
    ("학생 산출물", "appendix"),
    ("정리·발표 장면", "appendix"),
)


@dataclass
class PhotoEntry:
    file: str
    sha256: str
    bytes: int
    privacy_risk: str
    blur_required: bool
    suggested_placement: str
    checklist: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class PhotoManifest:
    source_dir: str
    count: int
    photos: list[PhotoEntry] = field(default_factory=list)
    missing_required: bool = False
    required_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _classify(name: str) -> tuple[str, str]:
    low = name.lower()
    if any(hint in low for hint in HIGH_RISK_HINTS):
        return RISK_HIGH, "파일명에 식별 위험 신호가 있어 우선 블러/제외 검토."
    if any(hint in low for hint in LOW_RISK_HINTS):
        return RISK_LOW, "산출물/화면 계열로 보이나 사람이 실제 화면을 최종 확인."
    return RISK_UNREVIEWED, "사람이 얼굴·이름·학번·개인화면 노출을 직접 확인하기 전까지 사용 보류."


def _placement(risk: str) -> str:
    if risk == RISK_MISSING:
        return "appendix"
    if risk == RISK_LOW:
        return "body"
    if risk == RISK_HIGH:
        return "exclude"
    return "appendix"


def _checklist(risk: str) -> list[str]:
    if risk == RISK_MISSING:
        return [
            "수업 장면 사진 첨부",
            "얼굴·이름·학번 블러 처리",
            "본문/부록 배치 확정",
        ]
    base = [
        "얼굴 식별 가능 여부 확인",
        "이름표·명찰·학번 노출 확인",
        "개인 화면(메신저, 성적, 개인정보) 노출 확인",
        "학교 밖 공개 가능 여부 확인",
    ]
    if risk != RISK_LOW:
        base.append("필요 시 블러/크롭 후 재검토")
    return base


def _missing_photo_entries(required_count: int) -> list[PhotoEntry]:
    entries: list[PhotoEntry] = []
    labels = list(PHOTO_PLACEHOLDER_LABELS)
    while len(labels) < required_count:
        labels.append((f"추가 수업사진 {len(labels) + 1}", "appendix"))
    for index, (label, placement) in enumerate(labels[:required_count], 1):
        entries.append(
            PhotoEntry(
                file=f"사진첨부필요_{index:02d}_{label}",
                sha256="",
                bytes=0,
                privacy_risk=RISK_MISSING,
                blur_required=True,
                suggested_placement=placement,
                checklist=_checklist(RISK_MISSING),
                notes=f"{label} 사진 첨부 필요",
            )
        )
    return entries


def build_manifest(
    source_dir: Path,
    placeholder_if_empty: bool = True,
    required_count: int = DEFAULT_REQUIRED_PHOTOS,
) -> PhotoManifest:
    manifest = PhotoManifest(source_dir=source_dir.as_posix(), count=0)
    if not source_dir.exists():
        if placeholder_if_empty:
            manifest.photos = _missing_photo_entries(required_count)
            manifest.missing_required = True
            manifest.required_count = required_count
        return manifest
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        data = path.read_bytes()
        risk, note = _classify(path.name)
        manifest.photos.append(
            PhotoEntry(
                file=path.relative_to(source_dir).as_posix(),
                sha256=hashlib.sha256(data).hexdigest(),
                bytes=len(data),
                privacy_risk=risk,
                blur_required=risk != RISK_LOW,
                suggested_placement=_placement(risk),
                checklist=_checklist(risk),
                notes=note,
            )
        )
    manifest.count = len(manifest.photos)
    if manifest.count == 0 and placeholder_if_empty:
        manifest.photos = _missing_photo_entries(required_count)
        manifest.missing_required = True
        manifest.required_count = required_count
    return manifest


def render_checklist_markdown(manifest: PhotoManifest) -> str:
    count_line = f"- 사진 수: {manifest.count}"
    if manifest.missing_required:
        count_line = "- 사진 수: 0"
    lines = [
        "# 사진 개인정보 점검표",
        "",
        f"- 원본 폴더: `{manifest.source_dir}`",
        count_line,
    ]
    if manifest.missing_required:
        lines.append(f"- 첨부 필요: {manifest.required_count}장")
    lines += [
        "",
        "기본값은 안전 우선입니다. 검토 전 사진은 `unreviewed`이며 최종 반영이 차단됩니다.",
        "",
        "| 파일 | 위험도 | 블러 필요 | 배치 제안 | 비고 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for photo in manifest.photos:
        lines.append(
            f"| `{photo.file}` | {photo.privacy_risk} | {'예' if photo.blur_required else '아니오'} "
            f"| {photo.suggested_placement} | {photo.notes} |"
        )
    lines.append("")
    lines.append("## 사람이 확인할 항목")
    lines.append("")
    lines.append("- 각 사진의 얼굴/이름표/학번/개인화면 노출을 직접 확인")
    lines.append("- 위험 확인된 사진은 블러·크롭 후 `privacy_risk`를 low로 갱신")
    lines.append("- 확인 전(`unreviewed`) 또는 high 위험 사진은 본문·요약서·부록에 넣지 않는다")
    lines.append("")
    return "\n".join(lines)


def build_claim_ledger(manifest: PhotoManifest) -> dict[str, Any]:
    claims: list[dict[str, Any]] = []
    for index, photo in enumerate(manifest.photos, 1):
        status = "placeholder" if photo.privacy_risk != RISK_LOW else "real"
        claims.append(
            {
                "id": f"photo-{index}",
                "text": f"수업사진 `{photo.file}` 배치 후보({photo.suggested_placement})",
                "status": status,
                "evidence": f"input/photos/{photo.file}" if status == "real" else "",
                "notes": photo.notes,
            }
        )
    return {"claims": claims}


def _write_photo_lane(
    workspace: Path,
    markdown_text: str,
    claim_ledger: dict[str, Any],
    status: str,
    reason: str,
    agent: str = "harness-photo",
) -> None:
    lane_dir = workspace / "lanes" / "photo-curator" / agent
    lane_dir.mkdir(parents=True, exist_ok=True)
    (lane_dir / "evidence").mkdir(exist_ok=True)
    (lane_dir / "lane-output.md").write_text(markdown_text, encoding="utf-8")
    (lane_dir / "lane-output.json").write_text(
        json.dumps(
            {
                "lane": "photo-curator",
                "agent": agent,
                "summary": reason,
                "artifacts": [
                    "input/photos/analysis/photo-manifest.json",
                    "input/photos/analysis/privacy-checklist.md",
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (lane_dir / "claim-ledger.json").write_text(
        json.dumps(claim_ledger, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (lane_dir / "verdict.json").write_text(
        json.dumps({"status": status, "reason": reason}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def import_photos(
    source_dir: Path,
    output_dir: Path,
    workspace: Path | None = None,
    placeholder_if_empty: bool = True,
    required_count: int = DEFAULT_REQUIRED_PHOTOS,
) -> PhotoManifest:
    manifest = build_manifest(
        source_dir,
        placeholder_if_empty=placeholder_if_empty,
        required_count=required_count,
    )
    checklist = render_checklist_markdown(manifest)
    ledger = build_claim_ledger(manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "photo-manifest.json").write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "privacy-checklist.md").write_text(checklist, encoding="utf-8")
    (output_dir / "claim-ledger.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if workspace is not None:
        if manifest.missing_required:
            status = "needs-work"
            reason = "사진 파일 없음. 수업사진 첨부 필요."
            agent = "harness-missing"
        else:
            status = "needs-work" if any(photo.privacy_risk != RISK_LOW for photo in manifest.photos) else "pass"
            reason = "사진 개인정보 검토 필요." if status == "needs-work" else "사진 매니페스트 완료."
            agent = "harness-photo"
        _write_photo_lane(workspace, checklist, ledger, status=status, reason=reason, agent=agent)
    return manifest
