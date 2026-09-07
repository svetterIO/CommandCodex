param(
    [string]$Image = "commandcodex",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
podman run --rm -it -p "127.0.0.1:${Port}:80" $Image
if ($LASTEXITCODE -ne 0) { throw "podman run failed with exit code $LASTEXITCODE" }
