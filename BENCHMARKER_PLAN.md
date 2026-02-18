I have a modular AI agent system. I need you to create a new module called benchmarker.

The module should provide tools that call the Benchmarker IoT monitoring platform's Agent API. The API is a Django REST API running at a configurable base URL, authenticated with a Bearer token.

API Details
Base URL: Configured via env var BENCHMARKER_API_URL (e.g. https://api.benchmarker.nz)
Auth: Authorization: Bearer <key> header, key from env var BENCHMARKER_API_KEY

Response envelope (all endpoints):


{"ok": true, "data": {...}, "error": null}
{"ok": false, "data": null, "error": {"code": "NOT_FOUND", "message": "..."}}
Tools to implement
1. benchmarker.device_lookup
Look up a device by serial number. Returns device info, location in the org hierarchy, latest sensor readings, and linked assets.

API: GET {base}/api/agent/v1/device/lookup?serial_number={serial_number}
Parameters:
serial_number (string, required) — Device serial number e.g. CEL-12345. Serial prefixes indicate device type: CEL=Celsor (temperature), MRP=MeterReader, DOR=DoorInformer, SPC/PEP=SpaceMon, HVN=HVAC, HTL=HeadTeller, WMN=WaterMon, PUK=TemperatureBeacon, OCT=MagBeacon, WWH=WashWatch, VAC=VAC, PWR=PowerReader, SOL=Spectra.
Response data shape:

{
  "device": {"serial_number": "CEL-12345", "dev_eui": "aa-bb-cc-dd-ee-ff-00-11", "firmware_version": "1.2.3", "last_packet_time": "2026-02-18T03:45:00Z", "packet_count": 14523, "time_since_last_packet": "2 hours ago"},
  "measurement_point": {"id": 42, "name": "Freezer 1", "device_type": "Celsor"},
  "location": {"organisation": "Acme Foods", "site": "Auckland Warehouse", "zone": "Cold Storage A"},
  "latest_status": {"time": "2026-02-18T03:45:00Z", "temperature": 3.5, "battery_level": 85.0, "relative_humidity": 45.2},
  "assets": ["Freezer Unit F-001"]
}
2. benchmarker.send_downlink
Send a CLI command to a device. The command is queued and sent asynchronously.

API: POST {base}/api/agent/v1/device/send-downlink
Body: {"serial_number": "CEL-12345", "cli_command": "version"}
Parameters:
serial_number (string, required) — Target device serial number
cli_command (string, required) — CLI command to send to the device (e.g. "version", "reboot", "config")
Response data shape:

{
  "serial_number": "CEL-12345", "downlink_id": 456, "cli_command": "version",
  "status": "Pending", "message": "Downlink queued for device CEL-12345"
}
3. benchmarker.organisation_summary
Get an overview of an organisation including site/zone/device counts, health stats, and subscriptions.

API: GET {base}/api/agent/v1/organisation/summary?short_name={short_name} or ?name={name}
Parameters:
name (string, optional) — Organisation name (fuzzy match, case-insensitive)
short_name (string, optional) — Organisation short code (exact match, max 4 chars). At least one of name or short_name is required.
Response data shape:

{
  "organisation": {"id": 1, "name": "Acme Foods", "short_name": "ACM", "timezone": "Pacific/Auckland"},
  "subscriptions": ["Celsor", "MeterReader"],
  "counts": {"sites": 3, "zones": 12, "measurement_points": 87, "devices_total": 90, "devices_online": 82, "devices_never_reported": 0, "devices_offline_24h": 3, "devices_offline_48h": 2, "active_issues": 5, "users": 8},
  "sites": [{"id": 1, "name": "Auckland Warehouse", "zones": 4, "measurement_points": 35}]
}
4. benchmarker.site_overview
Get details about a specific site including per-zone device breakdown and health.

API: GET {base}/api/agent/v1/site/overview?site_id={site_id} or ?name={name}&organisation={organisation}
Parameters:
site_id (integer, optional) — Site ID (direct lookup)
name (string, optional) — Site name (fuzzy match)
organisation (string, optional) — Organisation short_name to narrow site name search
Response data shape:

{
  "site": {"id": 1, "name": "Auckland Warehouse", "organisation": "Acme Foods"},
  "address": {"street": "123 Main St", "suburb": null, "city": "Auckland", "country": "New Zealand"},
  "zones": [{"name": "Cold Storage A", "measurement_points": 8, "device_types": {"Celsor": 6, "MeterReader": 2}, "devices_online": 7, "devices_offline": 1}],
  "totals": {"zones": 4, "measurement_points": 35, "devices_online": 32, "devices_offline": 3, "active_issues": 2}
}
5. benchmarker.silent_devices
Find devices that haven't reported within a given time window. Useful for identifying connectivity issues.

API: GET {base}/api/agent/v1/health/silent-devices?hours={hours}&organisation={organisation}&device_type={device_type}&site_id={site_id}
Parameters:
hours (integer, optional, default 24) — How many hours of silence to consider a device "silent"
organisation (string, optional) — Filter by organisation short_name
site_id (integer, optional) — Filter by site ID
device_type (string, optional) — Filter by device type. Values: Celsor, MeterReader, DoorInformer, SpaceMon, HVAC, HeadTeller, WaterMon, TemperatureBeacon, MagBeacon, WASHWATCH, VAC, PowerReader, Spectra
Response data shape:

{
  "threshold_hours": 24, "filters": {"organisation": "ACM"}, "count": 3,
  "devices": [{"serial_number": "CEL-12345", "last_packet_time": "2026-02-17T01:30:00Z", "hours_silent": 26.5, "measurement_point": "Freezer 1", "site": "Auckland Warehouse", "zone": "Cold Storage A"}]
}
6. benchmarker.low_battery_devices
Find devices whose latest battery reading is below a threshold.

API: GET {base}/api/agent/v1/health/low-battery?threshold={threshold}&organisation={organisation}&site_id={site_id}
Parameters:
threshold (integer, optional, default 20) — Battery percentage threshold
organisation (string, optional) — Filter by organisation short_name
site_id (integer, optional) — Filter by site ID
Response data shape:

{
  "threshold_percent": 20, "count": 2,
  "devices": [{"serial_number": "CEL-67890", "battery_level": 12.5, "reading_time": "2026-02-18T02:00:00Z", "measurement_point": "Chiller 3", "site": "Auckland Warehouse", "device_type": "Celsor"}]
}
7. benchmarker.device_issues
Get open issues for a specific device.

API: GET {base}/api/agent/v1/issues/by-device?serial_number={serial_number}&include_closed={include_closed}
Parameters:
serial_number (string, required) — Device serial number
include_closed (boolean, optional, default false) — Whether to include resolved/closed issues
Response data shape:

{
  "serial_number": "CEL-12345", "count": 2,
  "issues": [{"key": "ACM-AKL-003", "summary": "Temperature exceeds threshold", "priority": "Urgent", "status": "Pending", "time_raised": "2026-02-17T14:00:00Z", "asset": "Freezer Unit F-001"}]
}
8. benchmarker.org_issues_summary
Get issue statistics for an organisation, broken down by status and priority.

API: GET {base}/api/agent/v1/issues/org-summary?organisation={organisation}
Parameters:
organisation (string, required) — Organisation short_name
Response data shape:

{
  "organisation": "Acme Foods",
  "by_status": {"Pending": 3, "Acknowledged": 1, "In Progress": 2, "Resolved": 15, "Closed": 42},
  "by_priority": {"Urgent": 1, "Attention": 2, "Developing": 1, "Performance": 2},
  "active_count": 6,
  "recent_issues": [{"key": "ACM-AKL-003", "summary": "Temperature exceeds threshold", "priority": "Urgent", "status": "Pending", "time_raised": "2026-02-17T14:00:00Z", "site": "Auckland Warehouse"}]
}
9. benchmarker.provision_organisation
Provision new organisations and sites. Supports dry-run validation.

API: POST {base}/api/agent/v1/actions/provision-organisation?dry_run={dry_run}&no_geocode={no_geocode}
Body: {"organisations": [{"name": "New Org", "short_name": "NORG", "subscriptions": ["Celsor"], "sites": [{"name": "Site 1", "short_name": "S001", "address": {"street": "1 Main St", "city": "Auckland", "code": "1010", "country": "New Zealand"}}]}]}
Parameters:
organisations (object, required) — The full provisioning payload (passed as the request body)
dry_run (boolean, optional, default false) — Validate only, don't create anything
no_geocode (boolean, optional, default false) — Skip geocoding addresses
Response data shape (success):

{"organisations_created": 1, "organisations_existing": 0, "sites_created": 1, "sites_skipped": 0, "addresses_geocoded": 1, "geocoding_failures": 0, "details": [...]}
Response data shape (dry run):

{"dry_run": true, "valid": true, "organisation_count": 1, "message": "Validation passed. Use without dry_run to provision."}
Implementation notes
Use httpx as the async HTTP client.
Create a BenchmarkerClient class in tools.py that wraps all API calls with auth header injection, response envelope unwrapping, and error handling.
The client should check response["ok"] and raise a descriptive exception if false, using response["error"]["message"].
For the provision_organisation tool, organisations is a complex object — pass it through directly as the request body. The dry_run and no_geocode flags go as query params.
For send_downlink, use POST with JSON body. All other tools use GET with query params.
All tools need helpful descriptions that mention the IoT/monitoring domain so the LLM picks the right tool. For example, mention "LoRa IoT devices", "temperature sensors", "measurement points" etc.
Environment variables needed
Add to .env.example and shared/shared/config.py:

BENCHMARKER_API_URL — Base URL of the Benchmarker API (e.g. https://api.benchmarker.nz)
BENCHMARKER_API_KEY — Bearer token for agent API authentication
Files to create
Follow the module creation guide in docs/ADDING_MODULES.md exactly. Create all required files:

modules/benchmarker/__init__.py
modules/benchmarker/manifest.py
modules/benchmarker/tools.py
modules/benchmarker/main.py
modules/benchmarker/Dockerfile
modules/benchmarker/requirements.txt
Then update the registration points:
7. Add "benchmarker": "http://benchmarker:8000" to module_services in shared/shared/config.py
8. Add the service block to docker-compose.yml under # --- Modules ---

Permission level for all tools: user (except provision_organisation which should be admin and send_downlink which should be admin)