$build = "C:\Users\snoop\AppData\Local\PlariumPlay\StandAloneApps\raid-shadow-legends\build"
$modDir = "C:\PyAutoRaid\mod\bepinex"
$refs = "$modDir\refs"

# Create refs directory
New-Item -ItemType Directory -Force -Path $refs | Out-Null

# Copy interop assemblies we need
$interop = "$build\BepInEx\interop"
$needed = @(
    "Unity.SharedModel.dll",
    "Unity.Model.dll",
    "Unity.App.dll",
    "Unity.MVVM.dll",
    "Il2Cppmscorlib.dll",
    "Il2CppSystem.Core.dll",
    "Il2CppSystem.dll",
    "UnityEngine.CoreModule.dll",
    "UnityEngine.UI.dll",
    "UnityEngine.UIModule.dll",
    "UnityEngine.InputLegacyModule.dll"
)

foreach ($dll in $needed) {
    $src = Join-Path $interop $dll
    if (Test-Path $src) {
        Copy-Item $src $refs -Force
        Write-Output "  Copied: $dll"
    } else {
        Write-Output "  MISSING: $dll"
    }
}

# Also copy BepInEx core DLLs for compilation
$core = "$build\BepInEx\core"
$coreDlls = @(
    "BepInEx.Core.dll",
    "BepInEx.Unity.IL2CPP.dll",
    "BepInEx.Unity.Common.dll",
    "BepInEx.Preloader.Core.dll",
    "Il2CppInterop.Runtime.dll",
    "Il2CppInterop.Common.dll"
)
foreach ($dll in $coreDlls) {
    $src = Join-Path $core $dll
    if (Test-Path $src) {
        Copy-Item $src $refs -Force
        Write-Output "  Copied core: $dll"
    } else {
        Write-Output "  MISSING core: $dll"
    }
}

Write-Output "`nRefs copied. Building..."

# Build
& C:\dotnet\dotnet.exe build $modDir\RaidAutomationPlugin.csproj -c Release 2>&1

$outDll = "$modDir\bin\Release\net6.0\RaidAutomationPlugin.dll"
if (Test-Path $outDll) {
    $pluginsDir = "$build\BepInEx\plugins"
    New-Item -ItemType Directory -Force -Path $pluginsDir | Out-Null
    Copy-Item $outDll "$pluginsDir\RaidAutomationPlugin.dll" -Force
    Write-Output "`nBUILD SUCCESS - DEPLOYED to $pluginsDir"
} else {
    Write-Output "`nBUILD FAILED"
}
