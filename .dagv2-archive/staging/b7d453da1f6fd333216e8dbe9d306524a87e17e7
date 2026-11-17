#!/usr/bin/env python3
"""Derive a small WebWalker-only artifact from immutable release_v2 bytes."""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile


STAGE = Path(__file__).resolve().parent
SOURCE = STAGE / 'release_v2' / 'dagbt_benchmarks_v4_experiment'
RELEASE = STAGE / 'release_webwalker_v2'
NAME = 'dagbt_webwalker_v4_v2_experiment'
BUNDLE = RELEASE / NAME
ARCHIVE = RELEASE / (NAME + '.tar.gz')
TARGET = '~/dagbt_runs/20261017_webwalker_v4_v2_experiment/dagv2'
OLD_TARGET = '~/dagbt_runs/20261016_dual_benchmark_v4_v2/dagv2'
BASELINE = 'e6677081cdfb33c01db3aaa274a497168f314f78'
EXCLUDED = {
    'configs/browsecomp-plus-v4.json',
    'dagbt/benchmark_suite.py',
    'dagbt/browsecomp_data.py', 'dagbt/browsecomp_engine.py', 'dagbt/browsecomp_runner.py',
    'data/browsecomp_plus/corpus.sqlite3', 'data/browsecomp_plus/evaluation_only.json',
    'data/browsecomp_plus/manifest.json', 'data/browsecomp_plus/questions.jsonl',
    'docs/BENCHMARKS_UPLOAD.md',
    'scripts/browsecomp_offline_smoke.py', 'scripts/package_benchmarks.py',
    'scripts/prepare_browsecomp_plus.py', 'scripts/run_benchmarks.sh',
    'scripts/run_browsecomp_plus.sh',
    'tests/test_benchmark_package.py', 'tests/test_benchmark_suite.py',
    'tests/test_browsecomp_data.py', 'tests/test_browsecomp_engine.py',
    'tests/test_browsecomp_runner.py',
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def source_manifest():
    old = read(SOURCE / 'bundle_manifest.json')
    require(old.get('bundle_revision') == 2 and old.get('baseline_commit') == BASELINE,
            'Source is not the approved revision 2')
    require(len(old['payload_sha256']) == 175 and len(old['baseline_source_sha256']) == 107,
            'Unexpected source payload/core count')
    require(EXCLUDED <= set(old['payload_sha256'])
            and not EXCLUDED.intersection(old['baseline_source_sha256']),
            'Excluded paths must be non-core revision 2 members')
    kept = {path: digest for path, digest in old['payload_sha256'].items() if path not in EXCLUDED}
    require(len(kept) == 155, 'Expected exactly 155 retained payload files')
    require(all(kept.get(path) == digest for path, digest in old['baseline_source_sha256'].items()),
            'A public baseline member was omitted or changed')
    return old, kept


def readme():
    return """# WebWalkerQA v4 轻量 v2

本包只运行 WebWalkerQA：完整 680 题、joint/residual 两组，生成结束后自动评分。
运行文件、配置、数据、107 个公共核心文件及 PDF wheel 均精确保留自双数据集修订 2。
BrowseComp-Plus 数据与专属代码、配置、脚本和双数据集协调器已移除。
WebWalker 的 Playwright/Chromium 浏览器能力及安装脚本保留。

这是原 v2 的轻量派生包，没有加入后续 v3 算法改动。新包安装与离线验证状态见
validation.json；未重新运行付费真实题目，不声称新的真实回归或服务器全量结果。
上一轮原 v2 WebWalker 4 任务中 2 个产出最终答案，另 2 个预算耗尽；
此处不报告正确率，仅记录历史来源。

## 上传并启动

上传本目录同名 tar.gz 与 tar.gz.sha256 到服务器 ~/bt/，执行：

    cd ~/bt
    sha256sum -c dagbt_webwalker_v4_v2_experiment.tar.gz.sha256
    mkdir -p ~/dagbt_patches/webwalker_v4_v2
    tar -xzf dagbt_webwalker_v4_v2_experiment.tar.gz -C ~/dagbt_patches/webwalker_v4_v2
    export DAGBT_PYTHON="$HOME/dagbt_runs/20260930_v3/dagv2/.venv/bin/python"
    bash ~/dagbt_patches/webwalker_v4_v2/dagbt_webwalker_v4_v2_experiment/install_and_run.sh

入口依次完成独立安装、浏览器检查、WebWalker 离线夹具验证和真实服务预检，
然后在后台运行 WebWalker full。SSH 断开后继续运行。
默认新目标：~/dagbt_runs/20261017_webwalker_v4_v2_experiment/dagv2。
不覆盖旧部署、旧 tar 或旧输出。不要对同一输出重复启动 full。

仅安装及离线检查时，将入口换为 install_and_offline.sh；该入口不调用真实模型。
两个入口均接受第一参数自定义目标，第二参数 --no-browser：

    bash install_and_offline.sh /独立/目标/dagv2 --no-browser

--no-browser 仅适用于目标已经有完整且可运行的浏览器依赖。
首次浏览器安装需要访问 PyPI 和 Chromium CDN；安装器不运行 sudo。

## 来源部署与 PersonaMem

默认来源为 ~/dagbt_runs/20261014_personamem_v4_experiment/dagv2，
可用 DAGBT_PERSONAMEM_BASE 指定。来源须满足固定公共核心基线；
私人凭据不在包内，只在服务器本地从来源部署复用，权限为 0600。
沿用已有可用 Python 环境，DAGBT_PYTHON 可指定解释器。

full 使用的 PersonaMem 输出默认为上述来源部署的
outputs/personamem_v4_experiment_full，可用 PERSONAMEM_OUTPUT 指定。
该输出必须有 progress.json，状态为 complete、complete_with_failures 或 stopped，
且没有活跃 writer。安装和离线检查本身不要求运行 PersonaMem。

## 状态、日志、停止与恢复

    cd ~/dagbt_runs/20261017_webwalker_v4_v2_experiment/dagv2
    bash scripts/run_webwalker.sh status
    tail -f outputs/webwalkerqa_v4_access_v13_full/launcher.log
    bash scripts/run_webwalker.sh stop outputs/webwalkerqa_v4_access_v13_full

启动后用状态和日志确认。停止后等 live_writer、live_scorer 均为 false；
同源码、配置、PersonaMem 路径及输出目录下再次执行：

    bash scripts/run_webwalker.sh full

已终态任务复用；已经开始但未正常发布结果的任务保留失败，不自动重试。
WEBWALKER_OUTPUT 可指定 WebWalker 输出；恢复时保持一致。
stop 的第二参数必须明确传入 WebWalker 输出路径；full 第二参数则是 PersonaMem 输出。
progress.state=complete 表示生成完成；评分另看 live_scorer、日志及 evaluation.json。
单题日志与结果位于 tasks/<题>/<组>/，完整调用和成本明细保留在同一任务目录。

轻量包移除了未使用的模块，因此 source manifest 的文件集合不同于双数据集包。
必须使用本包的新目标与全新输出，不能复用旧双数据集输出继续生成或评分。
"""


def create_bundle(old, kept):
    RELEASE.mkdir(parents=True, exist_ok=True)
    BUNDLE.mkdir(exist_ok=False)
    for relative, expected in kept.items():
        source = SOURCE / 'payload' / relative
        require(source.is_file() and not source.is_symlink() and sha(source) == expected,
                'Revision 2 retained source differs: ' + relative)
        target = BUNDLE / 'payload' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    shutil.copy2(SOURCE / 'install_webwalker.py', BUNDLE / 'install_webwalker.py')
    wheel = BUNDLE / old['pdf_wheel']
    wheel.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE / old['pdf_wheel'], wheel)
    parent_checksum = (SOURCE.parent / (SOURCE.name + '.tar.gz.sha256')).read_text().split()[0]
    manifest = {
        'bundle_name': NAME, 'artifact_variant': 'webwalker_only_derived_from_v2',
        'bundle_revision': 2, 'baseline_commit': BASELINE, 'source_commit': old['source_commit'],
        'baseline_source_sha256': old['baseline_source_sha256'], 'payload_sha256': kept,
        'pdf_wheel': old['pdf_wheel'], 'pdf_wheel_sha256': old['pdf_wheel_sha256'],
        'datasets': {'webwalkerqa': old['datasets']['webwalkerqa']},
        'protocol': 'provided_root_observed_link_traversal_v4_access_v13',
        'access_policy': 'paired_root_unavailable_exclusion_v1',
        'generation_before_scoring': True, 'credentials_in_bundle': False,
        'default_target': TARGET, 'fresh_output_required': True,
        'retained_payload_bytes_equal_source_v2': True, 'generation_source_files': 119,
        'source_bundle': {'name': SOURCE.name, 'bundle_revision': 2,
                          'declared_archive_sha256': parent_checksum,
                          'manifest_sha256': sha(SOURCE / 'bundle_manifest.json')},
        'excluded_source_payload_paths': sorted(EXCLUDED),
    }
    save(BUNDLE / 'bundle_manifest.json', manifest)
    save(BUNDLE / 'validation.json', {
        'state': 'pending_install_offline', 'bundle_name': NAME,
        'artifact_variant': manifest['artifact_variant'], 'bundle_revision': 2,
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Exact revision 2 WebWalker subset; new candidate installation/offline validation pending.',
        'payload_files': 155, 'unchanged_public_python_files': 107,
        'retained_payload_bytes_equal_source_v2': True, 'generation_source_files': 119,
        'source_bundle': manifest['source_bundle'],
        'installation': {'state': 'pending'}, 'offline_webwalker': {'state': 'pending'},
        'new_real_paid_regression_run': False, 'server_full_execution_claimed': False,
        'historical_source_evidence': {'source_bundle_revision': 2,
                                       'webwalker_final_answer_tasks': 2,
                                       'webwalker_budget_exhausted_tasks': 2,
                                       'webwalker_tasks': 4,
                                       'answer_accuracy_reported': False,
                                       'scope': 'Historical source result only, not a new candidate regression.'},
    })
    (BUNDLE / 'README.md').write_text(readme())
    launcher = (SOURCE / 'install_and_run.sh').read_text()
    require(OLD_TARGET[2:] in launcher, 'Original revision 2 launcher target changed')
    launcher = launcher.replace(OLD_TARGET[2:], TARGET[2:]).replace('run_benchmarks.sh', 'run_webwalker.sh')
    require('run_benchmarks.sh' not in launcher and 'run_webwalker.sh full' in launcher,
            'Launcher must start only WebWalker full')
    offline = launcher.replace(
        'DAGBT_PYTHON="$TASK_PYTHON" bash scripts/run_webwalker.sh full\n',
        'echo "Installed and WebWalker offline verification passed; full was not started."\n')
    require('run_webwalker.sh full' not in offline, 'Offline launcher must not start a real run')
    for name, text in (('install_and_run.sh', launcher), ('install_and_offline.sh', offline)):
        path = BUNDLE / name
        path.write_text(text)
        path.chmod(0o755)


def verify_bundle(old, kept):
    manifest = read(BUNDLE / 'bundle_manifest.json')
    require(manifest['payload_sha256'] == kept
            and manifest['baseline_source_sha256'] == old['baseline_source_sha256']
            and set(manifest['datasets']) == {'webwalkerqa'}, 'Candidate manifest differs')
    expected_top = {'bundle_manifest.json', 'install_webwalker.py', 'README.md', 'validation.json',
                    'install_and_run.sh', 'install_and_offline.sh', old['pdf_wheel']}
    expected_files = {'payload/' + path for path in kept} | expected_top
    files = {}
    for path in BUNDLE.rglob('*'):
        require(not path.is_symlink(), 'Candidate contains a symlink')
        if not path.is_file():
            continue
        relative = str(path.relative_to(BUNDLE))
        require(relative in expected_files, 'Unexpected candidate file: ' + relative)
        require(not any(piece in ('credentials.local.json', '__pycache__', '.git', 'outputs')
                        for piece in path.parts), 'Private/cache/output candidate member')
        files[relative] = sha(path)
        if path.suffix == '.py':
            text = path.read_text()
            ast.parse(text, filename=str(path))
            compile(text, str(path), 'exec')
        if path.suffix == '.sh':
            subprocess.run(['bash', '-n', str(path)], check=True)
    require(set(files) == expected_files and len(files) == 162, 'Candidate member set differs')
    require(all(files['payload/' + path] == expected for path, expected in kept.items()),
            'A retained payload byte differs from revision 2')
    require(files['install_webwalker.py'] == sha(SOURCE / 'install_webwalker.py')
            and files[old['pdf_wheel']] == old['pdf_wheel_sha256'],
            'Original installer/PDF wheel differs')
    return files


def package(files):
    with tempfile.TemporaryDirectory(prefix='.candidate-', dir=RELEASE) as temporary_name:
        temporary = Path(temporary_name)
        candidate = temporary / ARCHIVE.name
        with tarfile.open(candidate, 'w:gz', compresslevel=3) as archive:
            archive.add(BUNDLE, arcname=NAME)
        seen = {}
        with tarfile.open(candidate, 'r|gz') as archive:
            for member in archive:
                path = PurePosixPath(member.name)
                require(not path.is_absolute() and '..' not in path.parts and path.parts[0] == NAME,
                        'Unsafe archive path')
                if member.isdir():
                    continue
                require(member.isfile() and not member.islnk() and not member.issym(),
                        'Archive links or special members are forbidden')
                relative = str(path.relative_to(NAME))
                require(relative not in seen and relative in files, 'Unexpected/duplicate archive member')
                digest = hashlib.sha256()
                with archive.extractfile(member) as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(block)
                seen[relative] = digest.hexdigest()
        require(seen == files, 'Streamed candidate archive differs from verified bundle files')
        digest = sha(candidate)
        checksum = temporary / (ARCHIVE.name + '.sha256')
        checksum.write_text(digest + '  ' + ARCHIVE.name + '\n')
        checker = (['sha256sum', '-c', checksum.name] if shutil.which('sha256sum') else
                   ['shasum', '-a', '256', '-c', checksum.name])
        subprocess.run(checker, cwd=temporary, check=True)
        os.replace(candidate, ARCHIVE)
        os.replace(checksum, RELEASE / checksum.name)
    return digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repack', action='store_true',
                        help='Preserve externally updated README/validation and reverify/repack the candidate')
    args = parser.parse_args()
    old, kept = source_manifest()
    if not args.repack:
        create_bundle(old, kept)
    files = verify_bundle(old, kept)
    digest = package(files)
    report = {'state': 'candidate_built' if not args.repack else 'repacked',
              'bundle': str(BUNDLE), 'archive': str(ARCHIVE), 'sha256': digest,
              'checksum_file': str(ARCHIVE) + '.sha256', 'bytes': ARCHIVE.stat().st_size,
              'payload_files': len(kept), 'regular_archive_files': len(files),
              'unchanged_public_python_files': 107, 'generation_source_files': 119,
              'retained_payload_bytes_equal_source_v2': True,
              'original_installer_and_pdf_wheel_bytes_preserved': True,
              'validation_state': read(BUNDLE / 'validation.json')['state'],
              'new_real_paid_regression_run': False}
    save(RELEASE / 'candidate_build.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
