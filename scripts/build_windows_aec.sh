#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
dotnet_path='/mnt/c/Program Files/dotnet/dotnet.exe'
project_path="$(wslpath -w "$project_root/windows/WindowsAecCapture/WindowsAecCapture.csproj")"
"$dotnet_path" build "$project_path" -c Release --nologo
chmod +x "$project_root/windows/WindowsAecCapture/bin/Release/net8.0-windows/WindowsAecCapture.exe"
