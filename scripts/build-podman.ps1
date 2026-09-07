param(
    [string]$Image = "commandcodex",
    [string]$Password
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($Password)) {
    $secure = Read-Host "Content password" -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $Password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

try {
    $env:CONTENT_PASSWORD = $Password
    podman build --no-cache `
      --build-arg "CONTENT_PASSWORD=$env:CONTENT_PASSWORD" `
      -t $Image .
    if ($LASTEXITCODE -ne 0) { throw "podman build failed with exit code $LASTEXITCODE" }
}
finally {
    Remove-Item Env:CONTENT_PASSWORD -ErrorAction SilentlyContinue
}
