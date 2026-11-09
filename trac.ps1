# TRAC helper: one command for the everyday jobs.   Usage:  .\trac.ps1 <verb>      (.\trac.ps1 help lists the verbs)
#
# If Windows says scripts are blocked, do not change any system setting. Run it like this instead:
#   powershell -ExecutionPolicy Bypass -File .\trac.ps1 <verb>
#
# Before you start, set DATABASE_URL in this window, for example:
#   $env:DATABASE_URL = "postgres://user:pass@localhost:5432/trac"
# The `sync` verb also uses $env:TRAC_USER (your TRAC username); it asks if that is not set.

param(
    [Parameter(Position = 0)]
    [string]$Verb = "help",
    [switch]$Publish,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Verb and what it does, in plain words. `help` prints this list.
$HelpText = [ordered]@{
    setup  = "First time only: make the Python environment, install what TRAC needs, create the database tables."
    run    = "Start TRAC on your computer. Open http://127.0.0.1:8000/ in a browser. Press Ctrl+C to stop."
    test   = "Run the automated tests. Every line should end in dots and the last line should say 'passed'."
    check  = "Check the content files (guides, controls, risks) and the site's own settings. Changes nothing."
    sync   = "Send the content files to the site as drafts. Add -DryRun to preview, -Publish to publish (single-approver mode only)."
    export = "Write what is on the site back into the content files, so the files match the site."
    demo   = "Fill a DEMO database with sample content. Refuses unless the database name contains 'demo'."
    help   = "Show this list."
}

function Show-Help {
    Write-Host ""
    Write-Host "TRAC helper. Use:  .\trac.ps1 <verb>"
    Write-Host ""
    foreach ($name in $HelpText.Keys) {
        Write-Host ("  {0,-8}{1}" -f $name, $HelpText[$name])
    }
    Write-Host ""
    Write-Host "Each step is printed before it runs, and the helper stops at the first error."
    Write-Host ""
}

function Get-Python {
    $venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) { return $venvPython }
    return "python"
}

function Invoke-Step {
    param([string]$Program, [string[]]$Arguments)
    Write-Host ("> " + $Program + " " + ($Arguments -join " ")) -ForegroundColor Cyan
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "That step failed (exit code $LASTEXITCODE). Read the message just above this one."
    }
}

function Require-Database {
    if (-not $env:DATABASE_URL) {
        throw 'DATABASE_URL is not set. Set it first, for example: $env:DATABASE_URL = "postgres://user:pass@localhost:5432/trac"'
    }
}

try {
    switch ($Verb) {
        "setup" {
            Require-Database
            if (-not (Test-Path (Join-Path $PSScriptRoot ".venv"))) {
                Invoke-Step "python" @("-m", "venv", ".venv")
            }
            $py = Get-Python
            Invoke-Step $py @("-m", "pip", "install", "-r", "requirements.txt")
            Invoke-Step $py @("manage.py", "migrate")
            Write-Host "Setup finished. Next: .\trac.ps1 run" -ForegroundColor Green
        }
        "run" {
            Require-Database
            Invoke-Step (Get-Python) @("manage.py", "runserver")
        }
        "test" {
            Require-Database
            Invoke-Step (Get-Python) @("-m", "pytest")
        }
        "check" {
            Require-Database
            $py = Get-Python
            Invoke-Step $py @("manage.py", "check_content")
            Invoke-Step $py @("manage.py", "check")
        }
        "sync" {
            Require-Database
            $user = $env:TRAC_USER
            if (-not $user) { $user = Read-Host "Your TRAC username" }
            $arguments = @("manage.py", "sync_content", "--user", $user)
            if ($Publish) { $arguments += "--publish" }
            if ($DryRun) { $arguments += "--dry-run" }
            Invoke-Step (Get-Python) $arguments
        }
        "export" {
            Require-Database
            Invoke-Step (Get-Python) @("manage.py", "export_content")
        }
        "demo" {
            Require-Database
            $databaseName = $env:DATABASE_URL.Split("?")[0].Split("/")[-1]
            if ($databaseName -notlike "*demo*") {
                throw "Refusing to continue: the database is called '$databaseName', and a demo database must have 'demo' in its name. Point DATABASE_URL at a separate demo database."
            }
            Write-Host "WARNING: this adds demo users and sample content to the database '$databaseName'." -ForegroundColor Yellow
            Write-Host "Use it only on a demo copy, never on the real site." -ForegroundColor Yellow
            $answer = Read-Host "Type yes to continue"
            if ($answer -ne "yes") { throw "Cancelled. Nothing was changed." }
            $py = Get-Python
            Invoke-Step $py @("manage.py", "migrate")
            Invoke-Step $py @("manage.py", "load_demo")
        }
        "help" {
            Show-Help
        }
        default {
            Write-Host "Unknown verb '$Verb'." -ForegroundColor Red
            Show-Help
            exit 1
        }
    }
}
catch {
    Write-Host ("Stopped: " + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
