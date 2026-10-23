#!/usr/bin/env python3
"""Reproduce and prevent BusyBox HTTPS-probe zombies in disposable containers.

Uses the configured/pinned gateway image and health command, without credentials,
production mounts, host ports or changes to the running Paca stack. Requires Docker.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import tempfile
import time
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', default='orbstack')
    parser.add_argument('--probes', type=int, default=300)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.probes < 100:
        parser.error('--probes must be >=100 to exceed the 64-task fixture limit')
    docker = ['docker', '--context', args.context]

    def run(*command, check=True):
        result = subprocess.run([*docker, *command], text=True, capture_output=True, timeout=30)
        if check and result.returncode:
            raise RuntimeError(f'Docker {command[0]} failed: {result.stderr[:500]}')
        return result

    compose = Path(__file__).with_name('compose.yaml')
    # Do not load deployment credentials or interpolate the host environment.
    model = json.loads(run('compose', '--env-file', '/dev/null', '-f', str(compose),
                           'config', '--no-interpolate', '--format', 'json').stdout)
    gateway = model['services']['gateway']
    image = gateway['image']
    probe = gateway['healthcheck']['test']
    if probe[0] != 'CMD' or not image.startswith('caddy:') or '@sha256:' not in image:
        raise RuntimeError('Review changed gateway image/healthcheck before updating this fixture')
    run('image', 'inspect', '--format', '{{.Id}}', image)  # --pull never below.
    prefix = 'paca-health-repro-' + uuid.uuid4().hex[:10]
    created = []
    records = []

    def snapshot(name):
        # docker top hides dead processes; an independent cgroup can inspect their
        # PID namespace even when the target's process limit is already exhausted.
        data = run('run', '--rm', '--pull', 'never', '--network', 'none',
                   '--pid', 'container:' + name, '--read-only', '--cap-drop', 'ALL',
                   '--cap-add', 'NET_BIND_SERVICE', '--security-opt', 'no-new-privileges:true',
                   '--entrypoint', '/bin/ps', image, '-eo', 'pid,ppid,stat,comm').stdout
        rows = [line.split() for line in data.splitlines()[1:]]
        counts = Counter((row[2], row[3]) for row in rows if len(row) >= 4)
        zombies = sum(count for (state, _), count in counts.items() if state.startswith('Z'))
        pid1 = next((row[3] for row in rows if row[0] == '1'), None)
        return {'zombies': zombies, 'pid1': pid1,
                'process_counts': {state + ':' + command: count for (state, command), count in counts.items()}}

    try:
        with tempfile.TemporaryDirectory(prefix='paca-health-config-') as temporary:
            config = Path(temporary) / 'Caddyfile'
            config.write_text('''{
    admin off
    auto_https disable_redirects
    skip_install_trust
}
https://localhost {
    tls internal
    respond /api/healthz 200
}
''')
            # Bridge control proves blocked external access is not required for the
            # defect. All requests/certificates are local, including that control.
            for label, network, init, count in [
                ('offline-no-init', 'none', False, 80),
                ('bridge-no-init', 'bridge', False, 80),
                ('offline-configured', 'none', bool(gateway.get('init')), args.probes),
            ]:
                name = prefix + '-' + label
                command = ['run', '-d', '--name', name, '--pull', 'never', '--network', network,
                           '--read-only', '--cap-drop', 'ALL', '--cap-add', 'NET_BIND_SERVICE',
                           '--security-opt', 'no-new-privileges:true', '--pids-limit', '64',
                           '--memory', '128m', '--cpus', '0.5', '--tmpfs', '/data',
                           '--tmpfs', '/config', '--tmpfs', '/tmp',
                           '--mount', 'type=bind,source=' + str(config) + ',target=/etc/caddy/Caddyfile,readonly']
                if init:
                    command.append('--init')
                command += [image, 'caddy', 'run', '--config', '/etc/caddy/Caddyfile', '--adapter', 'caddyfile']
                run(*command)
                created.append(name)
                for _ in range(30):
                    ready = run('exec', name, *probe[1:], check=False)
                    if ready.returncode == 0:
                        break
                    time.sleep(0.1)
                else:
                    raise RuntimeError('Fixture did not become ready: ' + label)
                baseline = snapshot(name)
                successful, failure = 0, None
                started = time.monotonic()
                for index in range(count):
                    result = run('exec', name, *probe[1:], check=False)
                    if result.returncode:
                        failure = {'probe': index + 1, 'exit_code': result.returncode,
                                   'error': (result.stderr + result.stdout).strip()[:400]}
                        break
                    successful += 1
                after = snapshot(name)
                record = {'case': label, 'network': network, 'init': init,
                          'successful_probes': successful, 'failure': failure,
                          'baseline': baseline, 'after': after,
                          'seconds': round(time.monotonic() - started, 2)}
                records.append(record)
                print(json.dumps(record), flush=True)
            for control in records[:2]:
                if not control['failure'] or control['after']['zombies'] < 40:
                    raise RuntimeError('Negative control did not reproduce TLS-helper accumulation')
            fixed = records[-1]
            if not fixed['init'] or fixed['failure'] or fixed['after']['zombies'] != 0:
                raise RuntimeError('Configured gateway leaked TLS-helper children or exhausted its task limit')
            report = {'gateway_image': image, 'healthcheck': probe, 'fixture_pids_limit': 64,
                      'cases': records, 'passed': True,
                      'limits': 'Local synthetic TLS responder; no Paca API/data or host ports. Live-stack verification is separate.'}
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(report, indent=2) + '\n')
            print('PASS: controls reproduced the defect; configured offline gateway stayed healthy.', flush=True)
    finally:
        for name in reversed(created):
            run('rm', '-f', name, check=False)


if __name__ == '__main__':
    main()
