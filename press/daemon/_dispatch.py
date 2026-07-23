"""CommandDispatcher — execute transform commands against the clipboard."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from press.daemon._tray import _create_tray_image

if TYPE_CHECKING:
    from press.clipboard import ClipboardGuard
    from press.config import PressConfig
    from press.daemon._backends import TrayIcon


class CommandDispatcher:
    """Execute clipboard transform commands and optionally notify via the tray.

    Args:
        config: A :class:`~press.config.PressConfig` instance.
    """

    def __init__(self, config: PressConfig) -> None:
        self._config = config
        self._icon: TrayIcon | None = None
        # In-memory undo slot: the clipboard text the last dispatch overwrote.
        # File-less on purpose — the hotkey path must not gain disk I/O.
        self._undo_text: str | None = None
        # Dual-layer clipboard guard (Windows only; None on other platforms)
        self._guard: ClipboardGuard | None = None
        if sys.platform == "win32":
            from press.clipboard import ClipboardGuard as _Guard

            self._guard = _Guard(config.hold, on_conflict=self._on_hold_conflict)

    def set_icon(self, icon: TrayIcon) -> None:
        """Bind the tray icon used for notifications."""
        self._icon = icon

    # ------------------------------------------------------------------
    # Public

    def dispatch(self, command: str) -> None:
        """Run *command* on the clipboard in-place.

        Reads the current clipboard text, applies the named transform, and
        writes the result back.  Notifications are emitted according to
        ``config.ui.notify_level``.
        """
        import contextlib

        from press.clipboard import clear_clipboard, get_clipboard_text, set_clipboard_text

        try:
            if command == "clear":
                # Empty/non-text clipboard — clear proceeds without a snapshot
                with contextlib.suppress(OSError, RuntimeError):
                    self._remember_for_undo(get_clipboard_text())
                clear_clipboard()
                self._notify_success(command, "")
                return
            if command == "hold":
                self._toggle_hold()
                return
            if command == "undo":
                self._undo_swap()
                return
            if command == "type":
                self._type_clipboard()
                return
            text = get_clipboard_text()
            result = self.transform(command, text)
            self._remember_for_undo(text)
            set_clipboard_text(result)
            self._notify_success(command, result)
        except Exception as exc:
            self._notify_error(command, str(exc))

    def transform(self, command: str, text: str, kwargs: dict[str, Any] | None = None) -> str:
        """Apply the named transform to *text* and return the result.

        Public because the named-pipe server (:mod:`press.daemon._pipe`) runs
        transforms for delegating CLI clients without touching the clipboard.

        Args:
            command: Registry command name or alias.
            text: Input text.
            kwargs: Options supplied by a delegating CLI process.  When
                ``None`` (the hotkey path) a parametric command derives its
                options from the daemon's config instead.

        Raises:
            ValueError: When *command* is not a known transform.
        """
        from press.commands import is_registry_command, run_command

        # Registry (simple or parametric) commands share the CLI's execution
        # path.  ``kwargs`` from a delegating pipe client win; the hotkey path
        # passes ``None`` and parametric options come from config instead.
        if is_registry_command(command):
            return run_command(command, text, cli_kwargs=kwargs, config=self._config)

        # Special commands that require internal helpers
        match command:
            case "dict":
                return self._run_dict(text, reverse=False)
            case "dict_reverse":
                return self._run_dict(text, reverse=True)
            case _:
                pipeline = self._config.pipelines.get(command)
                if pipeline is not None:
                    return self._run_pipeline(command, pipeline, text)
                raise ValueError(f"unknown command: {command!r}")

    def _run_pipeline(self, name: str, steps: tuple[str, ...], text: str) -> str:
        """Run a ``[pipelines]`` entry: registry transforms applied in order.

        Steps are restricted to registry commands — the same rule as the CLI
        ``chain`` command, and a structural guarantee against recursion.
        """
        from press.commands import is_registry_command

        for step in steps:
            if not is_registry_command(step):
                raise ValueError(f"pipeline {name!r}: step {step!r} is not a transform command")
            text = self.transform(step, text)
        return text

    def notify_error(self, command: str, message: str) -> None:
        """Deliver an error notification; public entry point for external callers."""
        self._notify_error(command, message)

    # ------------------------------------------------------------------
    # Internal

    def _run_dict(self, text: str, *, reverse: bool) -> str:
        from press.dictionary import default_dict_path
        from press.transforms.dictionary import dict_forward, dict_reverse, load_tsv

        cfg = self._config.dictionary
        paths = cfg.resolved_paths()
        path = paths[0] if paths else default_dict_path()
        table = load_tsv(path)
        return dict_reverse(text, table=table) if reverse else dict_forward(text, table=table)

    def _notify_success(self, command: str, _result: str) -> None:
        if self._config.ui.notify_level in ("success", "all"):
            self._notify("press", f"[{command}] done")

    def _notify_error(self, command: str, message: str) -> None:
        if self._config.ui.notify_level in ("error", "all"):
            self._notify(f"press: {command} failed", message[:120])

    def _notify(self, title: str, message: str) -> None:
        if self._icon is None:
            return
        import contextlib

        with contextlib.suppress(Exception):
            self._icon.notify(message, title)

    def _toggle_hold(self) -> None:
        """Toggle dual-layer clipboard guard and update the tray icon."""
        if self._guard is None:
            return  # non-Windows: no-op

        if not self._guard.is_active:
            from press.clipboard import get_clipboard_text

            text = get_clipboard_text()
            self._guard.engage(text)
            self._update_icon(holding=True)
            self._notify_success("hold", "")
        else:
            self._guard.release()
            self._update_icon(holding=False)
            self._notify_success("hold-release", "")

    def _type_clipboard(self) -> None:
        """Type the clipboard into the focused window instead of pasting it.

        The clipboard is only ever the *source* here, so there is nothing to
        snapshot for undo — and nothing press can take back once the target
        application has received the keystrokes.
        """
        from press.clipboard import get_clipboard_text
        from press.keystrokes import type_text

        cfg = self._config.type
        type_text(
            get_clipboard_text(),
            newline=cfg.newline,
            max_chars=cfg.max_chars,
            chunk_size=cfg.chunk_size,
            chunk_delay=cfg.chunk_delay_ms / 1000,
        )
        self._notify_success("type", "")

    def _remember_for_undo(self, text: str) -> None:
        """Keep the pre-overwrite clipboard text for the undo command.

        Skipped for content carrying the sensitive-exclusion formats (press
        honours its own genpass marks) and under ``PRESS_NO_UNDO=1``.
        """
        from press.transforms.undo import undo_disabled

        if undo_disabled():
            return
        try:
            from press.clipboard import clipboard_has_sensitive_marks

            if clipboard_has_sensitive_marks():
                return
        except (OSError, RuntimeError):
            return  # cannot verify the marks — err on the side of not keeping it
        self._undo_text = text

    def _undo_swap(self) -> None:
        """Swap the clipboard with the undo slot (undo twice = redo)."""
        from press.clipboard import get_clipboard_text, set_clipboard_text

        if self._undo_text is None:
            self._notify_error("undo", "nothing to undo")
            return
        saved = self._undo_text
        try:
            current = get_clipboard_text()
        except (OSError, RuntimeError):
            current = ""  # empty/non-text clipboard — the redo slot becomes empty
        set_clipboard_text(saved)
        self._undo_text = current
        self._notify_success("undo", "")

    def _on_hold_conflict(self) -> None:
        """Hold auto-released: another app kept rewriting the clipboard.

        Called from the guard's monitor thread after it stood down, so the
        tray reflects reality and the user learns why protection ended.
        """
        self._update_icon(holding=False)
        self.notify_error("hold", "auto-released: another application is rewriting the clipboard")

    def _update_icon(self, *, holding: bool) -> None:
        """Swap the tray icon to reflect hold state."""
        if self._icon is None or not self._config.ui.hold_icon:
            return
        import contextlib

        with contextlib.suppress(Exception):
            self._icon.icon = _create_tray_image(holding=holding)
