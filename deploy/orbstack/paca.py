#!/usr/bin/env python3
"""Local Paca lifecycle and encrypted NAS backups. Python standard library only."""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import plistlib
import secrets
import signal
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid

SOURCE = Path(__file__).resolve().parent
# Keep launchd code and private runtime files outside macOS-protected Documents.
# The repository remains the editable/distributable source.
BASE = Path.home() / 'Library' / 'Application Support' / 'Paca-OrbStack'
KEYS = BASE / 'secrets'
BACKUPS = BASE / 'backups'
NAS_ROOT = Path('/Volumes/Personal/Backups')
DOCKER = shutil.which('docker') or '/usr/local/bin/docker'
TOOLS = 'paca-orbstack-tools:1'
LABEL = 'com.tschleuss.paca-orbstack.backup'
RUNTIME = ['network-guard', 'postgres', 'valkey', 'rustfs', 'api', 'web', 'realtime', 'gateway']
WRITERS = ['gateway', 'web', 'realtime', 'api', 'rustfs', 'valkey']


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def dc(*args, **kwargs):
    return run([DOCKER, '--context', 'orbstack', 'compose', '--project-directory', BASE,
                '--env-file', BASE / '.env', '-f', BASE / 'compose.yaml', *args], **kwargs)


def helper(*args, **kwargs):
    return dc('run', '--rm', '--no-deps', 'backup', *args, **kwargs)


def private_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def sync_runtime_source():
    if SOURCE == BASE:
        return
    for name in ['.env.example', '.dockerignore', 'compose.yaml', 'Caddyfile', 'Dockerfile', 'paca.py', 'README.md']:
        shutil.copyfile(SOURCE / name, BASE / name)
    shutil.copytree(SOURCE / 'scripts', BASE / 'scripts', dirs_exist_ok=True)
    if (SOURCE / 'VALIDATION.md').exists():
        shutil.copyfile(SOURCE / 'VALIDATION.md', BASE / 'VALIDATION.md')


def mount_for(path):
    """Reject a local fallback directory beneath /Volumes when NAS is absent."""
    lines = run(['/sbin/mount'], capture_output=True, text=True).stdout.splitlines()
    matches = []
    for line in lines:
        if ' on ' not in line or ' (' not in line:
            continue
        source, tail = line.split(' on ', 1)
        mount, options = tail.rsplit(' (', 1)
        if path.is_relative_to(Path(mount)):
            matches.append({'source': source, 'mount': mount, 'type': options.split(',')[0].rstrip(')')})
    if not matches:
        raise RuntimeError('NAS path has no mounted filesystem')
    result = max(matches, key=lambda x: len(x['mount']))
    if result['type'] not in ('smbfs', 'nfs'):
        raise RuntimeError('NAS share is not mounted as SMB/NFS; refusing local fallback under /Volumes')
    return result


def configure_nas():
    mount = mount_for(NAS_ROOT)
    if not NAS_ROOT.is_dir():
        raise RuntimeError(f'Existing NAS backup root is missing: {NAS_ROOT}')
    instance = (KEYS / 'instance-id').read_text().strip()
    destination = NAS_ROOT / 'Paca-OrbStack' / instance
    destination.mkdir(parents=True, exist_ok=True)
    marker = destination / '.paca-backup-target'
    if marker.exists() and marker.read_text().strip() != instance:
        raise RuntimeError('NAS destination identity does not match')
    marker.write_text(instance + '\n')
    private_json(KEYS / 'backup-target.json', {'mount': mount, 'destination': str(destination), 'instance': instance})
    print(f'NAS target verified: {destination}')


def nas_target():
    record = json.loads((KEYS / 'backup-target.json').read_text())
    if mount_for(NAS_ROOT) != record['mount']:
        raise RuntimeError('Mounted NAS share differs from the configured backup target')
    destination = Path(record['destination'])
    if (destination / '.paca-backup-target').read_text().strip() != record['instance']:
        raise RuntimeError('NAS backup marker missing or mismatched')
    return destination


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def upload_pending():
    destination = nas_target()
    for archive in sorted(BACKUPS.glob('paca-*.tar.age')):
        # Check the mount immediately before each copy; never mkdir a fallback.
        if nas_target() != destination:
            raise RuntimeError('NAS target changed during upload')
        checksum = digest(archive)
        target = destination / archive.name
        if target.exists():
            if digest(target) != checksum:
                raise RuntimeError(f'Existing NAS archive has a different checksum: {target.name}')
        else:
            partial = target.with_suffix(target.suffix + '.partial')
            try:
                shutil.copyfile(archive, partial)
                if digest(partial) != checksum:
                    raise RuntimeError('NAS copy checksum verification failed')
                partial.replace(target)
            finally:
                if partial.exists():
                    partial.unlink()
        # Marker is written only after a verified, atomically renamed archive.
        (destination / (archive.name + '.sha256')).write_text(f'{checksum}  {archive.name}\n')
    # Only app-owned local copies are pruned, after every NAS copy verified.
    # NAS recovery points are never deleted here.
    for old in sorted(BACKUPS.glob('paca-*.tar.age'))[:-4]:
        old.unlink()
        old.with_suffix(old.suffix + '.sha256').unlink(missing_ok=True)
    return str(destination)


def init():
    sync_runtime_source()
    for path in [KEYS, BACKUPS, BASE / 'logs']:
        path.mkdir(exist_ok=True, mode=0o700)
    env = BASE / '.env'
    if not env.exists():
        text = (BASE / '.env.example').read_text()
        for name in ['POSTGRES_PASSWORD', 'ADMIN_PASSWORD', 'JWT_SECRET', 'ENCRYPTION_KEY',
                     'INTERNAL_API_KEY', 'STORAGE_ACCESS_KEY_ID', 'STORAGE_SECRET_ACCESS_KEY']:
            text = text.replace(name + '=GENERATE', name + '=' + secrets.token_hex(32))
        env.write_text(text)
        env.chmod(0o600)
    if not (KEYS / 'instance-id').exists():
        (KEYS / 'instance-id').write_text(str(uuid.uuid4()) + '\n')
    dc('build', 'network-guard')
    if not (KEYS / 'backup.agekey').exists():
        helper('age-keygen', '-o', '/keys/backup.agekey', capture_output=True, text=True)
    public = helper('age-keygen', '-y', '/keys/backup.agekey', capture_output=True, text=True).stdout
    (KEYS / 'backup.recipient').write_text(public)
    # Volumes are local Linux filesystems. Root-owned fresh RustFS volumes need initialization.
    helper('sh', '-ec', 'chown -R 10001:10001 /snapshot/rustfs', capture_output=True)
    if not (KEYS / 'backup-target.json').exists():
        configure_nas()
    print('Initialized. Keep secrets/backup.agekey in a separate password manager/recovery location.')


def states():
    result = dc('ps', '--format', 'json', capture_output=True, text=True).stdout.strip()
    if not result:
        return {}
    rows = json.loads(result) if result.startswith('[') else [json.loads(line) for line in result.splitlines()]
    return {row['Service']: row for row in rows}


def backup():
    status = {'attempted_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    current = states()
    if not all(current.get(service, {}).get('State') == 'running' for service in RUNTIME):
        # Still deliver encrypted archives from an earlier NAS outage when possible.
        try:
            status['nas_target'] = upload_pending()
        except (OSError, RuntimeError) as exc:
            status['nas_error'] = str(exc)
        status['result'] = 'skipped: app is not fully running; no services were started'
        private_json(BASE / 'backup-status.json', status)
        print(status['result'])
        return
    work = Path(tempfile.mkdtemp(prefix='.working-', dir=BACKUPS))
    paused = False
    try:
        paused = True
        dc('stop', *WRITERS, stdout=subprocess.DEVNULL)
        with (work / 'database.dump').open('wb') as dump:
            dc('exec', '-T', 'postgres', 'pg_dump', '-U', 'paca', '-d', 'paca', '-Fc', stdout=dump)
        with (work / 'database.dump').open('rb') as dump:
            dc('exec', '-T', 'postgres', 'pg_restore', '--list', stdin=dump, stdout=subprocess.DEVNULL)
        dc('stop', 'postgres', stdout=subprocess.DEVNULL)
        helper('tar', '-czf', '/work/' + work.name + '/state.tar.gz', '-C', '/snapshot', '.', stdout=subprocess.DEVNULL)
        helper('tar', '-tzf', '/work/' + work.name + '/state.tar.gz', stdout=subprocess.DEVNULL)
        # Restart the existing containers, preserving their guarded network namespace.
        dc('start', '--wait', '--wait-timeout', '180', 'postgres', 'valkey', 'rustfs', 'api', 'web', 'realtime', 'gateway', stdout=subprocess.DEVNULL)
        paused = False
        metadata = work / 'configuration'
        metadata.mkdir()
        for name in ['.env', 'compose.yaml', 'Caddyfile', 'Dockerfile', 'paca.py', 'README.md']:
            shutil.copyfile(BASE / name, metadata / name)
        if (BASE / 'VALIDATION.md').exists():
            shutil.copyfile(BASE / 'VALIDATION.md', metadata / 'VALIDATION.md')
        shutil.copytree(BASE / 'scripts', metadata / 'scripts')
        shutil.copyfile(KEYS / 'instance-id', metadata / 'instance-id')
        private_json(metadata / 'backup-info.json', {'time': status['attempted_at'], 'image': TOOLS,
                     'docker_context': 'orbstack', 'recovery_key': 'NOT included; use separately saved backup.agekey'})
        bundle = work / 'bundle.tar'
        with tarfile.open(bundle, 'w') as archive:
            for name in ['database.dump', 'state.tar.gz', 'configuration']:
                archive.add(work / name, arcname=name)
        stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        final = BACKUPS / ('paca-' + stamp + '.tar.age')
        recipient = (KEYS / 'backup.recipient').read_text().strip()
        helper('age', '-r', recipient, '-o', '/work/' + final.name + '.partial',
               '/work/' + work.name + '/bundle.tar', stdout=subprocess.DEVNULL)
        partial = final.with_suffix(final.suffix + '.partial')
        partial.chmod(0o600)
        partial.replace(final)
        checksum = digest(final)
        final.with_suffix(final.suffix + '.sha256').write_text(f'{checksum}  {final.name}\n')
        status.update({'result': 'local backup complete', 'archive': str(final), 'sha256': checksum})
        # Keep last successful recovery details even if a later job skips/fails.
        private_json(BACKUPS / 'last-success.json', status)
        try:
            status['nas_target'] = upload_pending()
            status['result'] = 'local and NAS backup complete'
            private_json(BACKUPS / 'last-success.json', status)
        except (OSError, RuntimeError) as exc:
            status['nas_error'] = str(exc)
            status['result'] = 'local backup complete; NAS copy pending'
            raise RuntimeError(status['result'] + ': ' + str(exc)) from exc
        print(f"Encrypted backup verified on NAS: {final.name}")
    except Exception as exc:
        status['error'] = str(exc)
        raise
    finally:
        try:
            if paused:
                dc('start', 'postgres', 'valkey', 'rustfs', 'api', 'web', 'realtime', 'gateway', stdout=subprocess.DEVNULL)
        finally:
            shutil.rmtree(work)
            private_json(BASE / 'backup-status.json', status)


def verify_network():
    current = states()
    guard = current.get('network-guard', {}).get('ID')
    if not guard:
        raise RuntimeError('Start the app first')
    # The rules apply to every app process because every app shares this namespace.
    probes = '''set -eu
curl -fsS --max-time 5 http://127.0.0.1:8080/api/healthz >/dev/null
for url in https://1.1.1.1 http://8.8.8.8:80 'https://[2606:4700:4700::1111]'; do
  if curl --noproxy '*' -k -sS --max-time 2 "$url" >/dev/null 2>&1; then
    echo "FAIL: outbound connection succeeded"; exit 1
  fi
done
if dig +time=1 +tries=1 @8.8.8.8 example.com >/dev/null 2>&1; then exit 1; fi
if dig +time=1 +tries=1 @127.0.0.11 example.com >/dev/null 2>&1; then exit 1; fi
echo 'PASS: local API works; public IPv4/IPv6, external DNS and embedded DNS blocked'
'''
    run([DOCKER, '--context', 'orbstack', 'run', '--rm', '--network', 'container:' + guard,
         '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--entrypoint', 'sh', TOOLS, '-ec', probes])
    for service in RUNTIME[1:]:
        cid = current[service]['ID']
        mode = run([DOCKER, '--context', 'orbstack', 'inspect', '--format', '{{.HostConfig.NetworkMode}}', cid], capture_output=True, text=True).stdout.strip()
        if not mode.startswith('container:'):
            raise RuntimeError(service + ' is not sharing the guarded namespace')
        netns = dc('exec', '-T', service, 'readlink', '/proc/self/ns/net', capture_output=True, text=True).stdout.strip()
        guardns = dc('exec', '-T', 'network-guard', 'readlink', '/proc/self/ns/net', capture_output=True, text=True).stdout.strip()
        if netns != guardns:
            raise RuntimeError(service + ' has a different network namespace')
    proc = dc('exec', '-T', 'network-guard', 'cat', '/proc/1/status', capture_output=True, text=True).stdout
    caps = dict(line.split(':', 1) for line in proc.splitlines() if ':' in line)
    if any(int(caps[name].strip(), 16) != 0 for name in ['CapPrm', 'CapEff', 'CapBnd']):
        raise RuntimeError('Firewall keeper retained capabilities after initialization')
    print('PASS: every app service shares the verified firewall namespace')


def install_schedule():
    logs = BASE / 'logs'
    logs.mkdir(exist_ok=True, mode=0o700)
    agent = Path.home() / 'Library' / 'LaunchAgents' / (LABEL + '.plist')
    agent.parent.mkdir(parents=True, exist_ok=True)
    interpreter = shutil.which('python3') or sys.executable
    config = {'Label': LABEL, 'ProgramArguments': [interpreter, str(BASE / 'paca.py'), 'backup'],
              'WorkingDirectory': str(BASE), 'StartInterval': 21600, 'StartOnMount': True,
              'RunAtLoad': False, 'ExitTimeOut': 180, 'StandardOutPath': str(logs / 'backup.log'),
              'StandardErrorPath': str(logs / 'backup-error.log'),
              'EnvironmentVariables': {'PATH': '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'}}
    if agent.exists():
        subprocess.run(['launchctl', 'bootout', 'gui/' + str(os.getuid()), str(agent)], capture_output=True)
    agent.write_bytes(plistlib.dumps(config))
    run(['launchctl', 'bootstrap', 'gui/' + str(os.getuid()), agent])
    print('Installed user LaunchAgent: backup every 6 hours while awake, plus on mounts; no automatic app startup.')


def main():
    os.umask(0o077)
    def interrupted(signum, frame):
        raise RuntimeError('Backup/lifecycle operation interrupted by signal ' + str(signum))
    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'start', 'stop', 'status', 'backup', 'configure-backup',
                                           'sync-backups', 'verify-network', 'install-schedule'])
    args = parser.parse_args()
    BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (BASE / '.operation-lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another Paca lifecycle/backup operation is running') from None
        if args.command == 'init':
            init()
        elif args.command == 'start':
            if not (BASE / '.env').exists():
                init()
            dc('up', '-d', '--wait', '--wait-timeout', '180')
            dc('cp', 'gateway:/data/caddy/pki/authorities/local/root.crt', KEYS / 'root.crt')
            print('Paca is running at https://localhost:8443 (see secrets/root.crt for TLS trust).')
        elif args.command == 'stop':
            dc('down')
        elif args.command == 'status':
            dc('ps')
            if (BASE / 'backup-status.json').exists():
                print((BASE / 'backup-status.json').read_text())
        elif args.command == 'backup':
            backup()
        elif args.command == 'configure-backup':
            configure_nas()
        elif args.command == 'sync-backups':
            print('Verified pending archives on NAS:', upload_pending())
        elif args.command == 'verify-network':
            verify_network()
        elif args.command == 'install-schedule':
            install_schedule()


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        sys.exit('Paca: ' + str(exc))
