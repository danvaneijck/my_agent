"""Benchmarker module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="benchmarker",
    description="Interact with the Benchmarker IoT monitoring platform to look up LoRa devices, check sensor health, manage issues, send downlink commands, and provision organisations.",
    tools=[
        ToolDefinition(
            name="benchmarker.device_lookup",
            description=(
                "Look up an IoT device by serial number on the Benchmarker platform. "
                "Returns device info, location in the organisation hierarchy (org/site/zone), "
                "latest sensor readings (temperature, humidity, battery), and linked assets. "
                "Serial prefixes indicate device type: CEL=Celsor (temperature), MRP=MeterReader, "
                "DOR=DoorInformer, SPC/PEP=SpaceMon, HVN=HVAC, HTL=HeadTeller, WMN=WaterMon, "
                "PUK=TemperatureBeacon, OCT=MagBeacon, WWH=WashWatch, VAC=VAC, PWR=PowerReader, SOL=Spectra."
            ),
            parameters=[
                ToolParameter(
                    name="serial_number",
                    type="string",
                    description="Device serial number, e.g. CEL-12345",
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="benchmarker.send_downlink",
            description=(
                "Send a CLI command to a LoRa IoT device via the Benchmarker platform. "
                "The command is queued and sent asynchronously on the next downlink window. "
                "Common commands: 'version', 'reboot', 'config'."
            ),
            parameters=[
                ToolParameter(
                    name="serial_number",
                    type="string",
                    description="Target device serial number, e.g. CEL-12345",
                ),
                ToolParameter(
                    name="cli_command",
                    type="string",
                    description="CLI command to send to the device (e.g. 'version', 'reboot', 'config')",
                ),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="benchmarker.organisation_summary",
            description=(
                "Get an overview of an organisation on the Benchmarker IoT platform including "
                "site/zone/device counts, device health stats, active issues, and subscriptions. "
                "Search by organisation name (fuzzy) or short_name (exact, max 4 chars)."
            ),
            parameters=[
                ToolParameter(
                    name="name",
                    type="string",
                    description="Organisation name (fuzzy match, case-insensitive)",
                    required=False,
                ),
                ToolParameter(
                    name="short_name",
                    type="string",
                    description="Organisation short code (exact match, max 4 chars)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="benchmarker.site_overview",
            description=(
                "Get details about a specific site on the Benchmarker IoT platform including "
                "address, per-zone device breakdown, device types, and online/offline counts. "
                "Look up by site_id (direct) or by name with optional organisation filter."
            ),
            parameters=[
                ToolParameter(
                    name="site_id",
                    type="integer",
                    description="Site ID for direct lookup",
                    required=False,
                ),
                ToolParameter(
                    name="name",
                    type="string",
                    description="Site name (fuzzy match)",
                    required=False,
                ),
                ToolParameter(
                    name="organisation",
                    type="string",
                    description="Organisation short_name to narrow site name search",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="benchmarker.silent_devices",
            description=(
                "Find IoT devices on the Benchmarker platform that haven't reported within a "
                "given time window. Useful for identifying connectivity or hardware issues. "
                "Can filter by organisation, site, or device type."
            ),
            parameters=[
                ToolParameter(
                    name="hours",
                    type="integer",
                    description="Hours of silence to consider a device 'silent' (default 24)",
                    required=False,
                ),
                ToolParameter(
                    name="organisation",
                    type="string",
                    description="Filter by organisation short_name",
                    required=False,
                ),
                ToolParameter(
                    name="site_id",
                    type="integer",
                    description="Filter by site ID",
                    required=False,
                ),
                ToolParameter(
                    name="device_type",
                    type="string",
                    description="Filter by device type",
                    enum=[
                        "Celsor", "MeterReader", "DoorInformer", "SpaceMon",
                        "HVAC", "HeadTeller", "WaterMon", "TemperatureBeacon",
                        "MagBeacon", "WASHWATCH", "VAC", "PowerReader", "Spectra",
                    ],
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="benchmarker.low_battery_devices",
            description=(
                "Find IoT devices on the Benchmarker platform whose latest battery reading "
                "is below a threshold percentage. Useful for planning battery replacements. "
                "Can filter by organisation or site."
            ),
            parameters=[
                ToolParameter(
                    name="threshold",
                    type="integer",
                    description="Battery percentage threshold (default 20)",
                    required=False,
                ),
                ToolParameter(
                    name="organisation",
                    type="string",
                    description="Filter by organisation short_name",
                    required=False,
                ),
                ToolParameter(
                    name="site_id",
                    type="integer",
                    description="Filter by site ID",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="benchmarker.device_issues",
            description=(
                "Get open issues for a specific IoT device on the Benchmarker platform. "
                "Returns issue key, summary, priority, status, and linked asset. "
                "Optionally include closed/resolved issues."
            ),
            parameters=[
                ToolParameter(
                    name="serial_number",
                    type="string",
                    description="Device serial number, e.g. CEL-12345",
                ),
                ToolParameter(
                    name="include_closed",
                    type="boolean",
                    description="Whether to include resolved/closed issues (default false)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="benchmarker.org_issues_summary",
            description=(
                "Get issue statistics for an organisation on the Benchmarker IoT platform, "
                "broken down by status and priority. Includes active count and recent issues."
            ),
            parameters=[
                ToolParameter(
                    name="organisation",
                    type="string",
                    description="Organisation short_name",
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="benchmarker.provision_organisation",
            description=(
                "Provision new organisations and sites on the Benchmarker IoT platform. "
                "Accepts a provisioning payload with organisation details, subscriptions, "
                "and site definitions including addresses. Supports dry-run validation."
            ),
            parameters=[
                ToolParameter(
                    name="organisations",
                    type="object",
                    description=(
                        "Provisioning payload: {\"organisations\": [{\"name\": \"...\", "
                        "\"short_name\": \"...\", \"subscriptions\": [...], \"sites\": "
                        "[{\"name\": \"...\", \"short_name\": \"...\", \"address\": "
                        "{\"street\": \"...\", \"city\": \"...\", \"code\": \"...\", "
                        "\"country\": \"...\"}}]}]}"
                    ),
                ),
                ToolParameter(
                    name="dry_run",
                    type="boolean",
                    description="Validate only without creating anything (default false)",
                    required=False,
                ),
                ToolParameter(
                    name="no_geocode",
                    type="boolean",
                    description="Skip geocoding addresses (default false)",
                    required=False,
                ),
            ],
            required_permission="admin",
        ),
    ],
)
