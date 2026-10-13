# Laptop Control Pass (Stage 1-3)

## Pre-flight & fixed constraints verified:
- Laptop control is explicitly **OFF** by default (managed by `settings.enable_laptop_control`).
- Global kill-switch (`ctrl+alt+k`) was verified live using the `keyboard` library to immediately halt test loops.
- On-screen indicator triggers immediately via a daemonized `tkinter` red banner.
- Risk tiers are floored: Stage 2 (Launch/Close) = 2, Stage 3 (Mouse/Keyboard) = 2 (Max tier available).
- The `is_blocklisted()` mechanism is enforced at *every* action point (e.g. `LaptopLaunchAppTool` and `_verify_and_record_action`). The blocklist overrides any allowlist configuration.

## Milestones Achieved

### M1 - Stage 1: Observation
Built and tested tools for `laptop_screenshot`, `laptop_window_list`, `laptop_foreground_window`, and `laptop_clipboard_read`.
- **Safety Tested:** Content is actively scraped through `redact_string` for secrets. Screenshots are stored as content-addressed hashes in `data/blobs/`, meaning the database contains only a blob hash, never raw image bits.

### M2 - Stage 2: Scoped Application Control
Implemented `laptop_launch_app` and `laptop_close_app`.
- **Safety Tested:** Actions are restricted strictly to `guardian/config/laptop_allowlist.json`. Blocklist checks were tested by temporarily whitelisting a blocklisted app ("Bitwarden") and verifying it was correctly blocked anyway. Live tests successfully targeted opening and closing `Notepad`.

### M3 - Stage 3 Foundation: Session Safety
Implemented the `ComputerUseSession` struct.
- **Safety Tested:** Validated that tools crash out safely if there is no active session, if action budgets (max N actions) are exceeded, if the session times out, or if the global kill-switch is triggered.

### M4 - Stage 3: Element-Targeted Automation
Created `LaptopClickTool` and `LaptopTypeTool` heavily leaning on `pywinauto`. 
- **Safety Tested:** Tests successfully executed element-targeted and fallback-coordinate clicks. Verified the continuous foreground-window re-check logic by mocking a foreground window swap to a blocklisted title ("bitwarden login") and ensuring the action was aborted and the session killed before any keys were pressed.

### M5 - Wiring Into Agents
- Isolated laptop tools exclusively to the `LaptopAgent` context in `guardian.laptop.agent`. 
- Wired into the `Escalation` protocol from prior passes, verifying that ambiguous instructions ("click somewhere") raise an explicit `EscalationReason.AMBIGUOUS_SCOPE` back to the human instead of guessing coordinates.

### M6 - Surfacing It
Patched `guardian status` to cleanly render the new state.
- **Verified:** Status accurately dumps feature-flag enablement, kill-switch bindings, blocklist/allowlist sizes, and running session action counts.

### M7 (Stretch)
Deferred. Local screen recording was skipped to preserve credit budget, as per instruction to prioritize M0-M6 fully.

---

## IMPORTANT: Manual Verification
Before you flip the feature flag on your personal machine, **you must verify the kill-switch hotkey works without elevation issues on your specific Windows setup.** We verified it dynamically in the pytest runner context, but UAC boundaries sometimes drop low-level keyboard hooks. Open a safe window, hit `ctrl+alt+k`, and check the Guardian console before testing automation targets.
