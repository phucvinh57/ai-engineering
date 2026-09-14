"""Golden Q&A set for evaluating retrieval + generation.

Every question and `expected_matches` substring below was checked against the
live corpus (`tauri-assistant search`) rather than guessed, so a failing item
reflects a real retrieval gap and not a bad fixture.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GoldenItem:
    id: str
    question: str
    source: str
    # A retrieved chunk counts as relevant if its heading_path or url contains
    # any of these substrings (case-insensitive).
    expected_matches: tuple[str, ...]
    # Prior turns as (role, content) pairs, oldest first -- lets a harvested
    # multi-turn conversation (see eval/harvest.py) replay through
    # condense_query exactly as it happened live. Empty for single-turn items.
    history: tuple[tuple[str, str], ...] = ()


GOLDEN_SET: list[GoldenItem] = [
    GoldenItem(
        "js-get-version",
        "How do I get the app's version number from the frontend JavaScript API?",
        "js-api",
        ("app > getVersion",),
    ),
    GoldenItem(
        "js-get-name",
        "How do I get the name of a Tauri application from the frontend JS API?",
        "js-api",
        ("app > getName",),
    ),
    GoldenItem(
        "perm-fs-read",
        "How do I check whether the fs plugin is allowed to read a file?",
        "permissions",
        ("fs plugin > permissions > allow-read-file",),
    ),
    GoldenItem(
        "perm-autostart-disable",
        "What is the permission identifier that allows disabling autostart, for the autostart plugin?",
        "permissions",
        ("autostart plugin > permissions > allow-disable",),
    ),
    GoldenItem(
        "guide-tray",
        "How do I create a system tray icon in a Tauri app?",
        "guide",
        ("learn/system-tray",),
    ),
    GoldenItem(
        "guide-state",
        "How do I manage global state in a Tauri app?",
        "guide",
        ("develop/state-management",),
    ),
    GoldenItem(
        "guide-updater",
        "How do I configure Tauri's built-in updater plugin?",
        "guide",
        ("plugin/updater",),
    ),
    GoldenItem(
        "guide-dialog",
        "How do I show a file open dialog from a Tauri app?",
        "guide",
        ("plugin/dialog",),
    ),
    GoldenItem(
        "guide-notification",
        "Which permission is needed to send desktop notifications in Tauri?",
        "guide",
        ("plugin/notification", "notification plugin > permissions"),
    ),
    GoldenItem(
        "guide-isolation",
        "How does Tauri's isolation pattern secure inter-process communication?",
        "guide",
        ("isolation",),
    ),
    GoldenItem(
        "rust-cursor-icon",
        "What does the CursorIcon enum represent in the tauri Rust crate?",
        "rust-api",
        ("enum.cursoricon",),
    ),
    GoldenItem(
        "rust-state-manager",
        "What Rust struct manages state that commands can access via State<T>?",
        "rust-api",
        ("struct.statemanager",),
    ),
]
