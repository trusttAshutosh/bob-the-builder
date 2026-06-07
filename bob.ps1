# Bob the Builder — run from repo root: .\bob.ps1 builder-intel --open
$BobRoot = $PSScriptRoot
& python (Join-Path $BobRoot "bob.py") @args
exit $LASTEXITCODE
