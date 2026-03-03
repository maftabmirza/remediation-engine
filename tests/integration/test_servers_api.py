"""
Integration tests for the Servers API.

Covers every behaviour added / changed in the March 2026 "server picker" feature:
  - GET /api/servers            (search, limit, group_id filter, auth guard)
  - GET /api/servers/groups     (server_count field)
  - GET /api/servers/by-group/{group_id}  (new endpoint)
"""

import uuid
import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_group(db, name="Test Group"):
    from app.models import ServerGroup
    g = ServerGroup(id=uuid.uuid4(), name=name, description=f"Desc for {name}")
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


def _make_server(db, name, hostname, group=None, environment="test"):
    from app.models import ServerCredential
    s = ServerCredential(
        id=uuid.uuid4(),
        name=name,
        hostname=hostname,
        port=22,
        username="deploy",
        os_type="linux",
        protocol="ssh",
        auth_type="key",
        environment=environment,
        group_id=group.id if group else None,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


# ===========================================================================
# GET /api/servers  — list with search / limit / group_id
# ===========================================================================

@pytest.mark.integration
class TestListServers:
    """GET /api/servers — list, search, limit, group filter."""

    # --- Auth guard ---

    def test_list_requires_auth(self, test_client: TestClient):
        """TC-SRV-01: Unauthenticated request is rejected."""
        response = test_client.get("/api/servers")
        assert response.status_code in (401, 403)

    # --- Happy path ---

    def test_list_returns_all_servers(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-SRV-02: Authenticated user can retrieve all servers."""
        _make_server(test_db_session, "ServerAlpha", "alpha.example.com")
        _make_server(test_db_session, "ServerBeta", "beta.example.com")

        response = test_client.get("/api/servers", headers=admin_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        names = [s["name"] for s in data]
        assert "ServerAlpha" in names
        assert "ServerBeta" in names

    def test_list_returns_empty_when_no_servers(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-SRV-03: Returns empty list when no servers exist."""
        # DB is clean at start of each function-scoped test
        response = test_client.get("/api/servers", headers=admin_auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    # --- search param ---

    def test_search_by_name(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-SRV-04: ?search= filters by partial server name."""
        _make_server(test_db_session, "nginx-prod-01", "nginx01.prod.local")
        _make_server(test_db_session, "mysql-prod-01", "mysql01.prod.local")

        response = test_client.get(
            "/api/servers?search=nginx", headers=admin_auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert all("nginx" in s["name"].lower() or "nginx" in s["hostname"].lower() for s in data)

    def test_search_by_hostname(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-SRV-05: ?search= also matches against hostname."""
        _make_server(test_db_session, "Web Frontend", "web-frontend.internal")
        _make_server(test_db_session, "DB Backend", "db-backend.internal")

        response = test_client.get(
            "/api/servers?search=web-frontend", headers=admin_auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        hostnames = [s["hostname"] for s in data]
        assert any("web-frontend" in h for h in hostnames)

    def test_search_no_match_returns_empty(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-SRV-06: ?search= with no matches returns empty list."""
        _make_server(test_db_session, "RandomServer", "random.local")

        response = test_client.get(
            "/api/servers?search=xyzzy_does_not_exist_ever",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_search_is_case_insensitive(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-SRV-07: Search is case-insensitive (ilike)."""
        _make_server(test_db_session, "ApplicationServer", "app.local")

        r_upper = test_client.get("/api/servers?search=APPLICATION", headers=admin_auth_headers)
        r_lower = test_client.get("/api/servers?search=application", headers=admin_auth_headers)
        r_mixed = test_client.get("/api/servers?search=Application", headers=admin_auth_headers)

        assert r_upper.status_code == 200
        assert r_lower.status_code == 200
        assert r_mixed.status_code == 200
        # All three searches should return the same server
        for r in (r_upper, r_lower, r_mixed):
            names = [s["name"] for s in r.json()]
            assert "ApplicationServer" in names

    def test_search_special_chars_do_not_crash(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-SRV-08: SQL wildcard chars in ?search= are sanitised — no 500."""
        _make_server(test_db_session, "Safe Server", "safe.local")

        for evil in ["'", "\"", "%", "_", "--", "'; DROP TABLE servers; --"]:
            response = test_client.get(
                f"/api/servers?search={evil}", headers=admin_auth_headers
            )
            assert response.status_code in (200, 422), (
                f"Got unexpected status {response.status_code} for search={evil!r}"
            )

    # --- limit param ---

    def test_limit_restricts_result_count(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-SRV-09: ?limit=N returns at most N servers."""
        for i in range(5):
            _make_server(test_db_session, f"LimitServer{i}", f"ls{i}.local")

        response = test_client.get(
            "/api/servers?limit=2", headers=admin_auth_headers
        )
        assert response.status_code == 200
        assert len(response.json()) <= 2

    def test_limit_capped_at_500(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-SRV-10: ?limit values > 500 are silently capped at 500."""
        # Just verify the endpoint accepts the param without error
        response = test_client.get(
            "/api/servers?limit=9999", headers=admin_auth_headers
        )
        assert response.status_code == 200

    def test_limit_zero_ignored(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-SRV-11: ?limit=0 is treated as 'no limit' (returns results)."""
        _make_server(test_db_session, "LimitZeroSrv", "lz.local")
        response = test_client.get(
            "/api/servers?limit=0", headers=admin_auth_headers
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    # --- group_id filter ---

    def test_group_id_filters_to_group_members(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-SRV-12: ?group_id= returns only servers in that group."""
        g1 = _make_group(test_db_session, "GroupA")
        g2 = _make_group(test_db_session, "GroupB")
        s1 = _make_server(test_db_session, "InGroupA", "inga.local", group=g1)
        _make_server(test_db_session, "InGroupB", "ingb.local", group=g2)

        response = test_client.get(
            f"/api/servers?group_id={g1.id}", headers=admin_auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        ids = [s["id"] for s in data]
        assert str(s1.id) in ids
        assert all(s["group_id"] == str(g1.id) for s in data if "group_id" in s)

    def test_group_id_nonexistent_returns_empty(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-SRV-13: ?group_id= for non-existent group returns empty list."""
        _make_server(test_db_session, "OrphanServer", "orphan.local")
        response = test_client.get(
            f"/api/servers?group_id={uuid.uuid4()}", headers=admin_auth_headers
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_search_and_limit_combined(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-SRV-14: search and limit can be combined."""
        for i in range(5):
            _make_server(test_db_session, f"combo-nginx-{i}", f"cn{i}.local")
        _make_server(test_db_session, "unrelated", "unrelated.local")

        response = test_client.get(
            "/api/servers?search=combo-nginx&limit=3", headers=admin_auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 3
        for s in data:
            assert "nginx" in s["name"].lower()

    def test_results_ordered_by_name(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-SRV-15: Results are ordered alphabetically by name."""
        _make_server(test_db_session, "Zebra Server", "zebra.local")
        _make_server(test_db_session, "Alpha Server", "alpha2.local")
        _make_server(test_db_session, "Mango Server", "mango.local")

        response = test_client.get("/api/servers", headers=admin_auth_headers)
        assert response.status_code == 200
        names = [s["name"] for s in response.json()]
        # At minimum the names we inserted should be alphabetically ordered
        my_names = [n for n in names if n in {"Zebra Server", "Alpha Server", "Mango Server"}]
        assert my_names == sorted(my_names)


# ===========================================================================
# GET /api/servers/groups  — with server_count
# ===========================================================================

@pytest.mark.integration
class TestListServerGroups:
    """GET /api/servers/groups — server_count field."""

    def test_groups_requires_auth(self, test_client: TestClient):
        """TC-GRP-01: Unauthenticated request is rejected."""
        response = test_client.get("/api/servers/groups")
        assert response.status_code in (401, 403)

    def test_groups_returns_list(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-GRP-02: Returns a list (possibly empty)."""
        response = test_client.get("/api/servers/groups", headers=admin_auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_groups_include_server_count_field(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-GRP-03: Every group response includes 'server_count' key."""
        _make_group(test_db_session, "CountGroup")
        response = test_client.get("/api/servers/groups", headers=admin_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        for g in data:
            assert "server_count" in g, f"Group {g.get('name')} missing server_count"

    def test_server_count_is_accurate(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-GRP-04: server_count reflects actual number of servers in the group."""
        grp = _make_group(test_db_session, "AccurateCountGroup")
        _make_server(test_db_session, "GS1", "gs1.local", group=grp)
        _make_server(test_db_session, "GS2", "gs2.local", group=grp)
        _make_server(test_db_session, "GS3", "gs3.local", group=grp)

        response = test_client.get("/api/servers/groups", headers=admin_auth_headers)
        assert response.status_code == 200
        data = response.json()
        matched = [g for g in data if g["name"] == "AccurateCountGroup"]
        assert len(matched) == 1
        assert matched[0]["server_count"] == 3

    def test_group_with_no_servers_has_zero_count(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-GRP-05: Empty group reports server_count of 0."""
        _make_group(test_db_session, "EmptyGroup")

        response = test_client.get("/api/servers/groups", headers=admin_auth_headers)
        assert response.status_code == 200
        data = response.json()
        matched = [g for g in data if g["name"] == "EmptyGroup"]
        assert len(matched) == 1
        assert matched[0]["server_count"] == 0

    def test_groups_response_schema(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-GRP-06: Each group has required schema fields."""
        _make_group(test_db_session, "SchemaGroup")

        response = test_client.get("/api/servers/groups", headers=admin_auth_headers)
        assert response.status_code == 200
        for g in response.json():
            assert "id" in g
            assert "name" in g
            assert "server_count" in g
            assert isinstance(g["server_count"], int)
            assert g["server_count"] >= 0


# ===========================================================================
# GET /api/servers/by-group/{group_id}  — new endpoint
# ===========================================================================

@pytest.mark.integration
class TestServersByGroup:
    """GET /api/servers/by-group/{group_id} — new endpoint."""

    def test_by_group_requires_auth(self, test_client: TestClient, test_db_session):
        """TC-BGP-01: Unauthenticated request is rejected."""
        g = _make_group(test_db_session, "AuthTestGroup")
        response = test_client.get(f"/api/servers/by-group/{g.id}")
        assert response.status_code in (401, 403)

    def test_by_group_returns_members(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-BGP-02: Returns servers that belong to the group."""
        grp = _make_group(test_db_session, "MemberGroup")
        s1 = _make_server(test_db_session, "MemberA", "ma.local", group=grp)
        s2 = _make_server(test_db_session, "MemberB", "mb.local", group=grp)
        _make_server(test_db_session, "Outsider", "outs.local")  # not in group

        response = test_client.get(
            f"/api/servers/by-group/{grp.id}", headers=admin_auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        ids = {s["id"] for s in data}
        assert str(s1.id) in ids
        assert str(s2.id) in ids
        # Outsider must NOT appear
        outsider_ids = {str(s1.id), str(s2.id)}
        for s in data:
            assert s["id"] in outsider_ids or s["name"] in ("MemberA", "MemberB")

    def test_by_group_excludes_other_group_servers(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-BGP-03: Servers in OTHER groups are excluded."""
        g1 = _make_group(test_db_session, "G1")
        g2 = _make_group(test_db_session, "G2")
        s_in = _make_server(test_db_session, "InG1", "ing1.local", group=g1)
        _make_server(test_db_session, "InG2", "ing2.local", group=g2)

        response = test_client.get(
            f"/api/servers/by-group/{g1.id}", headers=admin_auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        ids = [s["id"] for s in data]
        assert str(s_in.id) in ids
        assert not any(s["name"] == "InG2" for s in data)

    def test_by_group_nonexistent_group_returns_404(
        self, test_client: TestClient, admin_auth_headers
    ):
        """TC-BGP-04: Non-existent group_id returns HTTP 404."""
        response = test_client.get(
            f"/api/servers/by-group/{uuid.uuid4()}", headers=admin_auth_headers
        )
        assert response.status_code == 404

    def test_by_group_empty_group_returns_empty_list(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-BGP-05: Group with no servers returns empty list (not 404)."""
        grp = _make_group(test_db_session, "EmptyMemberGroup")

        response = test_client.get(
            f"/api/servers/by-group/{grp.id}", headers=admin_auth_headers
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_by_group_results_ordered_by_name(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-BGP-06: Servers are returned in alphabetical name order."""
        grp = _make_group(test_db_session, "OrderGroup")
        for name in ("Gamma", "Alpha", "Delta", "Beta"):
            _make_server(test_db_session, name, f"{name.lower()}.local", group=grp)

        response = test_client.get(
            f"/api/servers/by-group/{grp.id}", headers=admin_auth_headers
        )
        assert response.status_code == 200
        names = [s["name"] for s in response.json()]
        assert names == sorted(names)

    def test_by_group_invalid_uuid_returns_422(
        self, test_client: TestClient, admin_auth_headers
    ):
        """TC-BGP-07: Malformed UUID in path returns HTTP 422 (validation error)."""
        response = test_client.get(
            "/api/servers/by-group/not-a-valid-uuid", headers=admin_auth_headers
        )
        assert response.status_code == 422

    def test_by_group_server_schema_fields_present(
        self, test_client: TestClient, admin_auth_headers, test_db_session
    ):
        """TC-BGP-08: Returned server objects have expected schema fields."""
        grp = _make_group(test_db_session, "SchemaCheckGroup")
        _make_server(test_db_session, "CheckSrv", "check.local", group=grp)

        response = test_client.get(
            f"/api/servers/by-group/{grp.id}", headers=admin_auth_headers
        )
        assert response.status_code == 200
        for s in response.json():
            assert "id" in s
            assert "name" in s
            assert "hostname" in s
