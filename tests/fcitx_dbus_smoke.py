"""Functional input checks on a private bus and temporary HOME, never the desktop.

Requires fcitx5, dbus-run-session, dbus-python and PyGObject. Run with
python3 tests/fcitx_dbus_smoke.py --package ./result [--kimpanel].
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


def worker():
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    registry = dbus.Interface(
        bus.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus"),
        "org.freedesktop.DBus",
    )
    context = GLib.MainContext.default()
    kimpanel = os.environ["WETYPEX_TEST_KIMPANEL"] == "1"
    inline_preedit = os.environ["WETYPEX_TEST_INLINE_PREEDIT"] == "1"
    pinned = os.environ["WETYPEX_TEST_PIN_PREEDIT"] == "1"
    text_icon = os.environ["WETYPEX_TEST_TEXT_ICON"] == "1"
    updates, preedits, commits, visible, properties = [], [], [], [], []
    client_preedits, panel_preedits, panel_cursors, spots = [], [], [], []
    client_preedit_formats = []
    output_events, forwarded = [], []
    if kimpanel:
        class Panel(dbus.service.Object):
            @dbus.service.method("org.kde.impanel2", in_signature="asasasbbii")
            def SetLookupTable(self, labels, texts, attrs, prev, next_, cursor, layout):
                updates.append([(str(a), str(b)) for a, b in zip(labels, texts)])

            @dbus.service.method("org.kde.impanel2", in_signature="iiii")
            def SetSpotRect(self, x, y, width, height):
                spots.append(tuple(map(int, (x, y, width, height))))

            @dbus.service.signal("org.kde.impanel", signature="i")
            def SelectCandidate(self, index):
                pass

        panel_name = dbus.service.BusName("org.kde.impanel", bus=bus)
        panel = Panel(panel_name, "/org/kde/impanel")
        interface = "org.kde.kimpanel.inputmethod"
        bus.add_signal_receiver(lambda v: visible.append(bool(v)),
                                dbus_interface=interface, signal_name="ShowLookupTable")
        bus.add_signal_receiver(lambda rows: properties.extend(map(str, rows)),
                                dbus_interface=interface, signal_name="RegisterProperties")
        bus.add_signal_receiver(lambda row: properties.append(str(row)),
                                dbus_interface=interface, signal_name="UpdateProperty")
        bus.add_signal_receiver(lambda text, attrs: panel_preedits.append(str(text)),
                                dbus_interface=interface, signal_name="UpdatePreeditText")
        bus.add_signal_receiver(lambda cursor: panel_cursors.append(int(cursor)),
                                dbus_interface=interface, signal_name="UpdatePreeditCaret")

    def pump(seconds=.05):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            while context.pending():
                context.iteration(False)
            time.sleep(.005)

    def wait_for(predicate, message):
        end = time.monotonic() + 10
        while not predicate():
            assert daemon.poll() is None, "private daemon exited"
            assert time.monotonic() < end, message
            pump()

    with tempfile.TemporaryFile(mode="w+") as log:
        addons = "keyboard,clipboard,dbus,dbusfrontend,wetypex"
        if kimpanel:
            addons += ",kimpanel"
        daemon = subprocess.Popen(
            [os.environ["WETYPEX_TEST_FCITX"], "-D", "-k", "--disable", "all",
             "--enable", addons], stdout=log, stderr=log,
        )
        try:
            wait_for(lambda: registry.NameHasOwner("org.fcitx.Fcitx5"),
                     "private daemon startup timeout")
            # Verify ownership before sending any synthetic key events.
            assert int(registry.GetConnectionUnixProcessID("org.fcitx.Fcitx5")) == daemon.pid
            controller = dbus.Interface(
                bus.get_object("org.fcitx.Fcitx5", "/controller"),
                "org.fcitx.Fcitx.Controller1",
            )
            method = dbus.Interface(
                bus.get_object("org.fcitx.Fcitx5", "/org/freedesktop/portal/inputmethod"),
                "org.fcitx.Fcitx.InputMethod1",
            )
            path, _ = method.CreateInputContext([("program", "wetypex-synthetic-test")])
            interface = "org.fcitx.Fcitx.InputContext1"
            ic = dbus.Interface(bus.get_object("org.fcitx.Fcitx5", path), interface)
            ic.SetCapability(dbus.UInt64(((1 << 1) | (1 << 4) if inline_preedit else 0) |
                                         (0 if kimpanel else (1 << 39))))
            anchor = [120, 180, 1, 24]
            ic.SetCursorRect(*anchor)

            def client_preedit(rows, cursor):
                text = "".join(str(s[0]) for s in rows)
                preedits.append(text)
                client_preedits.append((text, int(cursor)))
                client_preedit_formats.append([int(s[1]) for s in rows if str(s[0])])
                output_events.append(("preedit", text))
                # Model a client that positions its candidate window at the
                # reported preedit caret, with fixed-width ASCII pinyin.
                x = anchor[0] + (max(0, int(cursor)) * 9 if text else 0)
                ic.SetCursorRect(x, *anchor[1:])

            def committed(text):
                commits.append(str(text))
                output_events.append(("commit", str(text)))
                anchor[0] += len(str(text)) * 18
                ic.SetCursorRect(*anchor)

            def client_ui(*args):
                updates.append([(str(c[0]), str(c[1])) for c in args[4]])
                panel_preedits.append("".join(str(s[0]) for s in args[0]))
                panel_cursors.append(int(args[1]))

            if not kimpanel:
                bus.add_signal_receiver(
                    client_ui,
                    dbus_interface=interface, signal_name="UpdateClientSideUI", path=path,
                )
            bus.add_signal_receiver(
                client_preedit,
                dbus_interface=interface, signal_name="UpdateFormattedPreedit", path=path,
            )
            bus.add_signal_receiver(committed,
                                    dbus_interface=interface, signal_name="CommitString", path=path)
            bus.add_signal_receiver(lambda *args: forwarded.append(tuple(args)),
                                    dbus_interface=interface, signal_name="ForwardKey", path=path)
            ic.FocusIn()
            controller.Activate()
            controller.SetCurrentIM("wetypex")
            assert controller.CurrentInputMethod() == "wetypex"
            pump(2)
            if kimpanel:
                assert controller.CurrentUI() == "kimpanel"

            def check_status(label, language):
                if not kimpanel:
                    return
                icon = (Path(os.environ["WETYPEX_TEST_PACKAGE"]) /
                        f"share/icons/hicolor/scalable/status/fcitx5-wetypex-{language}-symbolic.svg")
                assert icon.is_file(), icon

                def matches():
                    rows = [row for row in properties if row.startswith("/Fcitx/im:")]
                    if not rows or not rows[-1].endswith(f"label={label}"):
                        return False
                    return (rows[-1].startswith(f"/Fcitx/im:{label}::") if text_icon
                            else f":{icon}:" in rows[-1])

                wait_for(matches, f"panel did not show {label}: {properties[-4:]}")

            check_status("中", "zh")

            def key(sym, states=0, release=False, settle=True):
                consumed = ic.ProcessKeyEvent(
                    dbus.UInt32(sym), dbus.UInt32(0), dbus.UInt32(states),
                    dbus.Boolean(release), dbus.UInt32(int(time.time()*1000) & 0xffffffff),
                )
                if settle:
                    pump()
                return bool(consumed)

            def press(sym, states=0):
                consumed = key(sym, states)
                key(sym, states, release=True)
                return consumed

            def prefix():
                assert not press(ord("b"), 4), "Ctrl+b was consumed"
                assert not key(0xffe3, release=True), "Ctrl release was consumed"

            # The status badge follows the engine's language mode, including
            # panels that prefer labels and panels that use SVG icons.
            press(0xffe1)  # Shift switches to English on release.
            check_status("英", "en")
            assert not press(ord("a")), "English mode consumed a letter"
            press(0xffe1)
            check_status("中", "zh")

            # Forward tmux's command key and repeats, then resume composition.
            prefix()
            assert not key(ord("x")), "tmux command started a composition"
            assert not key(ord("x")), "tmux command repeat was consumed"
            assert not key(ord("x"), release=True)
            assert not any(preedits), "tmux prefix produced preedit"
            assert press(ord("x")), "normal typing did not resume"
            ic.Reset()
            pump()

            # Other control shortcuts must not forward the following letter.
            assert not press(ord("c"), 4)
            assert press(ord("x"))
            ic.Reset()
            pump()
            # A prefix must not leak across focus changes or explicit resets.
            prefix()
            ic.FocusOut()
            ic.FocusIn()
            assert press(ord("x")), "prefix survived focus loss"
            ic.Reset()
            pump()
            prefix()
            ic.Reset()
            pump()
            assert press(ord("x")), "prefix survived reset"
            ic.Reset()
            pump()

            # Some clients omit releases. A different letter ends the
            # forwarded-key repeat state, so later x can compose normally.
            assert not key(ord("b"), 4)
            assert not key(ord("x"))
            assert key(ord("n"))
            assert key(ord("x")), "forwarded key remained stuck without release"
            ic.Reset()
            pump()

            spot_begin = len(spots)
            for char in "nihao":
                begin = len(client_preedits)
                assert press(ord(char)), "letter was not consumed"
                if inline_preedit:
                    wait_for(lambda: len(client_preedits) > begin,
                             "composition did not update")
                    pump(.1)
                    assert len(client_preedits) == begin + 1, (
                        "one key repainted the preedit more than once", char,
                        client_preedits[begin:])
                    assert client_preedits[-1][0], "composition briefly disappeared"
                    formats = client_preedit_formats[-1]
                    assert formats and all(flag & (1 << 3) for flag in formats), formats
                    assert any(flag & (1 << 4) for flag in formats) == pinned, formats
            wait_for(lambda: updates and updates[-1] and updates[-1][0] == ("1 ", "你好"),
                     "Chinese candidates never arrived")
            if inline_preedit:
                wait_for(lambda: client_preedits and client_preedits[-1][0] == "ni'hao",
                         "final display preedit never arrived")
                assert client_preedits[-1][1] == (0 if pinned else 6), client_preedits[-1]
                if kimpanel and pinned:
                    assert spots and spots[-1] == tuple(anchor), spots
                    assert all(spot == tuple(anchor) for spot in spots[spot_begin:]), spots
            else:
                assert not any(text for text, _ in client_preedits)
                assert panel_preedits[-1] == "ni'hao", panel_preedits[-1:]
                assert panel_cursors[-1] == 6, panel_cursors[-1:]
            first = updates[-1]
            preedit_count = len(client_preedits)
            assert len(first) == 6, first
            assert [label for label, _ in first] == [f"{i} " for i in range(1, 7)]
            ic.NextPage()
            pump(.2)
            assert updates[-1] != first, "next page not delivered"
            assert [label for label, _ in updates[-1]] == [f"{i} " for i in range(1, 7)]
            ic.PrevPage()
            pump(.2)
            assert updates[-1] == first, "first page not restored"
            assert len(client_preedits) == preedit_count, "paging repainted client preedit"
            if kimpanel:
                assert visible[-1], "candidate window not shown"
                panel.SelectCandidate(0)
            else:
                assert press(32)
            wait_for(lambda: commits == ["你好"], "selected text never committed")
            wait_for(lambda: updates[-1] == [], "candidate list not cleared")
            if kimpanel:
                assert not visible[-1], "candidate window not hidden"

            # Pinning the client caret must not change the engine's edit
            # position. Home/insertion/End/backspace still edit the raw input.
            for char in "nihao":
                assert press(ord(char))
            assert press(0xff50)  # Home
            assert press(ord("x"))
            assert press(0xff57)  # End
            assert press(0xff08)  # Backspace
            assert press(0xff0d)  # Return commits the raw spelling
            wait_for(lambda: len(commits) == 2, "edited raw input never committed")
            assert commits == ["你好", "xniha"], commits
            # Exercise the reported long spelling, then delete it completely.
            # Each edit should publish one authoritative composition; the last
            # backspace must still clear the application's preedit.
            for sym in [ord(c) for c in "weismjfkdsajk"] + [0xff08] * 13:
                begin = len(client_preedits)
                assert press(sym)
                if inline_preedit:
                    wait_for(lambda: len(client_preedits) > begin,
                             "edited composition did not update")
                    pump(.1)
                    assert len(client_preedits) == begin + 1, client_preedits[begin:]
            if inline_preedit:
                assert client_preedits[-1][0] == "", client_preedits[-1]
            # Queue typing and selection without waiting for each backend
            # reply. Suppressing speculative drawing must not lose keystrokes.
            for char in "nihao nihao ":
                assert key(ord(char), settle=False)
                key(ord(char), release=True, settle=False)
            wait_for(lambda: len(commits) == 4, "rapid selections did not commit")
            assert commits[2:] == ["你好", "你好"], commits
            if inline_preedit:
                wait_for(lambda: client_preedits[-1][0] == "",
                         "rapid selection left stale preedit")
            for char in "hhh":
                assert press(ord(char))
            wait_for(lambda: updates and len(updates[-1]) > 1 and
                     updates[-1][1][1] == "😂", "hhh did not offer Unicode emoji")
            assert all(text != "[破涕为笑]" for _, text in updates[-1]), updates[-1]
            assert press(ord("2"))
            wait_for(lambda: len(commits) == 5, "emoji candidate did not commit")
            assert commits[-1] == "😂", commits
            # Forget the highlighted candidate, including on a later page.
            # Deletion must not commit text or redraw the unchanged preedit.
            assert not press(0xffff, 4), "idle Ctrl+Delete was consumed"
            for char in "nihao":
                assert press(ord(char))
            wait_for(lambda: updates[-1] and updates[-1][0][1] == "你好",
                     "forget test candidates never arrived")
            original_first = updates[-1][0][1]
            for later_page in (False, True):
                if later_page:
                    ic.NextPage()
                    pump(.2)
                target_index = next(i for i, (_, text) in enumerate(updates[-1])
                                    if i > 0 and text.isalpha())
                target = updates[-1][target_index][1]
                assert target != original_first
                for _ in range(target_index):
                    assert press(0xff54)  # Down highlights the target word.
                preedit_count = len(client_preedits)
                assert press(0xffff, 4), "Ctrl+Delete was not consumed"
                wait_for(lambda: updates[-1] and
                         updates[-1][0][1] == original_first and
                         all(text != target for _, text in updates[-1]),
                         "highlighted candidate was not forgotten")
                assert len(commits) == 5, "forget committed candidate text"
                assert len(client_preedits) == preedit_count, "forget repainted preedit"
                ic.Reset()
                pump()
                for char in "nihao":
                    assert press(ord(char))
                wait_for(lambda: updates[-1] and updates[-1][0][1] == original_first,
                         "composition after forget failed")
                if later_page:
                    ic.NextPage()
                    pump(.2)
                assert all(text != target for _, text in updates[-1]), updates[-1]
                if later_page:
                    ic.PrevPage()
                    pump(.2)
            assert press(0xff1b)  # Escape
            # Bare Shift commits the original spelling, then switches to
            # English. Automatic syllable separators are not committed.
            for spelling, shift in (("nihao", 0xffe1), ("xi'an", 0xffe2)):
                for char in spelling:
                    assert press(ord(char))
                count, event_begin = len(commits), len(output_events)
                key(shift)
                assert key(shift, 1, release=True), "bare Shift release was not consumed"
                wait_for(lambda: len(commits) == count + 1, "Shift did not commit preedit")
                assert commits[-1] == spelling, commits
                check_status("英", "en")
                if inline_preedit:
                    events = output_events[event_begin:]
                    assert ("preedit", "") not in events[:events.index(("commit", spelling))], events
                press(shift)
                check_status("中", "zh")

            # A Shift chord must neither commit nor change language mode.
            for char in "nihao":
                assert press(ord(char))
            count = len(commits)
            for modifier in (4, 8, 64):  # Ctrl, Alt, Super
                key(0xffe1, modifier)
                key(0xffe1, modifier | 1, release=True)
                assert len(commits) == count, "Shift chord committed preedit"
                check_status("中", "zh")
            assert press(0xff1b)

            # Shift used for uppercase typing is not a bare Shift tap.
            key(0xffe1)
            assert press(ord("A"), 1)
            key(0xffe1, 1, release=True)
            assert len(commits) == count
            assert press(ord("b"))
            key(0xffe2)
            assert press(ord("C"), 1)
            key(0xffe2, 1, release=True)
            assert len(commits) == count
            check_status("中", "zh")
            key(0xffe1)
            assert key(0xffe1, release=True)
            wait_for(lambda: len(commits) == count + 1, "mixed-case raw commit failed")
            assert commits[-1] == "AbC", commits
            press(0xffe1)
            check_status("中", "zh")

            # Preserve Chinese already selected within a longer composition.
            for char in "nihaoshijie":
                assert press(ord(char))
            index = next(i for i, (_, text) in enumerate(updates[-1]) if text == "你好")
            assert press(ord(str(index + 1)))
            count = len(commits)
            key(0xffe2)
            assert key(0xffe2, release=True)
            wait_for(lambda: len(commits) == count + 1, "partial selection was lost")
            assert commits[-1] == "你好shijie", commits
            press(0xffe2)
            check_status("中", "zh")

            # No waiting between typing, Shift, and the following English key.
            count, forward_begin = len(commits), len(forwarded)
            for char in "ceshi":
                assert key(ord(char), settle=False)
                key(ord(char), release=True, settle=False)
            key(0xffe1, settle=False)
            key(0xffe1, release=True, settle=False)
            queued_english = key(ord("q"), settle=False)
            key(ord("q"), release=True, settle=False)
            wait_for(lambda: len(commits) == count + 1, "rapid Shift lost input")
            assert commits[-1] == "ceshi", commits
            if queued_english:
                wait_for(lambda: any(int(args[0]) == ord("q") and not bool(args[-1])
                                     for args in forwarded[forward_begin:]),
                         "English key after Shift was not forwarded")
            check_status("英", "en")
            press(0xffe1)
            check_status("中", "zh")
            if inline_preedit and pinned:
                assert all(cursor == 0 for text, cursor in client_preedits if text)
            print("PASS:", "Kimpanel (including 中/英 status and click)" if kimpanel else "client UI",
                  "— Ctrl+b passthrough, six spaced labels, paging, Chinese commit,",
                  "preedit anchor, raw cursor editing, single preedit update per edit,",
                  "Unicode emoji, Ctrl+Delete candidate forgetting, Shift raw commit")
            ic.DestroyIC()
        except Exception:
            log.seek(0)
            print(log.read()[-12000:], file=sys.stderr)
            raise
        finally:
            daemon.terminate()
            try:
                daemon.wait(timeout=5)
            except subprocess.TimeoutExpired:
                daemon.kill()
                daemon.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--fcitx", default=shutil.which("fcitx5"))
    parser.add_argument("--kimpanel", action="store_true")
    parser.add_argument("--follow-cursor", action="store_true")
    parser.add_argument("--no-inline-preedit", action="store_true")
    parser.add_argument("--text-icon", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        assert os.environ.get("WETYPEX_PRIVATE_INPUT_TEST") == "1"
        worker()
        return
    if not args.package or not args.fcitx:
        parser.error("--package and a working fcitx5 executable are required")
    package = args.package.resolve()
    with tempfile.TemporaryDirectory(prefix="wetypex-input-check-") as directory:
        root = Path(directory)
        config = root / "config/fcitx5"
        config.mkdir(parents=True)
        # Let WeTypeX handle Shift itself, as in the real desktop setup.
        (config / "config").write_text("[Hotkey]\nAltTriggerKeys=\n")
        (config / "profile").write_text(
            "[Groups/0]\nName=Default\nDefault Layout=us\nDefaultIM=wetypex\n\n"
            "[Groups/0/Items/0]\nName=keyboard-us\nLayout=\n\n"
            "[Groups/0/Items/1]\nName=wetypex\nLayout=\n\n[GroupOrder]\n0=Default\n"
        )
        (config / "wetypex.json").write_text(json.dumps({
            "standalone": True, "auto_update": False,
            "preedit_cursor_at_beginning": not args.follow_cursor,
        }))
        if args.text_icon:
            (config / "conf").mkdir()
            (config / "conf/kimpanel.conf").write_text("PreferTextIcon=True\n")
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(("WETYPE_", "WETYPEX_")) and key not in (
                   "DISPLAY", "WAYLAND_DISPLAY", "WAYLAND_SOCKET", "XAUTHORITY",
                   "DBUS_SESSION_BUS_ADDRESS", "DBUS_STARTER_ADDRESS", "DBUS_STARTER_BUS_TYPE")}
        env.update(HOME=str(root), XDG_CONFIG_HOME=str(root/"config"),
                   XDG_DATA_HOME=str(root/"data"), XDG_CACHE_HOME=str(root/"cache"),
                   XDG_DATA_DIRS=f"{package}/share:/run/current-system/sw/share:/usr/share",
                   FCITX_ADDON_DIRS=str(package/"lib/fcitx5"),
                   WETYPEX_PRIVATE_INPUT_TEST="1", WETYPEX_TEST_PACKAGE=str(package),
                   WETYPEX_TEST_FCITX=args.fcitx,
                   WETYPEX_TEST_INLINE_PREEDIT="0" if args.no_inline_preedit else "1",
                   WETYPEX_TEST_PIN_PREEDIT="0" if args.follow_cursor else "1",
                   WETYPEX_TEST_TEXT_ICON="1" if args.text_icon else "0",
                   WETYPEX_TEST_KIMPANEL="1" if args.kimpanel else "0")
        subprocess.run(["dbus-run-session", "--", sys.executable, str(Path(__file__).resolve()),
                        "--worker"], env=env, timeout=60, check=True)


if __name__ == "__main__":
    main()
