[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^p\d{2}$')]
    [string]$TaskId,

    [Parameter(Mandatory = $true)]
    [string]$SmokeSql,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z_][A-Za-z0-9_]*$')]
    [string]$ExpectedClass
)

$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$cacheRoot = Join-Path $workspace '.agent-cache'
$env:PRE_COMMIT_HOME = Join-Path $cacheRoot 'pre-commit'
$env:UV_CACHE_DIR = Join-Path $cacheRoot 'uv'
New-Item -ItemType Directory -Force -Path $env:PRE_COMMIT_HOME, $env:UV_CACHE_DIR | Out-Null

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$ArgumentList
    )

    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $ArgumentList"
    }
}

Push-Location $workspace
try {
    Invoke-Checked '.venv/Scripts/python.exe' '-m' 'pytest' '--cov' '-p' 'no:cacheprovider'
    Invoke-Checked '.venv/Scripts/python.exe' '-m' 'ruff' 'check' '.'
    Invoke-Checked '.venv/Scripts/python.exe' '-m' 'ruff' 'format' '--check' '.'
    Invoke-Checked '.venv/Scripts/python.exe' '-m' 'mypy' 'src'
    Invoke-Checked 'git' 'diff' '--check'

    foreach ($minor in @('3.9', '3.10', '3.11', '3.12', '3.13', '3.14', '3.15')) {
        $python = Join-Path $env:USERPROFILE ".local\bin\python$minor.exe"
        if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
            throw "Missing required CPython shim: $python"
        }
        Invoke-Checked $python '--version'
        $pytestArguments = @(
            'run', '--isolated', '--python', $python, '--extra', 'dev',
            'python'
        )
        if ($minor -eq '3.15') {
            $pytestArguments += '-W'
            $pytestArguments += 'error::DeprecationWarning'
        }
        $pytestArguments += @('-m', 'pytest', '-p', 'no:cacheprovider', '-q')
        Invoke-Checked 'uv' @pytestArguments
    }

    $distName = "dist-$TaskId"
    $distPath = Join-Path $workspace $distName
    if (Test-Path -LiteralPath $distPath) {
        throw "Refusing to reuse existing release directory: $distPath"
    }
    $wheelEnvironment = Join-Path $env:TEMP ("vertica-wheel-$TaskId-" + [guid]::NewGuid())
    try {
        Invoke-Checked '.venv/Scripts/python.exe' '-m' 'build' '--no-isolation' '--outdir' $distName
        $wheels = @(Get-ChildItem -LiteralPath $distPath -Filter '*.whl' -File)
        if ($wheels.Count -ne 1) {
            throw "Expected exactly one wheel in $distPath; found $($wheels.Count)"
        }
        Invoke-Checked '.venv/Scripts/python.exe' '-m' 'venv' $wheelEnvironment
        $wheelPython = Join-Path $wheelEnvironment 'Scripts\python.exe'
        Invoke-Checked 'uv' 'pip' 'install' '--python' $wheelPython '--reinstall' $wheels[0].FullName
        Invoke-Checked $wheelPython '-m' 'pip' 'check'

        $env:VERTICA_GATE_SMOKE_SQL = $SmokeSql
        $env:VERTICA_GATE_EXPECTED_CLASS = $ExpectedClass
        $smoke = @'
import os
from sqlglot import exp, parse_one
from sqlglot_vertica import expressions as vexp

expression = parse_one(os.environ["VERTICA_GATE_SMOKE_SQL"], read="vertica")
class_name = os.environ["VERTICA_GATE_EXPECTED_CLASS"]
expected = getattr(vexp, class_name, None) or getattr(exp, class_name)
assert isinstance(expression, expected), type(expression).__name__
assert parse_one(expression.sql(dialect="vertica"), read="vertica") == expression
print(type(expression).__name__)
'@
        Invoke-Checked $wheelPython '-I' '-c' $smoke
    }
    finally {
        Remove-Item Env:VERTICA_GATE_SMOKE_SQL -ErrorAction SilentlyContinue
        Remove-Item Env:VERTICA_GATE_EXPECTED_CLASS -ErrorAction SilentlyContinue

        $resolvedTemp = (Resolve-Path -LiteralPath $env:TEMP).Path
        if (Test-Path -LiteralPath $wheelEnvironment) {
            $resolvedWheelEnvironment = (Resolve-Path -LiteralPath $wheelEnvironment).Path
            if (-not $resolvedWheelEnvironment.StartsWith(
                $resolvedTemp + [IO.Path]::DirectorySeparatorChar
            )) {
                throw "Refusing to remove wheel environment outside TEMP: $resolvedWheelEnvironment"
            }
            Remove-Item -LiteralPath $resolvedWheelEnvironment -Recurse -Force
        }
        if (Test-Path -LiteralPath $distPath) {
            $resolvedDist = (Resolve-Path -LiteralPath $distPath).Path
            if (-not $resolvedDist.StartsWith(
                $workspace + [IO.Path]::DirectorySeparatorChar
            )) {
                throw "Refusing to remove release directory outside workspace: $resolvedDist"
            }
            Remove-Item -LiteralPath $resolvedDist -Recurse -Force
        }
    }
}
finally {
    Pop-Location
}
