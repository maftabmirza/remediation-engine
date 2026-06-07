"""Unit tests for monitoring configuration files."""

from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
PROMETHEUS_CONFIG_PATH = REPO_ROOT / "prometheus" / "prometheus.yml"
PROMETHEUS_ALERTS_PATH = REPO_ROOT / "prometheus" / "alerts.yml"
ALERTMANAGER_CONFIG_PATH = REPO_ROOT / "alertmanager" / "config.yml"


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.mark.unit
def test_prometheus_scrapes_new_remote_apache_host() -> None:
    """Prometheus scrapes 74.208.225.85 through its exporter ports directly."""
    config = _load_yaml(PROMETHEUS_CONFIG_PATH)

    scrape_configs = {job["job_name"]: job for job in config["scrape_configs"]}
    apache_targets = scrape_configs["apache-exporter"]["static_configs"][0]["targets"]
    node_targets = scrape_configs["node-exporter"]["static_configs"][0]["targets"]

    assert "74.208.225.85:9117" in apache_targets
    assert "74.208.225.85:9100" in node_targets


@pytest.mark.unit
def test_prometheus_alerts_define_remote_apache_host_rules() -> None:
    """Alert rules cover exporter availability and host pressure for 74.208.225.85."""
    alerts = _load_yaml(PROMETHEUS_ALERTS_PATH)

    rules = {
        rule["alert"]: rule
        for group in alerts["groups"]
        for rule in group["rules"]
    }

    assert rules["ApacheExporterDown74_208_225_85"]["expr"] == 'up{job="apache-exporter", instance="74.208.225.85:9117"} == 0'
    assert rules["NodeExporterDown74_208_225_85"]["expr"] == 'up{job="node-exporter", instance="74.208.225.85:9100"} == 0'
    assert "node_cpu_seconds_total" in rules["HighCpu74_208_225_85"]["expr"]
    assert 'instance="74.208.225.85:9100"' in rules["HighCpu74_208_225_85"]["expr"]


@pytest.mark.unit
def test_alertmanager_routes_resolved_alerts_to_aiops_webhook() -> None:
    """Alertmanager receivers continue forwarding alerts to the AIOps webhook endpoint."""
    config = _load_yaml(ALERTMANAGER_CONFIG_PATH)

    receivers = {receiver["name"]: receiver for receiver in config["receivers"]}
    expected_url = "http://remediation-engine:8080/webhook/alerts"

    for receiver_name in ["default", "critical", "warning"]:
        webhook_config = receivers[receiver_name]["webhook_configs"][0]
        assert webhook_config["url"] == expected_url
        assert webhook_config["send_resolved"] is True