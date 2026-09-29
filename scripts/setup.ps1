$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 虚拟环境创建失败' }
}
$projectPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
# 优先使用官方源；额外源不可达时不反复重试。
$previousPipConfig = $env:PIP_CONFIG_FILE
$previousExtraIndex = $env:PIP_EXTRA_INDEX_URL
try {
    $env:PIP_CONFIG_FILE = 'NUL'
    $env:PIP_EXTRA_INDEX_URL = ''
    & $projectPython -m pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu --no-cache-dir --disable-pip-version-check --retries 0 --timeout 60
    if ($LASTEXITCODE -ne 0) { throw 'CPU PyTorch 安装失败，请检查网络后重试' }
    & $projectPython -m pip install -r requirements.txt --index-url https://pypi.org/simple --no-cache-dir --disable-pip-version-check --retries 0 --timeout 60
    if ($LASTEXITCODE -ne 0) { throw '依赖安装失败，请检查网络后重试' }
    & $projectPython scripts/download_model.py
    if ($LASTEXITCODE -ne 0) { throw '模型下载失败，可以重新运行本脚本' }
    & $projectPython scripts/prepare_gallery.py
    if ($LASTEXITCODE -ne 0) { throw '图库准备失败，请检查数据来源或网络' }
    Write-Host '准备完成。双击 start.cmd 即可启动。'
} finally {
    $env:PIP_CONFIG_FILE = $previousPipConfig
    $env:PIP_EXTRA_INDEX_URL = $previousExtraIndex
}
