from types import ModuleType

import pytest

from immich_motion_deduplicator import __main__


def test_delete_command_requires_execute_for_real_deletion():
    parser = __main__.build_parser()

    args = parser.parse_args(["delete"])

    assert args.command == "delete"
    assert args.execute is False


def test_all_command_supports_dry_run_flag():
    parser = __main__.build_parser()

    args = parser.parse_args(["all", "--dry-run"])

    assert args.command == "all"
    assert args.dry_run is True


def test_all_command_rejects_execute_flag():
    parser = __main__.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["all", "--execute"])


def test_main_runs_all_with_real_deletion_by_default(monkeypatch):
    calls = []
    scan_module = ModuleType("scan_library")
    ids_module = ModuleType("get_ids")
    delete_module = ModuleType("delete_assets")

    scan_module.run = lambda progress_every: calls.append(("scan", progress_every))
    ids_module.main = lambda: calls.append(("ids", None))
    delete_module.run = lambda dry_run: calls.append(("delete", dry_run))

    monkeypatch.setattr(__main__, "print_stage", lambda *args: None)
    monkeypatch.setattr(__main__, "error_console", ModuleType("error_console"))
    __main__.error_console.print = lambda *args, **kwargs: None
    monkeypatch.setitem(__import__("sys").modules, "immich_motion_deduplicator.scan_library", scan_module)
    monkeypatch.setitem(__import__("sys").modules, "immich_motion_deduplicator.get_ids", ids_module)
    monkeypatch.setitem(__import__("sys").modules, "immich_motion_deduplicator.delete_assets", delete_module)
    monkeypatch.setattr(__import__("sys"), "argv", ["immich-motion-deduplicator", "all"])

    __main__.main()

    assert calls == [("scan", 500), ("ids", None), ("delete", False)]


def test_main_runs_all_dry_run_when_requested(monkeypatch):
    calls = []
    scan_module = ModuleType("scan_library")
    ids_module = ModuleType("get_ids")
    delete_module = ModuleType("delete_assets")

    scan_module.run = lambda progress_every: calls.append(("scan", progress_every))
    ids_module.main = lambda: calls.append(("ids", None))
    delete_module.run = lambda dry_run: calls.append(("delete", dry_run))

    monkeypatch.setattr(__main__, "print_stage", lambda *args: None)
    monkeypatch.setattr(__main__, "error_console", ModuleType("error_console"))
    __main__.error_console.print = lambda *args, **kwargs: None
    monkeypatch.setitem(__import__("sys").modules, "immich_motion_deduplicator.scan_library", scan_module)
    monkeypatch.setitem(__import__("sys").modules, "immich_motion_deduplicator.get_ids", ids_module)
    monkeypatch.setitem(__import__("sys").modules, "immich_motion_deduplicator.delete_assets", delete_module)
    monkeypatch.setattr(
        __import__("sys"),
        "argv",
        ["immich-motion-deduplicator", "all", "--dry-run"],
    )

    __main__.main()

    assert calls == [("scan", 500), ("ids", None), ("delete", True)]


def test_scan_live_command_uses_expected_defaults():
    parser = __main__.build_parser()
    args = parser.parse_args(["scan-live"])
    assert args.command == "scan-live"
    assert args.time_window == 60
    assert args.fps == 5.0
    assert args.hamming_threshold == 8
    assert args.skip_perceptual is False
    assert args.progress_every == 100


def test_scan_live_command_accepts_custom_scan_args():
    parser = __main__.build_parser()
    args = parser.parse_args(["scan-live", "--time-window", "30", "--hamming-threshold", "5"])
    assert args.command == "scan-live"
    assert args.time_window == 30
    assert args.hamming_threshold == 5


def test_main_routes_scan_live_with_expected_kwargs(monkeypatch):
    calls = []
    scan_module = ModuleType("scan_live")
    scan_module.run = lambda **kwargs: calls.append(("scan_live", kwargs))

    import immich_motion_deduplicator as pkg
    monkeypatch.setattr(pkg, "scan_live", scan_module, raising=False)
    monkeypatch.setitem(__import__("sys").modules, "immich_motion_deduplicator.scan_live", scan_module)
    monkeypatch.setattr(__main__, "require_env", lambda key: "live.csv")
    monkeypatch.setattr(__import__("sys"), "argv", ["immich-motion-deduplicator", "scan-live"])

    __main__.main()
    assert calls == [
        (
            "scan_live",
            {
                "time_window": 60,
                "fps": 5.0,
                "hamming_threshold": 8,
                "skip_perceptual": False,
                "progress_every": 100,
            },
        )
    ]

def test_main_routes_all_live_then_delete_with_dry_run(monkeypatch):
    calls = []
    scan_module = ModuleType("scan_live")
    delete_module = ModuleType("delete_assets")
    scan_module.run = lambda **kwargs: calls.append(("scan_live", kwargs))
    delete_module.run = lambda dry_run, input_csv: calls.append(("delete", dry_run, input_csv))

    import immich_motion_deduplicator as pkg
    monkeypatch.setattr(pkg, "scan_live", scan_module, raising=False)
    monkeypatch.setattr(pkg, "delete_assets", delete_module, raising=False)
    monkeypatch.setitem(__import__("sys").modules, "immich_motion_deduplicator.scan_live", scan_module)
    monkeypatch.setitem(__import__("sys").modules, "immich_motion_deduplicator.delete_assets", delete_module)
    monkeypatch.setattr(__main__, "require_env", lambda key: "live.csv")
    monkeypatch.setattr(__main__, "print_stage", lambda *args: None)
    monkeypatch.setattr(__main__, "error_console", ModuleType("error_console"))
    __main__.error_console.print = lambda *args, **kwargs: None
    monkeypatch.setattr(__import__("sys"), "argv", ["immich-motion-deduplicator", "all-live", "--dry-run"])

    __main__.main()
    assert calls == [
        (
            "scan_live",
            {
                "time_window": 60,
                "fps": 5.0,
                "hamming_threshold": 8,
                "skip_perceptual": False,
                "progress_every": 100,
            },
        ),
        ("delete", True, "live.csv"),
    ]
