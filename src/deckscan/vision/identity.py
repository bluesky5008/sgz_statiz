"""템플릿 매칭 기반 안정 식별자 (설계 DES-06, ADR-002).

같은 렌더링은 픽셀이 거의 동일하다는 전제(map_search 검증)에서, 유저명
스트립·장수 초상 크롭을 등록된 템플릿과 NCC로 대조해 안정적 ID를 부여한다.
미등록 크롭은 새 ID로 등록하고 라벨은 `pending`으로 남긴다(FR-07).

템플릿은 크롭에서 가장자리 `inset`을 깎아 저장한다 — 행 앵커의 ±수 px
지터를 슬라이딩 매칭(max)으로 흡수하기 위해서다.
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from ..store.datastore import DataStore

log = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.90
_INSET = 3


class IdentityMatcher:
    def __init__(self, store: DataStore, root: Path, namespace: str,
                 threshold: float = DEFAULT_THRESHOLD, inset: int = _INSET):
        self.store = store
        self.root = Path(root)
        self.namespace = namespace
        self.threshold = threshold
        self.inset = inset
        self.dir = self.root / "assets" / "templates" / namespace
        self._templates: list[tuple[int, np.ndarray]] = []
        for row in store.iter_identities(namespace):
            for rel in store.templates_of(row["identity_id"]):
                path = self.root / rel
                if path.is_file():
                    tpl = np.asarray(Image.open(path).convert("RGB"))
                    self._templates.append((row["identity_id"], tpl))
                else:
                    log.warning("템플릿 파일 없음: %s (identity %d)",
                                rel, row["identity_id"])

    def resolve(self, crop: np.ndarray,
                suggest_label: str | None = None) -> tuple[int, float, bool]:
        """크롭을 식별한다. 반환: (identity_id, 매칭 점수, 신규 등록 여부)."""
        best_id, best = None, self.threshold
        for iid, tpl in self._templates:
            th, tw = tpl.shape[:2]
            if th > crop.shape[0] or tw > crop.shape[1]:
                continue
            score = float(cv2.matchTemplate(crop, tpl, cv2.TM_CCOEFF_NORMED).max())
            if score > best:
                best_id, best = iid, score
        if best_id is not None:
            return best_id, best, False
        return self._register(crop, suggest_label)

    def _register(self, crop: np.ndarray,
                  suggest_label: str | None) -> tuple[int, float, bool]:
        i = self.inset
        tpl = crop[i:crop.shape[0] - i, i:crop.shape[1] - i]
        self.dir.mkdir(parents=True, exist_ok=True)
        n = len(list(self.dir.glob("*.png"))) + 1
        path = self.dir / f"{self.namespace}_{n:06d}.png"
        Image.fromarray(tpl).save(path)
        rel = path.relative_to(self.root).as_posix()
        iid = self.store.create_identity(self.namespace, suggest_label, rel)
        self._templates.append((iid, tpl))
        log.info("신규 %s 등록: identity %d (%s)", self.namespace, iid, rel)
        return iid, 1.0, True
