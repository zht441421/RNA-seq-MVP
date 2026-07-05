$ErrorActionPreference = "Stop"

$ImageName = if ($env:DOCKER_R_IMAGE) { $env:DOCKER_R_IMAGE } else { "bioinformatics-agent-r-bulk-rnaseq:0.1" }
$DockerExecutable = if ($env:DOCKER_EXECUTABLE) { $env:DOCKER_EXECUTABLE } else { "docker" }
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Set-Location $RepoRoot

if (-not (Get-Command $DockerExecutable -ErrorAction SilentlyContinue)) {
    Write-Error "Docker executable '$DockerExecutable' was not found. Install Docker Desktop and make sure it is on PATH."
}

Write-Host "Building Docker image: $ImageName"
Write-Host "Repository root: $RepoRoot"

& $DockerExecutable build -f "docker/r-bulk-rnaseq/Dockerfile" -t $ImageName .
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Build complete: $ImageName"
Write-Host "Next checks:"
Write-Host "  scripts\test_r_docker_image.ps1"
Write-Host "  GET http://127.0.0.1:8000/system/docker-r-env"

