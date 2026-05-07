<#
    PyAutoRaid - one-shot installer for Windows.

    What this does:
      1. Finds Raid.exe under Plarium Play
      2. Downloads latest BepInEx IL2CPP (win x64) from GitHub if not installed
      3. Launches Raid once so BepInEx generates game interop DLLs, then closes it
      4. Copies interop + BepInEx core DLLs into mod/bepinex/refs
      5. Builds RaidAutomationPlugin.dll (requires dotnet)
      6. Copies the mod DLL into BepInEx/plugins/
      7. Installs pymem

    After this runs, `python tools/dashboard_server.py` will have a live mod API.

    Usage:
      .\install.ps1
      .\install.ps1 -SkipMod        # install BepInEx only, skip mod build
      .\install.ps1 -Reinstall      # force BepInEx re-download
#>

[CmdletBinding()]
param(
    [switch]$SkipMod,
    [switch]$Reinstall
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

function Info($m)    { Write-Host "[install] $m" -ForegroundColor Cyan }
function OK($m)      { Write-Host "[install] $m" -ForegroundColor Green }
function Warn($m)    { Write-Host "[install] $m" -ForegroundColor Yellow }
function Die($m)     { Write-Host "[install] $m" -ForegroundColor Red; exit 1 }

# 1. Find Raid
Info "Locating Raid.exe..."
$raidExe = Get-ChildItem "$env:LOCALAPPDATA\PlariumPlay\StandAloneApps" -Filter "Raid.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $raidExe) {
    Die "Raid.exe not found under $env:LOCALAPPDATA\PlariumPlay\StandAloneApps. Install Raid via Plarium Play first."
}
$raidDir = $raidExe.Directory.FullName
OK "Found Raid at $raidDir"

# 2. BepInEx install
$bepDir = Join-Path $raidDir "BepInEx"
$coreDir = Join-Path $bepDir "core"
$interopDir = Join-Path $bepDir "interop"
$pluginsDir = Join-Path $bepDir "plugins"
$doorstop = Join-Path $raidDir "winhttp.dll"
$needsBepInEx = $Reinstall -or -not (Test-Path $doorstop) -or -not (Test-Path $coreDir)

if ($needsBepInEx) {
    # Pinned to BE.755 for stable Il2CppInterop runtime. BE.755 no longer
    # generates Il2Cppmscorlib.dll (the mod csproj references it for compile-
    # time resolution), so we keep a copy of BE.741's Il2Cppmscorlib.dll in
    # mod/bepinex/refs/ as a compile-only shim. At runtime the mod DLL doesn't
    # depend on types from it.
    $zipUrl = "https://builds.bepinex.dev/projects/bepinex_be/755/BepInEx-Unity.IL2CPP-win-x64-6.0.0-be.755%2B3fab71a.zip"
    Info "Downloading pinned BepInEx BE.755..."

    # Clean stale BepInEx install if reinstalling
    if ((Test-Path $bepDir) -and $Reinstall) {
        Info "Removing old BepInEx install..."
        Remove-Item -Recurse -Force $bepDir
        Remove-Item -Force (Join-Path $raidDir "winhttp.dll") -ErrorAction SilentlyContinue
        Remove-Item -Force (Join-Path $raidDir "doorstop_config.ini") -ErrorAction SilentlyContinue
        Remove-Item -Force (Join-Path $raidDir ".doorstop_version") -ErrorAction SilentlyContinue
    }

    $zip = Join-Path $env:TEMP ("bepinex_" + [IO.Path]::GetFileName($zipUrl))
    Info "Downloading $zipUrl..."
    Invoke-WebRequest $zipUrl -OutFile $zip -UseBasicParsing
    Info "Extracting into $raidDir..."
    Expand-Archive -Path $zip -DestinationPath $raidDir -Force
    Remove-Item $zip
    OK "BepInEx installed"
} else {
    OK "BepInEx already present (use -Reinstall to overwrite)"
}

# 3. Generate interop if missing
$interopProbe = Join-Path $interopDir "Unity.App.dll"
if (-not (Test-Path $interopProbe)) {
    Info "Launching Raid once so BepInEx can generate interop DLLs..."
    Info "  You may see a Plarium login prompt - you do NOT need to log in; the interop gen runs before login."
    $proc = Start-Process -FilePath $raidExe.FullName -WorkingDirectory $raidDir -PassThru
    $ok = $false
    for ($i = 0; $i -lt 60; $i++) {    # up to 5 min
        Start-Sleep 5
        if (Test-Path $interopProbe) { $ok = $true; break }
        Write-Host -NoNewline "."
    }
    Write-Host ""
    if (-not $ok) { Die "Interop DLLs not generated after 5 min. Check $bepDir\LogOutput.log" }
    try {
        Get-Process -Name "Raid" -ErrorAction SilentlyContinue | ForEach-Object { $_.Kill(); $_.WaitForExit(10000) }
    } catch {}
    # Wait for file handles on interop DLLs to release
    for ($i = 0; $i -lt 10; $i++) {
        try {
            $fs = [IO.File]::Open($interopProbe, 'Open', 'Read', 'None')
            $fs.Close()
            break
        } catch {
            Start-Sleep 1
        }
    }
    OK "Interop generated"
} else {
    OK "Interop already present"
}

if ($SkipMod) {
    OK "Done (-SkipMod)"
    exit 0
}

# 4. Copy interop + core into refs/
$refs = Join-Path $repoRoot "mod\bepinex\refs"
New-Item -ItemType Directory -Force -Path $refs | Out-Null
$interopDlls = @(
    "Unity.SharedModel.dll","Unity.Model.dll","Unity.App.dll","Unity.MVVM.dll",
    "Il2Cppmscorlib.dll","Il2CppSystem.Core.dll","Il2CppSystem.dll",
    "UnityEngine.CoreModule.dll","UnityEngine.UI.dll","UnityEngine.UIModule.dll",
    "UnityEngine.InputLegacyModule.dll"
)
$coreDlls = @(
    "0Harmony.dll","BepInEx.Core.dll","BepInEx.Unity.IL2CPP.dll",
    "BepInEx.Unity.Common.dll","BepInEx.Preloader.Core.dll",
    "Il2CppInterop.Runtime.dll","Il2CppInterop.Common.dll"
)
foreach ($d in $interopDlls) {
    $src = Join-Path $interopDir $d
    if (Test-Path $src) { Copy-Item $src $refs -Force } else { Warn "missing interop: $d" }
}
foreach ($d in $coreDlls) {
    $src = Join-Path $coreDir $d
    if (Test-Path $src) { Copy-Item $src $refs -Force } else { Warn "missing core: $d" }
}
OK "References staged in $refs"

# 5. Build mod
$dotnet = Get-Command dotnet -ErrorAction SilentlyContinue
if (-not $dotnet) { Die "dotnet not found on PATH. Install .NET SDK 6+: https://dotnet.microsoft.com/download" }
$csproj = Join-Path $repoRoot "mod\bepinex\RaidAutomationPlugin.csproj"
Info "Building $csproj..."
& dotnet build $csproj -c Release --nologo -v minimal
if ($LASTEXITCODE -ne 0) { Die "dotnet build failed" }
$builtDll = Join-Path $repoRoot "mod\bepinex\bin\Release\net6.0\RaidAutomationPlugin.dll"
if (-not (Test-Path $builtDll)) { Die "Build succeeded but DLL missing at $builtDll" }
OK "Mod built"

# 6. Install plugin
New-Item -ItemType Directory -Force -Path $pluginsDir | Out-Null
Copy-Item $builtDll $pluginsDir -Force
OK "Mod installed -> $pluginsDir\RaidAutomationPlugin.dll"

# 7. pymem
Info "Ensuring pymem is installed..."
& python -m pip install --quiet pymem 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Warn "pip install pymem had issues - install manually if dashboard memory reader fails" }

OK ""
OK "Install complete."
OK "  1. Launch Raid via Plarium Play (or directly)"
OK "  2. python tools/dashboard_server.py"
OK "  3. Open http://localhost:8000/PyAutoRaid%20Dashboard.html"
