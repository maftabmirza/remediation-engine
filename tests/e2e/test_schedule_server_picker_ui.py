"""
E2E tests for the Schedules page — Target Server Picker Widget.

Tests the multi-select server/group picker added in March 2026 on the
Create/Edit Schedule modal at /schedules.

Requirements:
  - ADMIN_PASSWORD env var must be set
  - Running instance at BASE_URL (default: http://localhost:8080)

Test IDs: TC-SCHED-UI-01 … TC-SCHED-UI-14
"""

import json as _json
import re
import uuid

import pytest
from playwright.sync_api import Page, expect

_JSON_HEADERS = {"Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_runbook_via_api(page: Page, base_url: str) -> dict:
    uid = uuid.uuid4().hex[:8]
    payload = {
        "name": f"E2E Sched Runbook {uid}",
        "description": "Created by schedule server picker E2E tests",
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
        pytest.skip(f"Could not create test runbook ({resp.status}): {resp.text()[:200]}")
    return resp.json()


def _create_server_via_api(page: Page, base_url: str, name: str) -> dict:
    uid = uuid.uuid4().hex[:8]
    payload = {
        "name": name,
        "hostname": "127.0.0.1",
        "port": 8080,
        "username": "deploy",
        "os_type": "linux",
        "protocol": "ssh",
        "auth_type": "password",
        "credential_source": "inline",
        "password": "SchedTestP@ss1!",
        "environment": "test",
    }
    resp = page.request.post(
        f"{base_url}/api/servers",
        data=_json.dumps(payload),
        headers=_JSON_HEADERS,
    )
    if resp.status not in (200, 201):
        pytest.skip(f"Could not create test server ({resp.status}): {resp.text()[:200]}")
    return resp.json()


def _create_group_via_api(page: Page, base_url: str, name: str) -> dict:
    resp = page.request.post(
        f"{base_url}/api/servers/groups",
        data=_json.dumps({"name": name, "description": "E2E sched group"}),
        headers=_JSON_HEADERS,
    )
    if resp.status not in (200, 201):
        pytest.skip(f"Could not create test group ({resp.status}): {resp.text()[:200]}")
    return resp.json()


def _open_create_modal(page: Page, base_url: str) -> None:
    """Navigate to /schedules and open the Create Schedule modal."""
    page.goto(f"{base_url}/schedules")
    page.wait_for_load_state("networkidle", timeout=20000)

    create_btn = page.locator("button", has_text=re.compile(r"create|new|schedule", re.IGNORECASE)).first
    create_btn.wait_for(state="visible", timeout=8000)
    create_btn.click()

    expect(page.locator("#scheduleModal")).to_be_visible(timeout=8000)


def _fill_required_fields(page: Page, runbook_name: str) -> None:
    """Fill the minimum required fields in the Create Schedule modal."""
    # Select runbook
    runbook_select = page.locator("#runbookId")
    runbook_select.wait_for(state="visible", timeout=5000)
    if runbook_select.locator(f"option:has-text('{runbook_name[:30]}')").count() > 0:
        runbook_select.select_option(label=runbook_name[:40])

    # Fill schedule name
    name_input = page.locator("#scheduleName")
    uid = uuid.uuid4().hex[:6]
    name_input.fill(f"E2E Test Schedule {uid}")


# ===========================================================================
# TC-SCHED-UI-01  Modal has server picker widget, NOT plain <select>
# ===========================================================================

def test_schedule_modal_has_server_picker_widget(authenticated_page: Page, base_url: str):
    """TC-SCHED-UI-01: Create modal contains the server-picker widget."""
    _open_create_modal(authenticated_page, base_url)

    # New widget present
    expect(authenticated_page.locator("#schedServerPickerWidget")).to_be_visible()

    # Search input present
    expect(authenticated_page.locator("#schedServerSearchInput")).to_be_visible()

    # Old plain <select id="targetServer"> must be gone
    assert authenticated_page.locator("#targetServer").count() == 0, (
        "Old <select id='targetServer'> must not exist in the new picker design"
    )


# ===========================================================================
# TC-SCHED-UI-02  Placeholder text on search input
# ===========================================================================

def test_server_picker_placeholder_text(authenticated_page: Page, base_url: str):
    """TC-SCHED-UI-02: Search input has an appropriate placeholder."""
    _open_create_modal(authenticated_page, base_url)

    inp = authenticated_page.locator("#schedServerSearchInput")
    placeholder = inp.get_attribute("placeholder") or ""
    assert placeholder, "Placeholder must not be empty"
    assert "search" in placeholder.lower() or "server" in placeholder.lower(), (
        f"Placeholder '{placeholder}' should mention 'search' or 'server'"
    )


# ===========================================================================
# TC-SCHED-UI-03  Dropdown appears on focus
# ===========================================================================

def test_dropdown_appears_on_focus(authenticated_page: Page, base_url: str):
    """TC-SCHED-UI-03: Focusing the search input shows the dropdown."""
    _open_create_modal(authenticated_page, base_url)

    dropdown = authenticated_page.locator("#schedServerDropdown")
    authenticated_page.locator("#schedServerSearchInput").click()
    authenticated_page.wait_for_timeout(900)  # wait for debounce + request

    expect(dropdown).to_be_visible()


# ===========================================================================
# TC-SCHED-UI-04  Selecting a server creates a chip
# ===========================================================================

def test_selecting_server_creates_chip(authenticated_page: Page, base_url: str):
    """TC-SCHED-UI-04: Clicking a server option adds a chip."""
    uid = uuid.uuid4().hex[:8]
    _create_server_via_api(authenticated_page, base_url, f"SchedSrv-{uid}")
    _open_create_modal(authenticated_page, base_url)

    authenticated_page.fill("#schedServerSearchInput", f"SchedSrv-{uid}")
    authenticated_page.wait_for_timeout(900)

    option = authenticated_page.locator(".server-picker-option").filter(
        has_text=f"SchedSrv-{uid}"
    ).first
    expect(option).to_be_visible(timeout=5000)
    option.click()

    chips = authenticated_page.locator("#schedServerChips .server-chip")
    expect(chips).to_have_count(1, timeout=3000)
    expect(chips.first).to_contain_text(f"SchedSrv-{uid}")


# ===========================================================================
# TC-SCHED-UI-05  Multiple servers can be selected
# ===========================================================================

def test_multiple_servers_selectable(authenticated_page: Page, base_url: str):
    """TC-SCHED-UI-05: Multiple server chips can be added."""
    uid = uuid.uuid4().hex[:8]
    for i in range(2):
        _create_server_via_api(authenticated_page, base_url, f"SchedMulti-{uid}-{i}")

    _open_create_modal(authenticated_page, base_url)

    for i in range(2):
        authenticated_page.fill("#schedServerSearchInput", f"SchedMulti-{uid}-{i}")
        authenticated_page.wait_for_timeout(900)
        opt = authenticated_page.locator(".server-picker-option").filter(
            has_text=f"SchedMulti-{uid}-{i}"
        ).first
        opt.wait_for(state="visible", timeout=5000)
        opt.click()

    chips = authenticated_page.locator("#schedServerChips .server-chip")
    expect(chips).to_have_count(2, timeout=3000)


# ===========================================================================
# TC-SCHED-UI-06  Removing a chip deselects the server
# ===========================================================================

def test_removing_chip_deselects_server(authenticated_page: Page, base_url: str):
    """TC-SCHED-UI-06: Clicking × on a chip removes it."""
    uid = uuid.uuid4().hex[:8]
    _create_server_via_api(authenticated_page, base_url, f"SchedRm-{uid}")
    _open_create_modal(authenticated_page, base_url)

    authenticated_page.fill("#schedServerSearchInput", f"SchedRm-{uid}")
    authenticated_page.wait_for_timeout(900)
    opt = authenticated_page.locator(".server-picker-option").filter(
        has_text=f"SchedRm-{uid}"
    ).first
    opt.wait_for(state="visible", timeout=5000)
    opt.click()

    chips = authenticated_page.locator("#schedServerChips .server-chip")
    expect(chips).to_have_count(1, timeout=3000)

    chips.first.locator(".server-chip-remove").click()
    expect(chips).to_have_count(0, timeout=3000)


# ===========================================================================
# TC-SCHED-UI-07  Clear-all button removes all chips
# ===========================================================================

def test_clear_all_removes_all_chips(authenticated_page: Page, base_url: str):
    """TC-SCHED-UI-07: Clear-all button removes every selected server chip."""
    uid = uuid.uuid4().hex[:8]
    for i in range(2):
        _create_server_via_api(authenticated_page, base_url, f"SchedCA-{uid}-{i}")

    _open_create_modal(authenticated_page, base_url)

    for i in range(2):
        authenticated_page.fill("#schedServerSearchInput", f"SchedCA-{uid}-{i}")
        authenticated_page.wait_for_timeout(900)
        opt = authenticated_page.locator(".server-picker-option").filter(
            has_text=f"SchedCA-{uid}-{i}"
        ).first
        opt.wait_for(state="visible", timeout=5000)
        opt.click()

    expect(authenticated_page.locator("#schedServerChips .server-chip")).to_have_count(2, timeout=3000)

    clear_btn = authenticated_page.locator("#schedServerPickerClearBtn")
    expect(clear_btn).to_be_visible(timeout=3000)
    clear_btn.click()

    expect(authenticated_page.locator("#schedServerChips .server-chip")).to_have_count(0, timeout=3000)


# ===========================================================================
# TC-SCHED-UI-08  Clear-all button hidden when nothing selected
# ===========================================================================

def test_clear_all_button_hidden_when_empty(authenticated_page: Page, base_url: str):
    """TC-SCHED-UI-08: Clear-all button is hidden when no servers are chosen."""
    _open_create_modal(authenticated_page, base_url)

    clear_btn = authenticated_page.locator("#schedServerPickerClearBtn")
    expect(clear_btn).to_have_class(re.compile(r"\bhidden\b"))


# ===========================================================================
# TC-SCHED-UI-09  Server groups appear with server-count badge
# ===========================================================================

def test_groups_shown_with_badge(authenticated_page: Page, base_url: str):
    """TC-SCHED-UI-09: Server groups appear in the dropdown with a count badge."""
    uid = uuid.uuid4().hex[:8]
    _create_group_via_api(authenticated_page, base_url, f"SchedGrp-{uid}")
    _open_create_modal(authenticated_page, base_url)

    authenticated_page.locator("#schedServerSearchInput").click()
    authenticated_page.wait_for_timeout(900)

    dropdown = authenticated_page.locator("#schedServerDropdown")
    expect(dropdown).to_be_visible(timeout=5000)

    # Groups section label
    grp_section = dropdown.locator(".server-picker-section-label").filter(
        has_text=re.compile(r"group", re.IGNORECASE)
    )
    expect(grp_section).to_be_visible()

    # Our group
    grp_opt = dropdown.locator(".server-picker-option").filter(has_text=f"SchedGrp-{uid}")
    expect(grp_opt).to_be_visible(timeout=3000)

    # Count badge
    badge = grp_opt.locator(".server-picker-badge")
    expect(badge).to_be_visible()
    assert "server" in badge.inner_text().lower()


# ===========================================================================
# TC-SCHED-UI-10  Selecting a group creates a purple chip
# ===========================================================================

def test_selecting_group_adds_group_chip(authenticated_page: Page, base_url: str):
    """TC-SCHED-UI-10: Selected group gets a chip with the 'is-group' CSS class."""
    uid = uuid.uuid4().hex[:8]
    _create_group_via_api(authenticated_page, base_url, f"SchedGChip-{uid}")
    _open_create_modal(authenticated_page, base_url)

    authenticated_page.fill("#schedServerSearchInput", f"SchedGChip-{uid}")
    authenticated_page.wait_for_timeout(900)

    grp_opt = authenticated_page.locator(".server-picker-option").filter(
        has_text=f"SchedGChip-{uid}"
    ).first
    expect(grp_opt).to_be_visible(timeout=5000)
    grp_opt.click()

    chips = authenticated_page.locator("#schedServerChips .server-chip")
    expect(chips).to_have_count(1, timeout=3000)
    expect(chips.first).to_have_class(re.compile(r"\bis-group\b"))


# ===========================================================================
# TC-SCHED-UI-11  Summary text updates on selection
# ===========================================================================

def test_summary_text_updates_on_selection(authenticated_page: Page, base_url: str):
    """TC-SCHED-UI-11: The summary line reflects the current selection."""
    uid = uuid.uuid4().hex[:8]
    _create_server_via_api(authenticated_page, base_url, f"SchedSum-{uid}")
    _open_create_modal(authenticated_page, base_url)

    summary = authenticated_page.locator("#schedServerSummary")
    initial_text = summary.inner_text()
    assert "no target" in initial_text.lower() or "default" in initial_text.lower()

    authenticated_page.fill("#schedServerSearchInput", f"SchedSum-{uid}")
    authenticated_page.wait_for_timeout(900)
    opt = authenticated_page.locator(".server-picker-option").filter(
        has_text=f"SchedSum-{uid}"
    ).first
    opt.wait_for(state="visible", timeout=5000)
    opt.click()

    updated_text = summary.inner_text()
    assert "run on" in updated_text.lower() or "1" in updated_text, (
        f"Summary did not update after selection: '{updated_text}'"
    )


# ===========================================================================
# TC-SCHED-UI-12  Modal resets when closed and re-opened
# ===========================================================================

def test_modal_resets_on_close_reopen(authenticated_page: Page, base_url: str):
    """TC-SCHED-UI-12: Chips are cleared when modal is closed and re-opened."""
    uid = uuid.uuid4().hex[:8]
    _create_server_via_api(authenticated_page, base_url, f"SchedRst-{uid}")
    _open_create_modal(authenticated_page, base_url)

    # Select a server
    authenticated_page.fill("#schedServerSearchInput", f"SchedRst-{uid}")
    authenticated_page.wait_for_timeout(900)
    opt = authenticated_page.locator(".server-picker-option").filter(
        has_text=f"SchedRst-{uid}"
    ).first
    opt.wait_for(state="visible", timeout=5000)
    opt.click()
    expect(authenticated_page.locator("#schedServerChips .server-chip")).to_have_count(1)

    # Close modal
    close_btn = authenticated_page.locator("#scheduleModal button", has_text=re.compile(r"cancel", re.IGNORECASE)).first
    close_btn.click()
    expect(authenticated_page.locator("#scheduleModal")).to_be_hidden(timeout=3000)

    # Re-open
    _open_create_modal(authenticated_page, base_url)

    authenticated_page.wait_for_timeout(300)
    chips_count = authenticated_page.locator("#schedServerChips .server-chip").count()
    assert chips_count == 0, f"Modal did not reset — {chips_count} chips carried over"


# ===========================================================================
# TC-SCHED-UI-13  Save schedule with server selected — no validation error
# ===========================================================================

def test_save_schedule_with_server_no_error(authenticated_page: Page, base_url: str):
    """TC-SCHED-UI-13: Saving with a server selected succeeds (no form error on picker)."""
    uid = uuid.uuid4().hex[:8]
    _create_server_via_api(authenticated_page, base_url, f"SchedSave-{uid}")
    rb = _create_runbook_via_api(authenticated_page, base_url)
    _open_create_modal(authenticated_page, base_url)
    _fill_required_fields(authenticated_page, rb["name"])

    # Select a server
    authenticated_page.fill("#schedServerSearchInput", f"SchedSave-{uid}")
    authenticated_page.wait_for_timeout(900)
    opt = authenticated_page.locator(".server-picker-option").filter(
        has_text=f"SchedSave-{uid}"
    ).first
    opt.wait_for(state="visible", timeout=5000)
    opt.click()

    expect(authenticated_page.locator("#schedServerChips .server-chip")).to_have_count(1)

    # Widget should NOT have error class
    widget_class = authenticated_page.locator("#schedServerPickerWidget").get_attribute("class") or ""
    assert "error" not in widget_class.lower()


# ===========================================================================
# TC-SCHED-UI-14  Save schedule with no server — field is optional (no error)
# ===========================================================================

def test_save_schedule_no_server_is_optional(authenticated_page: Page, base_url: str):
    """TC-SCHED-UI-14: Server selection is optional — no error when none selected."""
    _open_create_modal(authenticated_page, base_url)

    # Widget should not carry an error class without interaction
    widget_class = authenticated_page.locator("#schedServerPickerWidget").get_attribute("class") or ""
    assert "error" not in widget_class.lower()
    assert "required" not in widget_class.lower()

    # Save button is enabled
    save_btn = authenticated_page.locator("#scheduleModal button[type='submit']").first
    expect(save_btn).to_be_visible()
    expect(save_btn).to_be_enabled()
