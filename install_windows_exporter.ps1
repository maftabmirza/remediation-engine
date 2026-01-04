$ErrorActionPreference = "Stop"

$Version = "0.25.1"
$Installer = "windows_exporter-$Version-amd64.msi"
$Url = "https://github.com/prometheus-community/windows_exporter/releases/download/v$Version/$Installer"
$Output = "$env:TEMP\$Installer"

Write-Host "Downloading windows_exporter v$Version..."
Invoke-WebRequest -Uri $Url -OutFile $Output

Write-Host "Installing windows_exporter..."
Start-Process msiexec.exe -ArgumentList "/i $Output ENABLED_COLLECTORS=cpu,cs,logical_disk,net,os,service,system,textfile /qn" -Wait

Write-Host "Verifying service..."
if (Get-Service windows_exporter -ErrorAction SilentlyContinue) {
    Write-Host "windows_exporter installed and running."
} else {
    Write-Error "Failed to verify windows_exporter service."
}

# Add firewall rule if needed (optional, assuming port 9182 needs to be open)
# New-NetFirewallRule -DisplayName "Prometheus Windows Exporter" -Direction Inbound -LocalPort 9182 -Protocol TCP -Action Allow
