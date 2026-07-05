$ErrorActionPreference = "Stop"

$ImageName = if ($env:DOCKER_R_IMAGE) { $env:DOCKER_R_IMAGE } else { "bioinformatics-agent-r-bulk-rnaseq:0.1" }
$DockerExecutable = if ($env:DOCKER_EXECUTABLE) { $env:DOCKER_EXECUTABLE } else { "docker" }
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not (Get-Command $DockerExecutable -ErrorAction SilentlyContinue)) {
    Write-Error "Docker executable '$DockerExecutable' was not found. Install Docker Desktop and make sure it is on PATH."
}

& $DockerExecutable image inspect $ImageName *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker image '$ImageName' was not found. Build it with scripts\build_r_docker_image.ps1."
}

$MountSpec = "type=bind,source=$RepoRoot,target=/workspace"
$DockerArgs = @(
    "run",
    "--rm",
    "--mount",
    $MountSpec,
    "-w",
    "/workspace",
    $ImageName,
    "Rscript",
    "backend/app/scripts/r/check_bioconductor_env.R"
)

Write-Host "Running R/Bioconductor environment check in image: $ImageName"
$Output = & $DockerExecutable @DockerArgs
$ExitCode = $LASTEXITCODE

if ($Output) {
    Write-Host $Output
}

if ($ExitCode -ne 0) {
    exit $ExitCode
}

try {
    $Parsed = $Output | ConvertFrom-Json
    Write-Host ""
    Write-Host "ready_for_real_r: $($Parsed.ready_for_real_r)"
    Write-Host "missing_required: $($Parsed.missing_required -join ', ')"
    Write-Host "missing_optional: $($Parsed.missing_optional -join ', ')"
    Write-Host "Package versions:"
    foreach ($Package in $Parsed.packages.PSObject.Properties) {
        Write-Host "  $($Package.Name): installed=$($Package.Value.installed), version=$($Package.Value.version)"
    }
} catch {
    Write-Warning "Could not parse environment JSON. Raw output was printed above."
}

