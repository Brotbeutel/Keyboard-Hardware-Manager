# Read-only, privacy-reduced Windows PnP snapshot for WP-01/WP-03.
# Run in a normal (non-elevated) PowerShell session.
# Property retrieval is batched, time-bounded, and may produce a marked partial snapshot.

[CmdletBinding()]
param(
    [string]$OutputPath = ".\pnp-snapshot.json",
    [ValidateRange(10, 180)][int]$EnumerationTimeoutSeconds = 60,
    [ValidateRange(1, 10000)][int]$MaxSelectedDevices = 1000,
    [ValidateRange(10, 600)][int]$MaxPropertySeconds = 300,
    [ValidateRange(10, 500)][int]$BatchSize = 100,
    [ValidateRange(5, 120)][int]$BatchTimeoutSeconds = 45
)

$ErrorActionPreference = "Stop"
if (-not (Get-Command Get-PnpDevice -ErrorAction SilentlyContinue)) {
    throw "Get-PnpDevice is unavailable. Ensure the Windows PnpDevice module is installed."
}
if (-not (Get-Command Get-PnpDeviceProperty -ErrorAction SilentlyContinue)) {
    throw "Get-PnpDeviceProperty is unavailable. Ensure the Windows PnpDevice module is installed."
}

function Invoke-BoundedPnpEnumeration {
    param([bool]$PresentOnly, [int]$TimeoutSeconds)

    $job = Start-Job -ScriptBlock {
        param($OnlyPresent)
        Import-Module PnpDevice -ErrorAction Stop
        if ($OnlyPresent) {
            Get-PnpDevice -PresentOnly -ErrorAction Stop
        }
        else {
            Get-PnpDevice -ErrorAction Stop
        }
    } -ArgumentList $PresentOnly

    try {
        $finished = Wait-Job -Job $job -Timeout $TimeoutSeconds
        if ($null -eq $finished -or $job.State -ne "Completed") {
            Stop-Job -Job $job -ErrorAction SilentlyContinue
            throw "PnP enumeration exceeded its $TimeoutSeconds second time limit."
        }
        $items = @(Receive-Job -Job $job -ErrorAction Stop)
        return $items
    }
    finally {
        if ($null -ne $job) {
            if ($job.State -eq "Running" -or $job.State -eq "NotStarted") {
                Stop-Job -Job $job -ErrorAction SilentlyContinue
            }
            Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
        }
    }
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

function Get-MapValue {
    param([hashtable]$Map, [string]$InstanceId, [string]$KeyName)
    if ($Map.ContainsKey($InstanceId) -and $Map[$InstanceId].ContainsKey($KeyName)) {
        return $Map[$InstanceId][$KeyName]
    }
    return $null
}

function Get-UsbVidPid {
    param([object[]]$Identifiers)
    foreach ($identifier in $Identifiers) {
        $text = [string]$identifier
        if ($text -notmatch '^(?i:USB)\\') { continue }
        $vidMatch = [regex]::Match($text, '(?i)VID_([0-9A-F]{4})')
        $pidMatch = [regex]::Match($text, '(?i)PID_([0-9A-F]{4})')
        if ($vidMatch.Success -and $pidMatch.Success) {
            return [pscustomobject]@{ Vid = $vidMatch.Groups[1].Value.ToUpperInvariant(); Pid = $pidMatch.Groups[1].Value.ToUpperInvariant() }
        }
    }
    return [pscustomobject]@{ Vid = $null; Pid = $null }
}

Write-Host "Enumerating Windows PnP devices (timeout: $EnumerationTimeoutSeconds s)..."
$allDevices = @(Invoke-BoundedPnpEnumeration -PresentOnly $false -TimeoutSeconds $EnumerationTimeoutSeconds)
Write-Host "Enumerating currently present PnP devices (timeout: $EnumerationTimeoutSeconds s)..."
$presentDevices = @(Invoke-BoundedPnpEnumeration -PresentOnly $true -TimeoutSeconds $EnumerationTimeoutSeconds)

$presentIds = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
foreach ($device in $presentDevices) {
    if (-not [string]::IsNullOrWhiteSpace([string]$device.InstanceId)) { [void]$presentIds.Add([string]$device.InstanceId) }
}

# Focus on keyboard/HID/USB DevNodes. Keep interfaces separate.
$selected = @($allDevices | Where-Object {
    $_.Class -in @("Keyboard", "HIDClass", "USB") -or ([string]$_.InstanceId -match '^(USB|HID)\\')
})
$selectedTotal = $selected.Count
$selectionTruncated = $false
if ($selectedTotal -gt $MaxSelectedDevices) {
    $selected = @($selected | Select-Object -First $MaxSelectedDevices)
    $selectionTruncated = $true
    Write-Warning "Selected device limit reached: processing $MaxSelectedDevices of $selectedTotal devices."
}
$selectedIds = @($selected | ForEach-Object { [string]$_.InstanceId } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })

# Batch all requested properties for multiple devices. This replaces the old
# per-device loop with ten separate Get-PnpDeviceProperty invocations.
$propertyKeys = @(
    "DEVPKEY_Device_HardwareIds",
    "DEVPKEY_Device_CompatibleIds",
    "DEVPKEY_Device_ContainerId",
    "DEVPKEY_Device_Parent",
    "DEVPKEY_Device_ClassGuid",
    "DEVPKEY_Device_BusReportedDeviceDesc",
    "DEVPKEY_Device_DriverProvider",
    "DEVPKEY_Device_DriverVersion",
    "DEVPKEY_Device_LocationPaths"
)
$propertyMap = @{}
$propertyErrors = 0
$propertyScanComplete = $true
$propertyStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$chunks = [Math]::Ceiling($selectedIds.Count / [double]$BatchSize)
$propertyJob = $null

try {
    for ($offset = 0; $offset -lt $selectedIds.Count; $offset += $BatchSize) {
        if ($propertyStopwatch.Elapsed.TotalSeconds -ge $MaxPropertySeconds) {
            $propertyScanComplete = $false
            Write-Warning "Property time budget of $MaxPropertySeconds seconds reached. Keeping collected partial data."
            break
        }

        $remainingSeconds = $MaxPropertySeconds - $propertyStopwatch.Elapsed.TotalSeconds
        if ($remainingSeconds -le 0) {
            $propertyScanComplete = $false
            Write-Warning "Property time budget of $MaxPropertySeconds seconds reached. Keeping collected partial data."
            break
        }
        $effectiveBatchTimeout = [Math]::Max(1, [Math]::Min($BatchTimeoutSeconds, [Math]::Ceiling($remainingSeconds)))

        $chunk = @($selectedIds | Select-Object -Skip $offset -First $BatchSize)
        $batchNumber = [Math]::Floor($offset / $BatchSize) + 1
        $percent = [Math]::Min(100, (($offset + $chunk.Count) / [Math]::Max(1, $selectedIds.Count)) * 100)
        Write-Progress -Activity "Reading PnP properties" -Status "Batch $batchNumber of $chunks ($($chunk.Count) devices)" -PercentComplete $percent

        try {
            $propertyJob = Get-PnpDeviceProperty -InstanceId $chunk -KeyName $propertyKeys -ThrottleLimit 8 -AsJob -ErrorAction Stop
            $completed = Wait-Job -Job $propertyJob -Timeout $effectiveBatchTimeout
            if ($null -eq $completed -or $propertyJob.State -ne "Completed") {
                $propertyScanComplete = $false
                $propertyErrors++
                Write-Warning "Property batch $batchNumber exceeded $effectiveBatchTimeout seconds and was stopped."
                Stop-Job -Job $propertyJob -ErrorAction SilentlyContinue
            }
            else {
                $batchResults = @(Receive-Job -Job $propertyJob -ErrorAction SilentlyContinue)
                foreach ($property in $batchResults) {
                    $instanceId = [string]$property.Device
                    if ([string]::IsNullOrWhiteSpace($instanceId)) { $instanceId = [string]$property.InstanceId }
                    $keyName = [string]$property.KeyName
                    if ([string]::IsNullOrWhiteSpace($instanceId) -or [string]::IsNullOrWhiteSpace($keyName)) { continue }
                    if (-not $propertyMap.ContainsKey($instanceId)) { $propertyMap[$instanceId] = @{} }
                    $propertyMap[$instanceId][$keyName] = $property.Data
                }
                if (@($propertyJob.ChildJobs | Where-Object { $_.State -eq "Failed" }).Count -gt 0) {
                    $propertyErrors++
                    $propertyScanComplete = $false
                }
            }
        }
        catch {
            $propertyErrors++
            Write-Warning "Property batch $batchNumber failed: $($_.Exception.Message)"
        }
        finally {
            if ($null -ne $propertyJob) {
                Remove-Job -Job $propertyJob -Force -ErrorAction SilentlyContinue
                $propertyJob = $null
            }
        }
    }
}
finally {
    if ($null -ne $propertyJob) {
        Stop-Job -Job $propertyJob -ErrorAction SilentlyContinue
        Remove-Job -Job $propertyJob -Force -ErrorAction SilentlyContinue
    }
    Write-Progress -Activity "Reading PnP properties" -Completed
    $propertyStopwatch.Stop()
}

$records = foreach ($device in $selected) {
    $instanceId = [string]$device.InstanceId
    $hardwareIds = @(Get-MapValue -Map $propertyMap -InstanceId $instanceId -KeyName "DEVPKEY_Device_HardwareIds")
    $compatibleIds = @(Get-MapValue -Map $propertyMap -InstanceId $instanceId -KeyName "DEVPKEY_Device_CompatibleIds")
    $allIds = @($hardwareIds) + @($compatibleIds)
    $usbIds = Get-UsbVidPid -Identifiers $allIds
    $locationPaths = @(Get-MapValue -Map $propertyMap -InstanceId $instanceId -KeyName "DEVPKEY_Device_LocationPaths")

    [pscustomobject]@{
        instance_token = Get-Sha256Token $instanceId
        name = [string]$device.FriendlyName
        class = [string]$device.Class
        status = [string]$device.Status
        present = $presentIds.Contains($instanceId)
        manufacturer = [string]$device.Manufacturer
        hardware_ids = @($hardwareIds | ForEach-Object { [string]$_ })
        compatible_ids = @($compatibleIds | ForEach-Object { [string]$_ })
        vid = $usbIds.Vid
        pid = $usbIds.Pid
        container_token = Get-Sha256Token ([string](Get-MapValue -Map $propertyMap -InstanceId $instanceId -KeyName "DEVPKEY_Device_ContainerId"))
        parent_token = Get-Sha256Token ([string](Get-MapValue -Map $propertyMap -InstanceId $instanceId -KeyName "DEVPKEY_Device_Parent"))
        class_guid = [string](Get-MapValue -Map $propertyMap -InstanceId $instanceId -KeyName "DEVPKEY_Device_ClassGuid")
        bus_reported_description = [string](Get-MapValue -Map $propertyMap -InstanceId $instanceId -KeyName "DEVPKEY_Device_BusReportedDeviceDesc")
        location_path_count = @($locationPaths).Count
        driver_provider = [string](Get-MapValue -Map $propertyMap -InstanceId $instanceId -KeyName "DEVPKEY_Device_DriverProvider")
        driver_version = [string](Get-MapValue -Map $propertyMap -InstanceId $instanceId -KeyName "DEVPKEY_Device_DriverVersion")
    }
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$isElevated = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

$snapshot = [pscustomobject]@{
    schema_version = 2
    captured_at_utc = [DateTime]::UtcNow.ToString("o")
    windows_version = [System.Environment]::OSVersion.Version.ToString()
    powershell_version = $PSVersionTable.PSVersion.ToString()
    elevated = $isElevated
    total_pnp_devices = $allDevices.Count
    total_present_pnp_devices = $presentDevices.Count
    selected_device_count = @($records).Count
    selected_device_limit = $MaxSelectedDevices
    selected_device_count_before_limit = $selectedTotal
    selection_truncated = $selectionTruncated
    property_scan_complete = $propertyScanComplete
    property_errors = $propertyErrors
    property_devices_with_data = $propertyMap.Count
    property_elapsed_seconds = [Math]::Round($propertyStopwatch.Elapsed.TotalSeconds, 2)
    devices = @($records)
}

$resolvedPath = [System.IO.Path]::GetFullPath($OutputPath)
$parentDirectory = [System.IO.Path]::GetDirectoryName($resolvedPath)
if (-not [System.IO.Directory]::Exists($parentDirectory)) { [void][System.IO.Directory]::CreateDirectory($parentDirectory) }
$tempPath = "$resolvedPath.tmp"
$json = $snapshot | ConvertTo-Json -Depth 8
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tempPath, $json, $utf8NoBom)
Move-Item -LiteralPath $tempPath -Destination $resolvedPath -Force

Write-Host ""
Write-Host "Snapshot written to: $resolvedPath"
Write-Host "Elevated: $isElevated | PnP devices: $($allDevices.Count) | Present: $($presentDevices.Count)"
Write-Host "Selected: $(@($records).Count) / $selectedTotal | Devices with properties: $($propertyMap.Count)"
Write-Host "Property scan complete: $propertyScanComplete | Errors/timeouts: $propertyErrors | Time: $($snapshot.property_elapsed_seconds)s"
if (-not $propertyScanComplete -or $selectionTruncated) {
    Write-Warning "This snapshot is partial. Check property_scan_complete and selection_truncated before using it for validation."
}
Write-Warning "Review device names and hardware IDs before sharing. Raw instance IDs and serial numbers are not exported."
