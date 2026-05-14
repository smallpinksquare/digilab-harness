# course_archive/run_all.ps1
# 一键重跑所有课程实验的 synth + verify，并验证产物 SHA256 与迁移前基线一致。
# 需要先在 digilab-harness/ 根目录执行过 pip install -e .
#
# 用法（从任意目录）：
#   powershell -File path\to\course_archive\run_all.ps1
# 或跳过 SHA256 校验：
#   powershell -File path\to\course_archive\run_all.ps1 --no-check

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
python "$ScriptDir\run_all.py" @args
exit $LASTEXITCODE
