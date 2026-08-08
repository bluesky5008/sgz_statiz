"""scan 오케스트레이션·실행 요약·라벨 확정 절차 (설계 DES-10, FR-06·FR-07).

run_scan은 설계 §정상·실패·복구 흐름의 예외 경계다: 내비게이션·순회 실패는
run을 aborted로 마감하고 종료 코드 2를 반환하며, 이미 저장된 레코드는
유지한다. 초기화 실패(창·권한·해상도, 종료 코드 1)는 CLI가 담당한다.
"""

from __future__ import annotations

import logging
from typing import Callable

from .store.datastore import DataStore

log = logging.getLogger(__name__)


def run_scan(store: DataStore, navigator, make_walker) -> tuple[int, str]:
    """전보 순회 실행. 반환: (종료 코드 0|2, 요약 텍스트).

    make_walker(run_id) → ListWalker — run 기록과 워커 생성 순서를 분리한다.
    """
    run_id = store.create_run()
    walker = None
    try:
        navigator.goto_combat_tab()
        walker = make_walker(run_id)
        s = walker.walk()
    except Exception:
        log.exception("scan 중단 — run #%d aborted", run_id)
        s = walker.summary if walker is not None else None
        store.finish_run(run_id, "aborted",
                         processed=s.processed if s else 0,
                         saved=s.saved if s else 0,
                         failed=s.failed if s else 0)
        return 2, summarize_run(store, run_id)
    store.finish_run(run_id, "done", processed=s.processed,
                     saved=s.saved, failed=s.failed)
    if s.partial or s.skipped:
        log.info("partial %d건, 건너뜀 %d건", s.partial, s.skipped)
    return 0, summarize_run(store, run_id)


def label_pending(store: DataStore, ask: Callable[[str], str],
                  opener: Callable[[str], None] | None = None) -> int:
    """pending 식별자를 순회하며 라벨을 확정한다(FR-07, AC-06).

    ask(프롬프트)의 입력 규약: 빈값=건너뜀(pending 유지), 'q'=중단,
    그 외=라벨 확정. opener(템플릿 경로)는 크롭 표시용(CLI가 뷰어 주입).
    반환: 확정한 식별자 수.
    """
    done = 0
    for row in store.pending_identities():
        templates = store.templates_of(row["identity_id"])
        template = templates[0] if templates else "?"
        if opener is not None:
            try:
                opener(template)
            except Exception:
                log.warning("크롭 표시 실패: %s", template)
        answer = ask(
            f"[{row['namespace']}#{row['identity_id']}] "
            f"제안='{row['label'] or ''}' 크롭={template} "
            f"→ 라벨 입력(빈값=건너뜀, q=종료): ").strip()
        if answer == "q":
            break
        if not answer:
            continue
        store.confirm_label(row["identity_id"], answer)
        done += 1
    return done


def summarize_run(store: DataStore, run_id: int) -> str:
    """run 요약 문자열(FR-06) — 처리·저장·실패 건수와 pending 안내."""
    run = store.get_run(run_id)
    lines = [f"run #{run_id} {run['status']} — 처리 {run['processed'] or 0}건, "
             f"저장 {run['saved'] or 0}건, 실패 {run['failed'] or 0}건"]
    pending = len(store.pending_identities())
    if pending:
        lines.append(f"미확정 식별자 pending {pending}건 — "
                     f"`deckscan label`로 라벨을 확정하세요")
    return "\n".join(lines)
