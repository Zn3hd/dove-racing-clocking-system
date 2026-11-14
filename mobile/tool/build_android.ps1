param(
    [string]$FlutterPath = "$env:USERPROFILE\develop\flutter\bin\flutter.bat",
    [string]$ApiUrl = 'https://dove-racing-clocking-system.onrender.com',
    [switch]$Preview,
    [string]$GradleArchive,
    [string]$GradleSha256
)
$ErrorActionPreference = 'Stop'
$source = Split-Path $PSScriptRoot -Parent
$repo = Split-Path $source -Parent
$buildRoot = Join-Path $repo ('.pytest-tmp-android-' + [guid]::NewGuid().ToString('N'))
if (!(Test-Path -LiteralPath $FlutterPath)) { throw 'Flutter SDK not found. Supply -FlutterPath.' }
New-Item -ItemType Directory -Path $buildRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $source 'pubspec.yaml') -Destination $buildRoot
foreach ($folder in @('lib','test')) { Copy-Item -LiteralPath (Join-Path $source $folder) -Destination $buildRoot -Recurse }
$env:CI = 'true'
$env:FLUTTER_SUPPRESS_ANALYTICS = 'true'
function Invoke-Flutter([string[]]$Arguments) {
    & $FlutterPath --no-version-check @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Flutter command failed: $($Arguments -join ' ')" }
}
Push-Location $buildRoot
try {
    Invoke-Flutter -Arguments @('create','--project-name','dove_racing_mobile','--platforms','android','--no-pub','.')
    if ($GradleArchive) {
        $archive = (Resolve-Path -LiteralPath $GradleArchive).Path
        if ($GradleSha256 -notmatch '^[a-fA-F0-9]{64}$' -or
            (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $GradleSha256) {
            throw 'Local Gradle archive requires its matching publisher SHA-256 checksum.'
        }
        $wrapper = Join-Path $buildRoot 'android\gradle\wrapper\gradle-wrapper.properties'
        $properties = Get-Content -LiteralPath $wrapper -Raw
        $properties = $properties -replace '(?m)^distributionUrl=.*$', ('distributionUrl=' + ([uri]$archive).AbsoluteUri)
        $properties += "`ndistributionSha256Sum=$GradleSha256`n"
        [IO.File]::WriteAllText($wrapper,$properties)
    }
    $templateTest = Join-Path $buildRoot 'test\widget_test.dart'
    if ((Test-Path -LiteralPath $templateTest) -and
        !(Test-Path -LiteralPath (Join-Path $source 'test\widget_test.dart'))) {
        Remove-Item -LiteralPath $templateTest
    }
    $manifestPath = Join-Path $buildRoot 'android\app\src\main\AndroidManifest.xml'
    [xml]$manifest = Get-Content -LiteralPath $manifestPath -Raw
    $ns = 'http://schemas.android.com/apk/res/android'
    $permission = $manifest.CreateElement('uses-permission')
    $permission.SetAttribute('name',$ns,'android.permission.INTERNET')
    $manifest.manifest.AppendChild($permission) | Out-Null
    $manifest.manifest.application.SetAttribute('label',$ns,'Pigeon Racing (Test)')
    $manifest.manifest.application.SetAttribute('allowBackup',$ns,'false')
    $manifest.manifest.application.SetAttribute('usesCleartextTraffic',$ns,'false')
    $manifest.Save($manifestPath)
    Invoke-Flutter -Arguments @('pub','get')
    Invoke-Flutter -Arguments @('analyze')
    Invoke-Flutter -Arguments @('test')
    $buildArgs = @('build','apk','--debug','--target-platform','android-arm64',"--dart-define=API_BASE_URL=$ApiUrl")
    if ($Preview) { $buildArgs += '--dart-define=WEB_PREVIEW=true' }
    Invoke-Flutter -Arguments $buildArgs
    $apk = Join-Path $buildRoot 'build\app\outputs\flutter-apk\app-debug.apk'
    $outputDir = Join-Path $repo 'dist\android'
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    $output = Join-Path $outputDir 'pigeon-racing-debug-arm64.apk'
    Copy-Item -LiteralPath $apk -Destination $output -Force
    Write-Output ('SHA256: ' + (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash)
    Write-Output "ARM64 test APK: $output"
} finally { Pop-Location }
