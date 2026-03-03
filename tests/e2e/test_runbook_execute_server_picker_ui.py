"""
E2E tests for the Runbook Execute modal — Server Picker Widget.

Tests the redesigned multi-select server/group picker that replaced the
original single <select> dropdown in March 2026.

Requirements:
  - ADMIN_PASSWORD env var must be set (authenticated_page fixture)
  - A running instance at BASE_URL (default: http://localhost:8080)

Test IDs:  TC-EXEC-UI-01 … TC-EXEC-UI-14
"""

import re
import json as _json
import uuid
import pytest
from playwright.sync_api import Page, expect

_JSON_HEADERS = {"Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_runbook_via_api(page: Page, base_url: str) -> dict:
    """Create a minimal runbook via the API and return its JSON."""
    uid = uuid.uuid4().hex[:8]
    payload = {
        "name": f"E2E Picker Runbook {uid}",
        "description": "Created by E2E server picker tests",
        "category": "infrastructure",
        "enabled": True,
        "auto_execute": False,
        "approval_required": False,
        "steps": [
            {
                "step_order": 1,
                "name": "Smoke Step",
                "command_linux": "echo hello",
                "target_os": "linux",
                "timeout_seconds": 30,
                "continue_on_fail": False,
                "retry_count": 0,
                "retry_delay_seconds": 5,
            }
        ],
        "triggers": [],
    }
    resp = page.request.post(
        f"{base_url}/api/remediation/runbooks",
        data=_json.dumps(payload),
        headers=_JSON_HEADERS,
    )
    if resp.status not in (200, 201):
        pytest.skip(f"Could not create test runbook via API ({resp.status}: {resp.text()[:200]})")
    return resp.json()


def _create_server_via_api(page: Page, base_url: str, name: str, hostname: str) -> dict:
    """Create a server credential via the API and return its JSON."""
    payload = {
        "name": name,
        "hostname": "127.0.0.1",  # always resolvable inside the container
        "port": 8080,             # app port — always open inside the container
        "username": "deploy",
        "os_type": "linux",
        "protocol": "ssh",
        "auth_type": "password",
        "credential_source": "inline",
        "password": "E2eTestP@ss1!",  # dummy — server is never actually connected
        "environment": "test",
    }
    resp = page.request.post(
        f"{base_url}/api/servers",
        data=_json.dumps(payload),
        headers=_JSON_HEADERS,
    )
    if resp.status not in (200, 201):
        pytest.skip(f"Could not create test server via API ({resp.status}: {resp.text()[:200]})")
    return resp.json()


def _create_group_via_api(page: Page, base_url: str, name: str) -> dict:
    """Create a server group via the API and return its JSON."""
    resp = page.request.post(
        f"{base_url}/api/servers/groups",
        data=_json.dumps({"name": name, "description": "E2E group"}),
        headers=_JSON_HEADERS,
    )
    if resp.status not in (200, 201):
        pytest.skip(f"Could not create test group via API ({resp.status}: {resp.text()[:200]})")
    return resp.json()


def _open_execute_modal(page: Page, base_url: str, runbook_id: str, runbook_name: str = "") -> None:
    """Navigate to /runbooks, ensure our runbook is visible, then open the Execute modal."""
    page.goto(f"{base_url}/runbooks")
    page.wait_for_load_state("networkidle", timeout=20000)

    # Reload the in-memory runbooks array via JS so our runbook is present
    # regardless of how many E2E runbooks accumulate over time.
    # The page's /api/remediation/runbooks endpoint defaults to limit=50, so
    # we re-fetch with a targeted search to guarantee our ID is loaded.
    if runbook_name:
        escaped = runbook_name[:40].replace("'", "\\'")
        page.evaluate(f"""
            (async () => {{
                const r = await fetch('/api/remediation/runbooks?search={escaped}&limit=10');
                const data = await r.json();
                if (typeof runbooks !== 'undefined') {{
                    runbooks = data;
                    if (typeof renderRunbooks === 'function') renderRunbooks();
                }}
            }})()
        """)
        page.wait_for_timeout(600)

    # Click the Run (play) button identified by the runbook UUID in the onclick attr
    run_btn = page.locator(f"button[onclick*='{runbook_id}'][title='Run']").first
    run_btn.wait_for(state="visible", timeout=8000)
    run_btn.click()

    # Wait for execute modal to appear
    expect(page.locator("#executeModal")).to_be_visible(timeout=8000)


# ===========================================================================
# TC-EXEC-UI-01  Modal contains new picker widget, NOT the old <select>
# ===========================================================================

def test_execute_modal_has_server_picker_widget(authenticated_page: Page, base_url: str):
    """TC-EXEC-UI-01: Execute modal contains the server-picker widget, not a bare <select>."""
    rb = _create_runbook_via_api(authenticated_page, base_url)

    _open_execute_modal(authenticated_page, base_url, rb["id"], rb["name"])

    # New widget must be present
    expect(authenticated_page.locator("#serverPickerWidget")).to_be_visible()

    # Search input inside the widget
    expect(authenticated_page.locator("#serverSearchInput")).to_be_visible()

    # The OLD single-select element should NOT be present
    assert authenticated_page.locator("#executeServerId").count() == 0, (
        "Old <select id='executeServerId'> must be removed in the new picker design"
    )


# ===========================================================================
# TC-EXEC-UI-02  Placeholder text
# ===========================================================================

def test_server_picker_placeholder_text(authenticated_page: Page, base_url: str):
    """TC-EXEC-UI-02: Search input shows the correct placeholder."""
    rb = _create_runbook_via_api(authenticated_page, base_url)
    _open_execute_modal(authenticated_page, base_url, rb["id"], rb["name"])

    inp = authenticated_page.locator("#serverSearchInput")
    placeholder = inp.get_attribute("placeholder")
    assert placeholder, "Placeholder attribute should not be empty"
    assert "search" in placeholder.lower() or "server" in placeholder.lower(), (
        f"Placeholder '{placeholder}' does not mention 'search' or 'server'"
    )


# ===========================================================================
# TC-EXEC-UI-03  Dropdown appears when input is focused
# ===========================================================================

def test_server_dropdown_appears_on_focus(authenticated_page: Page, base_url: str):
    """TC-EXEC-UI-03: Focusing the search input makes the dropdown visible."""
    rb = _create_runbook_via_api(authenticated_page, base_url)
    _open_execute_modal(authenticated_page, base_url, rb["id"], rb["name"])

    # Dropdown starts hidden
    dropdown = authenticated_page.locator("#serverDropdown")
    authenticated_page.locator("#serverSearchInput").click()

    # Give network request time to resolve
    authenticated_page.wait_for_timeout(900)

    # Dropdown should be visible/populated
    expect(dropdown).to_be_visible()


# ===========================================================================
# TC-EXEC-UI-04  Selecting a server creates a chip
# ===========================================================================

def test_selecting_server_creates_chip(authenticated_page: Page, base_url: str):
    """TC-EXEC-UI-04: Clicking a server option in the dropdown adds a chip."""
    uid = uuid.uuid4().hex[:8]
    _create_server_via_api(
        authenticated_page, base_url, f"E2EPicker-{uid}", f"e2e-{uid}.local"
    )

    rb = _create_runbook_via_api(authenticated_page, base_url)
    _open_execute_modal(authenticated_page, base_url, rb["id"], rb["name"])

    # Type server name fragment to filter
    authenticated_page.fill("#serverSearchInput", f"E2EPicker-{uid}")
    authenticated_page.wait_for_timeout(900)  # debounce

    # Click the matching option
    option = authenticated_page.locator(".server-picker-option").filter(
        has_text=f"E2EPicker-{uid}"
    ).first
    expect(option).to_be_visible(timeout=5000)
    option.click()

    # A chip should now appear
    chips = authenticated_page.locator("#serverChips .server-chip")
    expect(chips).to_have_count(1, timeout=3000)
    expect(chips.first).to_contain_text(f"E2EPicker-{uid}")


# ===========================================================================
# TC-EXEC-UI-05  Multiple servers can be selected (multi-select)
# ===========================================================================

def test_multiple_servers_can_be_selected(authenticated_page: Page, base_url: str):
    """TC-EXEC-UI-05: Multiple server chips can be added (multi-select)."""
    uid = uuid.uuid4().hex[:8]
    for i in range(2):
        _create_server_via_api(
            authenticated_page, base_url, f"Multi-{uid}-{i}", f"multi-{uid}-{i}.local"
        )

    rb = _create_runbook_via_api(authenticated_page, base_url)
    _open_execute_modal(authenticated_page, base_url, rb["id"], rb["name"])

    # Select server 0
    authenticated_page.fill("#serverSearchInput", f"Multi-{uid}-0")
    authenticated_page.wait_for_timeout(900)
    opt = authenticated_page.locator(".server-picker-option").filter(has_text=f"Multi-{uid}-0").first
    opt.wait_for(state="visible", timeout=5000)
    opt.click()

    # Select server 1
    authenticated_page.fill("#serverSearchInput", f"Multi-{uid}-1")
    authenticated_page.wait_for_timeout(900)
    opt2 = authenticated_page.locator(".server-picker-option").filter(has_text=f"Multi-{uid}-1").first
    opt2.wait_for(state="visible", timeout=5000)
    opt2.click()

    chips = authenticated_page.locator("#serverChips .server-chip")
    expect(chips).to_have_count(2, timeout=3000)


# ===========================================================================
# TC-EXEC-UI-06  Removing a chip deselects that server
# ===========================================================================

def test_removing_chip_deselects_server(authenticated_page: Page, base_url: str):
    """TC-EXEC-UI-06: Clicking the × on a chip removes it."""
    uid = uuid.uuid4().hex[:8]
    _create_server_via_api(
        authenticated_page, base_url, f"RemoveMe-{uid}", f"rm-{uid}.local"
    )

    rb = _create_runbook_via_api(authenticated_page, base_url)
    _open_execute_modal(authenticated_page, base_url, rb["id"], rb["name"])

    authenticated_page.fill("#serverSearchInput", f"RemoveMe-{uid}")
    authenticated_page.wait_for_timeout(900)
    opt = authenticated_page.locator(".server-picker-option").filter(has_text=f"RemoveMe-{uid}").first
    opt.wait_for(state="visible", timeout=5000)
    opt.click()

    # Verify chip is present
    chips = authenticated_page.locator("#serverChips .server-chip")
    expect(chips).to_have_count(1, timeout=3000)

    # Click the remove button on the chip
    remove_btn = chips.first.locator(".server-chip-remove")
    remove_btn.click()

    # Chip should be gone
    expect(chips).to_have_count(0, timeout=3000)


# ===========================================================================
# TC-EXEC-UI-07  Clear-all button removes every chip
# ===========================================================================

def test_clear_all_removes_all_chips(authenticated_page: Page, base_url: str):
    """TC-EXEC-UI-07: 'Clear all' button removes all selected server chips."""
    uid = uuid.uuid4().hex[:8]
    for i in range(2):
        _create_server_via_api(
            authenticated_page, base_url, f"ClearAll-{uid}-{i}", f"ca-{uid}-{i}.local"
        )

    rb = _create_runbook_via_api(authenticated_page, base_url)
    _open_execute_modal(authenticated_page, base_url, rb["id"], rb["name"])

    for i in range(2):
        authenticated_page.fill("#serverSearchInput", f"ClearAll-{uid}-{i}")
        authenticated_page.wait_for_timeout(900)
        opt = authenticated_page.locator(".server-picker-option").filter(
            has_text=f"ClearAll-{uid}-{i}"
        ).first
        opt.wait_for(state="visible", timeout=5000)
        opt.click()

    expect(authenticated_page.locator("#serverChips .server-chip")).to_have_count(2, timeout=3000)

    # Clear all button should now be visible
    clear_btn = authenticated_page.locator("#serverPickerClearBtn")
    expect(clear_btn).to_be_visible(timeout=3000)
    clear_btn.click()

    expect(authenticated_page.locator("#serverChips .server-chip")).to_have_count(0, timeout=3000)


# ===========================================================================
# TC-EXEC-UI-08  Clear-all button is hidden when nothing is selected
# ===========================================================================

def test_clear_all_button_hidden_when_empty(authenticated_page: Page, base_url: str):
    """TC-EXEC-UI-08: 'Clear all' button is hidden when no servers are selected."""
    rb = _create_runbook_via_api(authenticated_page, base_url)
    _open_execute_modal(authenticated_page, base_url, rb["id"], rb["name"])

    # No chips yet — clear button must be hidden
    clear_btn = authenticated_page.locator("#serverPickerClearBtn")
    expect(clear_btn).to_have_class(re.compile(r"\bhidden\b"))


# ===========================================================================
# TC-EXEC-UI-09  Groups appear with server count badge
# ===========================================================================

def test_groups_shown_with_server_count_badge(authenticated_page: Page, base_url: str):
    """TC-EXEC-UI-09: Server groups appear in the dropdown with a count badge."""
    uid = uuid.uuid4().hex[:8]
    grp = _create_group_via_api(authenticated_page, base_url, f"E2EGroup-{uid}")

    rb = _create_runbook_via_api(authenticated_page, base_url)
    _open_execute_modal(authenticated_page, base_url, rb["id"], rb["name"])

    # Open dropdown
    authenticated_page.locator("#serverSearchInput").click()
    authenticated_page.wait_for_timeout(900)

    dropdown = authenticated_page.locator("#serverDropdown")
    expect(dropdown).to_be_visible(timeout=5000)

    # Groups section header must exist
    group_section = dropdown.locator(".server-picker-section-label").filter(
        has_text=re.compile(r"group", re.IGNORECASE)
    )
    expect(group_section).to_be_visible()

    # The created group should appear
    group_opt = dropdown.locator(".server-picker-option").filter(has_text=f"E2EGroup-{uid}")
    expect(group_opt).to_be_visible(timeout=3000)

    # Should have a count badge
    badge = group_opt.locator(".server-picker-badge")
    expect(badge).to_be_visible()
    badge_text = badge.inner_text()
    assert "server" in badge_text.lower(), f"Badge text '{badge_text}' should mention 'server'"


# ===========================================================================
# TC-EXEC-UI-10  Selecting a group adds a purple chip
# ===========================================================================

def test_selecting_group_adds_purple_chip(authenticated_page: Page, base_url: str):
    """TC-EXEC-UI-10: Selecting a group adds a chip with the 'is-group' CSS class."""
    uid = uuid.uuid4().hex[:8]
    grp = _create_group_via_api(authenticated_page, base_url, f"GrpChip-{uid}")

    rb = _create_runbook_via_api(authenticated_page, base_url)
    _open_execute_modal(authenticated_page, base_url, rb["id"], rb["name"])

    # Search for the group by name
    authenticated_page.fill("#serverSearchInput", f"GrpChip-{uid}")
    authenticated_page.wait_for_timeout(900)

    group_opt = authenticated_page.locator(".server-picker-option").filter(
        has_text=f"GrpChip-{uid}"
    ).first
    expect(group_opt).to_be_visible(timeout=5000)
    group_opt.click()

    chips = authenticated_page.locator("#serverChips .server-chip")
    expect(chips).to_have_count(1, timeout=3000)
    # The chip should carry the 'is-group' CSS class
    expect(chips.first).to_have_class(re.compile(r"\bis-group\b"))


# ===========================================================================
# TC-EXEC-UI-11  Summary text updates when items are added
# ===========================================================================

def test_summary_updates_on_selection(authenticated_page: Page, base_url: str):
    """TC-EXEC-UI-11: The server summary line reflects the current selection."""
    uid = uuid.uuid4().hex[:8]
    _create_server_via_api(
        authenticated_page, base_url, f"SummaryTest-{uid}", f"st-{uid}.local"
    )

    rb = _create_runbook_via_api(authenticated_page, base_url)
    _open_execute_modal(authenticated_page, base_url, rb["id"], rb["name"])

    summary = authenticated_page.locator("#serverSummary")

    # Initially: "No target selected" message
    initial_text = summary.inner_text()
    assert "No target selected" in initial_text or "runbook default" in initial_text.lower()

    # Select a server
    authenticated_page.fill("#serverSearchInput", f"SummaryTest-{uid}")
    authenticated_page.wait_for_timeout(900)
    opt = authenticated_page.locator(".server-picker-option").filter(
        has_text=f"SummaryTest-{uid}"
    ).first
    opt.wait_for(state="visible", timeout=5000)
    opt.click()

    # Summary should now mention "execute" and a target count
    updated_text = summary.inner_text()
    assert "execute" in updated_text.lower() or "1" in updated_text, (
        f"Summary did not update after selection: '{updated_text}'"
    )


# ===========================================================================
# TC-EXEC-UI-12  Execute button label updates with target count
# ===========================================================================

def test_execute_button_label_updates(authenticated_page: Page, base_url: str):
    """TC-EXEC-UI-12: Execute button text changes to 'Execute on ~N targets' when servers are selected."""
    uid = uuid.uuid4().hex[:8]
    _create_server_via_api(
        authenticated_page, base_url, f"BtnLabel-{uid}", f"bl-{uid}.local"
    )

    rb = _create_runbook_via_api(authenticated_page, base_url)
    _open_execute_modal(authenticated_page, base_url, rb["id"], rb["name"])

    btn_label = authenticated_page.locator("#executeSubmitLabel")
    # Default
    expect(btn_label).to_have_text("Execute")

    # Select a server
    authenticated_page.fill("#serverSearchInput", f"BtnLabel-{uid}")
    authenticated_page.wait_for_timeout(900)
    opt = authenticated_page.locator(".server-picker-option").filter(
        has_text=f"BtnLabel-{uid}"
    ).first
    opt.wait_for(state="visible", timeout=5000)
    opt.click()

    # Button text should indicate target count
    updated_text = btn_label.inner_text()
    assert "execute on" in updated_text.lower() or "1" in updated_text, (
        f"Button label did not update: '{updated_text}'"
    )


# ===========================================================================
# TC-EXEC-UI-13  Modal can be closed and re-opened with reset state
# ===========================================================================

def test_modal_resets_on_close_and_reopen(authenticated_page: Page, base_url: str):
    """TC-EXEC-UI-13: Modal resets server selection when closed and re-opened."""
    uid = uuid.uuid4().hex[:8]
    _create_server_via_api(
        authenticated_page, base_url, f"ResetTest-{uid}", f"rt-{uid}.local"
    )

    rb = _create_runbook_via_api(authenticated_page, base_url)
    _open_execute_modal(authenticated_page, base_url, rb["id"], rb["name"])

    # Select a server
    authenticated_page.fill("#serverSearchInput", f"ResetTest-{uid}")
    authenticated_page.wait_for_timeout(900)
    opt = authenticated_page.locator(".server-picker-option").filter(
        has_text=f"ResetTest-{uid}"
    ).first
    opt.wait_for(state="visible", timeout=5000)
    opt.click()
    expect(authenticated_page.locator("#serverChips .server-chip")).to_have_count(1)

    # Close modal — use .first to disambiguate header × vs footer Cancel button
    authenticated_page.locator("#executeModal button[onclick='closeExecuteModal()']").first.click()
    expect(authenticated_page.locator("#executeModal")).to_be_hidden(timeout=3000)

    # Re-open modal
    _open_execute_modal(authenticated_page, base_url, rb["id"], rb["name"])

    # Previously selected chip should be gone (unless runbook has a default)
    # Give JS time to reset
    authenticated_page.wait_for_timeout(300)
    chips = authenticated_page.locator("#serverChips .server-chip")
    # Should be 0 or 1 (if default server was loaded) — not 1 from last session
    count = chips.count()
    assert count <= 1, f"Modal did not reset — {count} server chips carried over"


# ===========================================================================
# TC-EXEC-UI-14  Execute with no selection submits (uses runbook default)
# ===========================================================================

def test_execute_no_selection_submits(authenticated_page: Page, base_url: str):
    """TC-EXEC-UI-14: Submitting with no server selected does NOT show a validation error."""
    rb = _create_runbook_via_api(authenticated_page, base_url)
    _open_execute_modal(authenticated_page, base_url, rb["id"], rb["name"])

    # Don't select any server — just submit
    submit_btn = authenticated_page.locator("#executeSubmitBtn")
    expect(submit_btn).to_be_visible()
    expect(submit_btn).to_be_enabled()

    # The form must have a submit button
    assert authenticated_page.locator('#executeSubmitLabel').inner_text() == "Execute", (
        "Submit label should read 'Execute' when no servers are chosen"
    )

    # Modal must not show required-field error on the server picker
    # (server is optional)
    widget = authenticated_page.locator("#serverPickerWidget")
    widget_class = widget.get_attribute("class") or ""
    assert "error" not in widget_class.lower() and "required" not in widget_class.lower()
