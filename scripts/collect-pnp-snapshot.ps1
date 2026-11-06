# Collect a read-only, privacy-reduced Windows PnP snapshot for WP-01/WP-03.
# Run in a normal (non-elevated) PowerShell session:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\collect-pnp-snapshot.ps1
# No device, driver, registry, or firmware changes are made.

[CmdletBinding()]
param([string]$OutputPath = ".\pnp-snapshot.json")

$ErrorActionPreference = "Stop"
if (-not (Get-Command Get-PnpDevice -ErrorAction SilentlyContinue)) {
    throw "Get-PnpDevice is unavailable. Ensure the Windows PnpDevice module is installed."
}

function Get-Sha256Token {
    param([AllowNull()][string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $null }
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value.ToUpperInvariant())
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hash = $sha.ComputeHash($bytes)
        return ([BitConverter]::ToString($hash).Replace("-", "").Substring(0, 16))
    }
    finally { $sha.Dispose() }
}

function Get-DevicePropertyValue {
    param([string]$InstanceId, [string]$KeyName)
    try {
        $item = Get-PnpDeviceProperty -InstanceId $InstanceId -KeyName $KeyName -ErrorAction Stop
        return $item.Data
    }
    catch { return $null }
}

$allDevices = @(Get-PnpDevice -ErrorAction Stop)
$presentDevices = @(Get-PnpDevice -PresentOnly -ErrorAction Stop)
$presentIds = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
foreach ($device in $presentDevices) {
    if (-not [string]::IsNullOrWhiteSpace($device.InstanceId)) { [void]$presentIds.Add($device.InstanceId) }
}

# Focus on keyboard/HID/USB DevNodes; raw instance IDs and serial numbers are never exported.
$selected = @($allDevices | Where-Object {
    $_.Class -in @("Keyboard", "HIDClass", "USB") -or $_.InstanceId -match '^(USB|HID)\\'
})

$records = foreach ($device in $selected) {
    $instanceId = [string]$device.InstanceId
    $hardwareIds = @(Get-DevicePropertyValue -InstanceId $instanceId -KeyName "DEVPKEY_Device_HardwareIds")
    $compatibleIds = @(Get-DevicePropertyValue -InstanceId $instanceId -KeyName "DEVPKEY_Device_CompatibleIds")
    $idText = (@($hardwareIds) + @($compatibleIds)) -join [Environment]::NewLine
    $vidMatch = [regex]::Match($idText, '(?i)VID_([0-9A-F]{4})')
    $pidMatch = [regex]::Match($idText, '(?i)PID_([0-9A-F]{4})')

    $containerId = Get-DevicePropertyValue -InstanceId $instanceId -KeyName "DEVPKEY_Device_ContainerId"
    $parentId = Get-DevicePropertyValue -InstanceId $instanceId -KeyName "DEVPKEY_Device_Parent"
    $classGuid = Get-DevicePropertyValue -InstanceId $instanceId -KeyName "DEVPKEY_Device_ClassGuid"
    $busDescription = Get-DevicePropertyValue -InstanceId $instanceId -KeyName "DEVPKEY_Device_BusReportedDeviceDesc"
    $driverProvider = Get-DevicePropertyValue -InstanceId $instanceId -KeyName "DEVPKEY_Device_DriverProvider"
    $driverVersion = Get-DevicePropertyValue -InstanceId $instanceId -KeyName "DEVPKEY_Device_DriverVersion"
    $locationPaths = @(Get-DevicePropertyValue -InstanceId $instanceId -KeyName "DEVPKEY_Device_LocationPaths")

    [pscustomobject]@{
        instance_token = Get-Sha256Token $instanceId
        name = [string]$device.FriendlyName
        class = [string]$device.Class
        status = [string]$device.Status
        present = $presentIds.Contains($instanceId)
        manufacturer = [string]$device.Manufacturer
        hardware_ids = @($hardwareIds | ForEach-Object { [string]$_ })
        compatible_ids = @($compatibleIds | ForEach-Object { [string]$_ })
        vid = if ($vidMatch.Success) { $vidMatch.Groups[1].Value.ToUpperInvariant() } else { $null }
        pid = if ($pidMatch.Success) { $pidMatch.Groups[1].Value.ToUpperInvariant() } else { $null }
        container_token = Get-Sha256Token ([string]$containerId)
        parent_token = Get-Sha256Token ([string]$parentId)
        class_guid = [string]$classGuid
        bus_reported_description = [string]$busDescription
        location_path_count = @($locationPaths).Count
        driver_provider = [string]$driverProvider
        driver_version = [string]$driverVersion
    }
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$isElevated = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

$snapshot = [pscustomobject]@{
    schema_version = 1
    captured_at_utc = [DateTime]::UtcNow.ToString("o")
    windows_version = [System.Environment]::OSVersion.Version.ToString()
    powershell_version = $PSVersionTable.PSVersion.ToString()
    elevated = $isElevated
    total_pnp_devices = $allDevices.Count
    total_present_pnp_devices = $presentDevices.Count
    selected_device_count = @($records).Count
    devices = @($records)
}

$resolvedPath = [System.IO.Path]::GetFullPath($OutputPath)
$parentDirectory = [System.IO.Path]::GetDirectoryName($resolvedPath)
if (-not [System.IO.Directory]::Exists($parentDirectory)) {
    [void][System.IO.Directory]::CreateDirectory($parentDirectory)
}
$snapshot | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $resolvedPath -Encoding utf8
Write-Host "Snapshot written to: $resolvedPath"
Write-Host "Elevated: $isElevated | PnP devices: $($allDevices.Count) | Present: $($presentDevices.Count) | Selected: $(@($records).Count)"
Write-Warning "Review device names and hardware IDs before sharing. Raw instance IDs and serial numbers are not exported."
