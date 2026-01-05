from adaad6.kernel.failures import (
    DETERMINISM_BREACH,
    EVIDENCE_MISSING,
    INTEGRITY_VIOLATION,
    KernelCrash,
    map_exception,
)


def test_map_exception_is_deterministic() -> None:
    cases = [
        (ValueError("invalid"), INTEGRITY_VIOLATION, "invalid"),
        (ValueError(""), INTEGRITY_VIOLATION, "ValueError"),
        (TypeError("wrong type"), INTEGRITY_VIOLATION, "wrong type"),
        (PermissionError("forbidden"), INTEGRITY_VIOLATION, "forbidden"),
        (KeyError("missing"), EVIDENCE_MISSING, "'missing'"),
        (FileNotFoundError("not found"), EVIDENCE_MISSING, "not found"),
        (TimeoutError("hung"), DETERMINISM_BREACH, "hung"),
        (RuntimeError("fallback"), DETERMINISM_BREACH, "fallback"),
    ]

    for exc, expected_code, expected_detail in cases:
        crash_first = map_exception(exc)
        crash_second = map_exception(exc)

        assert crash_first.code == expected_code
        assert crash_second.code == expected_code
        assert crash_first.detail == expected_detail
        assert crash_second.detail == expected_detail
        assert crash_first.debug_detail is None
        assert crash_second.debug_detail is None


def test_map_exception_preserves_debug_traces() -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        crash = map_exception(exc, include_debug=True)

    assert isinstance(crash, KernelCrash)
    assert crash.code == DETERMINISM_BREACH
    assert crash.detail == "boom"
    assert crash.debug_detail is not None
    assert "RuntimeError: boom" in crash.debug_detail


def test_map_exception_does_not_mutate_original_kernel_crash_when_debug_disabled() -> None:
    original = KernelCrash(INTEGRITY_VIOLATION, "x")
    mapped = map_exception(original, include_debug=False)

    assert mapped is original
    assert mapped.debug_detail is None


def test_map_exception_can_attach_debug_to_kernel_crash() -> None:
    try:
        raise KernelCrash(INTEGRITY_VIOLATION, "x")
    except KernelCrash as exc:
        mapped = map_exception(exc, include_debug=True)

    assert mapped.code == INTEGRITY_VIOLATION
    assert mapped.detail == "x"
    assert mapped.debug_detail is not None
