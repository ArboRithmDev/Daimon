"""macOS updater script generation (pure). Any platform."""

from pathlib import PurePosixPath

from daimon.update import apply_macos


def test_app_bundle_resolved_from_macos_binary_dir():
    macos_dir = PurePosixPath("/Applications/Daimon.app/Contents/MacOS")
    assert apply_macos._app_bundle(macos_dir).as_posix().endswith("/Applications/Daimon.app")


def test_updater_script_swaps_app_and_relaunches():
    s = apply_macos.build_updater_script(
        asset=PurePosixPath("/tmp/Daimon-0.0.8.dmg"),
        app=PurePosixPath("/Applications/Daimon.app"),
        self_path=PurePosixPath("/tmp/daimon-update.sh"),
    )
    assert "pkill -f 'Daimon.app/Contents/MacOS'" in s     # quit running app
    assert "hdiutil attach" in s and ".dmg" in s           # mount the DMG
    assert 'rm -rf "/Applications/Daimon.app"' in s         # replace
    assert 'open "/Applications/Daimon.app"' in s           # relaunch
    assert "rm -f" in s and "daimon-update.sh" in s         # self-clean
