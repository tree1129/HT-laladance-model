param(
    [string]$RobotHost = "192.168.43.44",
    [string]$RobotUser = "hightorque",
    [string]$RemoteBase = ""
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AgentDir = Join-Path $ScriptDir "robot_agent"

if (-not (Test-Path $AgentDir)) {
    throw "robot_agent directory was not found: $AgentDir"
}

if ([string]::IsNullOrWhiteSpace($RemoteBase)) {
    $RemoteBase = "/home/$RobotUser/robot_remote_web_agent"
}

$Ssh = Get-Command ssh -ErrorAction SilentlyContinue
if (-not $Ssh) {
    throw "ssh was not found. Install Windows OpenSSH Client, Git for Windows, or use the robot manually."
}

$Scp = Get-Command scp -ErrorAction SilentlyContinue
if (-not $Scp) {
    throw "scp was not found. Install Windows OpenSSH Client or Git for Windows."
}

$Remote = "$RobotUser@$RobotHost"
$RemoteTarget = $Remote + ":" + $RemoteBase + "/"

Write-Host "Deploying robot agent to ${Remote}:$RemoteBase"
& $Ssh.Source $Remote "mkdir -p '$RemoteBase'"
& $Scp.Source -r $AgentDir $RemoteTarget

Write-Host ""
Write-Host "Deployment finished."
Write-Host ""
Write-Host "Start it on the robot:"
Write-Host "  ssh $Remote"
Write-Host "  cd $RemoteBase/robot_agent"
Write-Host "  bash start_robot_agent.sh"
Write-Host ""
Write-Host "Then open this URL in your browser:"
Write-Host "  http://$RobotHost:8766"
