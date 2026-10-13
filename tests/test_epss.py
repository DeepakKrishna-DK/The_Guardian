import pytest
from pathlib import Path
from guardian.security.epss import EPSSClient
from guardian.security.scanner import EnvironmentScanner
from guardian.security.report import format_report
import time

def test_epss_client(tmp_path, monkeypatch):
    import requests
    
    # Mock requests to avoid real network calls
    call_count = 0
    class MockResponse:
        def __init__(self, status_code, data):
            self.status_code = status_code
            self.data = data
        def json(self):
            return self.data
            
    def mock_get(url, timeout=5):
        nonlocal call_count
        call_count += 1
        if "CVE-2022-22965" in url:
            return MockResponse(200, {"data": [{"epss": "0.95"}]})
        elif "CVE-UNKNOWN" in url:
            return MockResponse(429, {})
        raise requests.RequestException("Unreachable")
        
    monkeypatch.setattr(requests, "get", mock_get)
    
    client = EPSSClient(cache_file=tmp_path / "cache.json", ttl_seconds=1)
    
    # Initial fetch
    assert client.get_score("CVE-2022-22965") == "0.95"
    assert call_count == 1
    
    # Cache hit avoids second call
    assert client.get_score("CVE-2022-22965") == "0.95"
    assert call_count == 1
    
    # Expiry triggers refetch
    time.sleep(1.1)
    assert client.get_score("CVE-2022-22965") == "0.95"
    assert call_count == 2
    
    # API unreachable/429
    assert client.get_score("CVE-UNKNOWN") == "unknown"
    assert client.get_score("CVE-OFFLINE") == "unknown"
    
def test_scanner_epss_surface(tmp_path, monkeypatch):
    # Setup mock requirements.txt
    (tmp_path / "requirements.txt").write_text("spring-core==5.3.17")
    
    import requests
    def mock_get(*args, **kwargs):
        class MockResp:
            status_code = 200
            def json(self): return {"data": [{"epss": "0.95"}]}
        return MockResp()
    monkeypatch.setattr(requests, "get", mock_get)
    
    # Patch EPSS client inside scanner to use tmp cache so it doesn't write to .guardian
    from guardian.security.epss import EPSSClient
    original_init = EPSSClient.__init__
    def mock_init(self, cache_file=None, ttl_seconds=86400):
        original_init(self, cache_file=tmp_path / "epss.json", ttl_seconds=ttl_seconds)
    monkeypatch.setattr(EPSSClient, "__init__", mock_init)
    
    scanner = EnvironmentScanner(tmp_path)
    findings = scanner.run()
    
    cve_finding = next((f for f in findings if f.title.startswith("Spring4Shell")), None)
    assert cve_finding is not None
    assert cve_finding.context.get("epss_score") == "0.95"
    
    report_text = format_report(findings)
    assert "EPSS:     0.95" in report_text
