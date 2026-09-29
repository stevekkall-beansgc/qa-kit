#!/usr/bin/env python3
"""Bounded shared validation planner/executor. Trust and runner isolation are adapter-owned.

No enrollment, installation, network access, or commands occur on import. JSON inputs
are pinned by the invoking adapter; this executor is not a process sandbox.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

CONTRACT_VERSION = '1.0'
HERE = Path(__file__).resolve().parent.parent
EFFECTS = {'repo-write', 'scratch-write', 'loopback', 'dependency-network', 'public-network'}
SHA = re.compile(r'[0-9a-f]{40}\Z')
DIGEST = re.compile(r'[0-9a-f]{64}\Z')
NAME = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_.-]*\Z')


class Invalid(ValueError):
    """An unavailable or invalid execution prerequisite."""


class Cancelled(Exception):
    """Adapter cancellation; child groups must still be stopped."""


def require(ok, message):
    if not ok:
        raise Invalid(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_digest(value):
    return digest(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


def fields(value, required, optional=()):
    require(isinstance(value, dict), 'expected JSON object')
    require(set(required) <= value.keys() and value.keys() <= set(required) | set(optional),
            'missing or unknown fields: ' + ', '.join(sorted(set(required) ^ value.keys())))


def strings(value, label, nonempty=False):
    require(isinstance(value, list) and all(isinstance(v, str) and v and '\x00' not in v for v in value),
            label + ' must be a string list')
    require(len(value) == len(set(value)), label + ' contains duplicates')
    require(bool(value) or not nonempty, label + ' is empty')
    return value


def read_json(path, schema):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    data = Path(path).read_bytes()
    value = json.loads(data, object_pairs_hook=unique)
    require(isinstance(value, dict) and value.get('schema') == schema, 'unsupported schema: ' + schema)
    return value, digest(data)


def confined(root, name, *, exists=True):
    require(isinstance(name, str) and name and '\x00' not in name, 'invalid repository path')
    rel = Path(name)
    require(not rel.is_absolute() and '..' not in rel.parts and '.git' not in rel.parts,
            'path must stay inside repository')
    current = root
    for part in rel.parts:
        current = current / part
        require(not current.is_symlink(), 'symlink path is not supported')
    require(current.resolve().is_relative_to(root.resolve()), 'path escaped repository')
    require(not exists or current.exists(), 'required path missing: ' + name)
    return current


def git(root, *args):
    env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    env.update({'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':os.devnull})
    p = subprocess.run(['git', '-C', str(root), *args], capture_output=True, timeout=15,
                       env=env)
    require(p.returncode == 0, 'cannot establish git identity')
    return p.stdout


def identity(root):
    require(Path(root).is_dir(), 'checkout missing')
    require(Path(git(root, 'rev-parse', '--show-toplevel').decode().strip()).resolve() == Path(root).resolve(),
            'expected checkout root')
    head = git(root, 'rev-parse', 'HEAD').decode().strip()
    dirty = bool(git(root, 'status', '--porcelain=v1', '--untracked-files=all'))
    flags=git(root,'ls-files','-v','-z').split(b'\0')
    require(all(not row or (row[:1].isupper() and row[:1] != b'S') for row in flags),
            'hidden index flags are unsupported')
    # Establish physical bytes/modes against HEAD blobs, not just index status.
    tree = hashlib.sha256()
    matches=True
    for entry in sorted(git(root, 'ls-tree', '-rz', 'HEAD').split(b'\0')):
        if not entry:
            continue
        metadata,raw=entry.split(b'\t',1)
        mode,kind,blob=metadata.split()
        require(kind==b'blob' and mode in (b'100644',b'100755'), 'symlink/submodule unsupported')
        path = confined(Path(root), os.fsdecode(raw))
        require(not path.is_symlink(), 'tracked symlink is unsupported')
        require(path.is_file(), 'tracked path missing or submodule unsupported')
        data=path.read_bytes()
        actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest().encode()
        executable=bool(path.stat().st_mode & 0o111)
        matches=matches and actual==blob and executable==(mode==b'100755')
        tree.update(raw+b'\0'+mode+b'\0'+hashlib.sha256(data).digest())
    return {'head':head, 'dirty':dirty or not matches, 'tracked_sha256':tree.hexdigest(), 'matches_head':matches}


def exact(root, expected):
    require(isinstance(expected, str) and SHA.fullmatch(expected), 'expected immutable commit')
    value = identity(root)
    require(value['head'] == expected and value['dirty'] is False, 'checkout is dirty or differs from expected commit')
    return value


def runtimes(spec):
    require(isinstance(spec, dict) and spec, 'runtime requirements missing')
    require('npm' not in spec or 'node' in spec, 'npm requires an explicit Node runtime')
    observed = {}
    commands = {'python':sys.executable, 'node':'node', 'bash':'bash', 'sh':'sh', 'npm':'npm'}
    for name, version in spec.items():
        require(name in commands, 'unsupported runtime: ' + name)
        require(isinstance(version, str) and re.fullmatch(r'\d+(\.\d+){0,2}', version), 'invalid runtime version')
        binary = shutil.which(commands[name])
        require(binary is not None, 'runtime unavailable: ' + name)
        binary = str(Path(binary).resolve())
        if name == 'sh':
            # POSIX shell implementations lack a common version API. Use bash explicitly.
            raise Invalid('sh version cannot be established; declare bash')
        probe = [binary, '-I', '-c', 'import platform;print(platform.python_version())'] if name == 'python' else [binary, '--version']
        p = subprocess.run(probe, capture_output=True, text=True, timeout=15,
                           env={'PATH':os.environ.get('PATH', os.defpath), 'LANG':'C', 'LC_ALL':'C'})
        match = re.search(r'(\d+\.\d+(?:\.\d+)?)', p.stdout)
        require(p.returncode == 0 and match is not None, 'cannot observe runtime: ' + name)
        actual = match.group(1)
        require(actual == version or actual.startswith(version + '.'), 'runtime version mismatch: ' + name)
        observed[name] = {'version':actual, 'executable':binary, 'sha256':digest(Path(binary).read_bytes())}
    return observed


def plan(contract, policy, selection, variant):
    fields(contract, ('schema', 'variants', 'tasks', 'selections'))
    fields(policy, ('contract', 'contract_sha256', 'selections', 'github_repository', 'required_selections'))
    require(isinstance(policy['github_repository'], str) and re.fullmatch(r'[\w.-]+/[\w.-]+', policy['github_repository']),
            'GitHub repository identity missing')
    require(isinstance(policy['required_selections'], dict) and set(policy['required_selections']) <= {'ci','release'},
            'invalid required context selections')
    require(all(isinstance(v,str) and v in policy['selections'] for v in policy['required_selections'].values()),
            'unknown required context selection')
    require(isinstance(contract['variants'], dict) and contract['variants'], 'variants missing')
    require(isinstance(contract['tasks'], dict) and contract['tasks'], 'tasks missing')
    require(isinstance(contract['selections'], dict) and isinstance(policy['selections'], dict), 'selections missing')
    require(contract['selections'] == policy['selections'], 'contract differs from centrally required selections')
    tasks, variants = contract['tasks'], contract['variants']
    for name, spec in variants.items():
        require(NAME.fullmatch(name), 'invalid variant identifier')
        fields(spec, ('os', 'arch', 'runtimes'))
        require(spec['os'] in ('linux', 'darwin', 'windows'), 'unsupported platform')
        require(isinstance(spec['arch'], str) and spec['arch'], 'architecture missing')
        require(isinstance(spec['runtimes'], dict) and spec['runtimes'], 'runtime requirements missing')
    for name, task in tasks.items():
        require(NAME.fullmatch(name), 'invalid task identifier')
        fields(task, ('argv', 'cwd', 'after', 'variants', 'env', 'effects', 'fixtures', 'timeout_seconds'))
        require(isinstance(task['argv'], list) and task['argv'] and isinstance(task['argv'][0],str), 'invalid argv')
        for argument in task['argv']:
            require((isinstance(argument,str) and argument and '\x00' not in argument) or
                    (isinstance(argument,dict) and set(argument)=={'qa_path'} and isinstance(argument['qa_path'],str)),
                    'invalid argv argument')
        for field in ('after', 'variants', 'effects', 'fixtures'):
            strings(task[field], field, nonempty=field == 'variants')
        require(set(task['after']) <= tasks.keys(), 'unknown prerequisite')
        require(set(task['variants']) <= variants.keys(), 'unknown task variant')
        require(set(task['effects']) <= EFFECTS, 'unsupported effect')
        require(all(NAME.fullmatch(v) for v in task['fixtures']), 'invalid fixture name')
        require(isinstance(task['env'], dict), 'env must be an object')
        for key, value in task['env'].items():
            require(isinstance(key,str) and isinstance(value,dict) and len(value)==1 and
                    set(value) <= {'literal','repo_path','fixture_path'}, 'unknown environment type')
        require(isinstance(task['timeout_seconds'], (int, float)) and not isinstance(task['timeout_seconds'], bool)
                and 0 < task['timeout_seconds'] <= 14400, 'invalid timeout')
    for name, required in contract['selections'].items():
        require(NAME.fullmatch(name), 'invalid selection identifier')
        for cell in strings(required, 'required selection', nonempty=True):
            require(cell.count('@') == 1, 'invalid task@variant')
            task, cell_variant = cell.split('@')
            require(task in tasks and cell_variant in variants and cell_variant in tasks[task]['variants'], 'unknown required task/variant')
    require(selection in contract['selections'], 'unknown selection')
    require(variant in variants, 'unknown variant')
    required = contract['selections'][selection]
    selected = [cell for cell in required if cell.split('@')[1] == variant]
    require(selected, 'variant has no required cells in selection')
    ordered, visiting = [], set()
    def visit(name):
        require(name not in visiting, 'cyclic prerequisites')
        require(variant in tasks[name]['variants'], 'prerequisite variant unavailable')
        if name in ordered:
            return
        visiting.add(name)
        for prerequisite in tasks[name]['after']:
            visit(prerequisite)
        visiting.remove(name)
        ordered.append(name)
    # Validate every required graph, including unselected cells, before execution.
    for target_variant in variants:
        original_variant = variant
        variant = target_variant
        for cell in required:
            task, cell_variant = cell.split('@')
            if cell_variant == target_variant:
                visit(task)
        ordered.clear()
        variant = original_variant
    for cell in selected:
        visit(cell.split('@')[0])
    return {'selection':selection, 'variant':variant, 'required':required, 'selected':selected,
            'remaining_required':[cell for cell in required if cell not in selected],
            'tasks':[{'task':name, **tasks[name]} for name in ordered], 'environment':variants[variant]}


def environment(root, spec, fixture_paths):
    result = {}
    for key, value in spec.items():
        require(re.fullmatch(r'[A-Z_][A-Z0-9_]*', key) and key not in ('PATH','HOME','PYTHONHOME','BASH_ENV','ENV','NODE_OPTIONS')
                and not key.startswith(('LD_', 'DYLD_', 'GIT_')), 'unsafe environment key')
        require(isinstance(value, dict) and len(value) == 1, 'environment values must have one explicit type')
        if 'literal' in value:
            require(key != 'PYTHONPATH' and isinstance(value['literal'], str) and '\x00' not in value['literal'], 'invalid literal environment value')
            result[key] = value['literal']
        elif 'repo_path' in value:
            result[key] = str(confined(root, value['repo_path']))
        elif 'fixture_path' in value:
            fields(value['fixture_path'], ('name','path'))
            name = value['fixture_path']['name']
            require(name in fixture_paths, 'unknown fixture environment reference')
            result[key] = str(confined(fixture_paths[name], value['fixture_path']['path']))
        else:
            raise Invalid('unknown environment type')
    return result


def execute(task, root, observed, env):
    binary = task['argv'][0]
    aliases = {'python':'python', 'python3':'python', 'node':'node', 'bash':'bash', 'npm':'npm'}
    name = aliases.get(binary)
    if name is None:
        name = next((n for n,v in observed.items() if str(Path(binary).resolve()) == v['executable']), None)
    require(name in observed, 'task executable lacks an observed runtime requirement')
    argv = [observed[name]['executable'], *task['argv'][1:]]
    started = time.monotonic()
    timed_out = False
    cancelled = False
    # Temporary files bound parent memory even if a child produces a large log.
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        process = subprocess.Popen(argv, cwd=confined(root, task['cwd']), env=env,
                                   stdout=out, stderr=err, start_new_session=True)
        def cancel(signum, frame):
            raise Cancelled()
        old_handlers={s:signal.getsignal(s) for s in (signal.SIGTERM,signal.SIGINT)}
        for s in old_handlers: signal.signal(s,cancel)
        try:
            process.wait(timeout=task['timeout_seconds'])
        except subprocess.TimeoutExpired:
            timed_out = True
        except Cancelled:
            cancelled = True
        finally:
            # Reap/stop surviving descendants as well as a timed-out parent.
            if os.name == 'posix':
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif process.poll() is None:
                process.kill()
            process.wait()
            for s, handler in old_handlers.items(): signal.signal(s,handler)
        hashes = {}
        for key, stream in (('stdout_sha256',out), ('stderr_sha256',err)):
            stream.seek(0); h=hashlib.sha256()
            for chunk in iter(lambda:stream.read(65536), b''): h.update(chunk)
            hashes[key]=h.hexdigest()
    return {'task':task['task'], 'status':'pass' if process.returncode == 0 and not timed_out and not cancelled else 'fail',
            'exit_code':process.returncode, 'timed_out':timed_out,
            'cancelled':cancelled,
            'seconds':round(time.monotonic()-started, 3), **hashes}


def run_validation(*, root, repo, registry_path, bundle_path, selection, variant, expected_head,
                   context, authorization_path, fixtures=None, adapter_root=None, qa_root=HERE,
                   expected_bundle=None):
    result = {'schema':'qa-kit.validation-result/v1', 'contract_version':CONTRACT_VERSION,
              'status':'blocked', 'repo':repo, 'selection':selection, 'variant':variant, 'context':context,
              'when':datetime.now(timezone.utc).isoformat(), 'tasks':[], 'selection_complete':False,
              'errors':[], 'candidate':{}, 'fixtures':{}, 'controls':{}}
    root = Path(root).resolve(); fixture_paths = {k:Path(v).resolve() for k,v in (fixtures or {}).items()}
    try:
        require(context in ('local','ci','release'), 'unsupported context')
        require(os.name == 'posix', 'process-group isolation not qualified on this platform')
        bundle, result['bundle_sha256'] = read_json(bundle_path, 'qa-kit.validation-bundle/v1')
        if expected_bundle is not None:
            require(DIGEST.fullmatch(expected_bundle) and expected_bundle == result['bundle_sha256'], 'bundle differs from trusted digest')
        fields(bundle, ('schema','protocol','qa_commit','registry_sha256','authorization_sha256','adapters','fixtures'))
        require(bundle['protocol'] == CONTRACT_VERSION, 'incompatible control bundle')
        result['controls']['qa'] = exact(qa_root, bundle['qa_commit'])
        registry, result['registry_sha256'] = read_json(registry_path, 'qa-kit.validation-registry/v1')
        require(result['registry_sha256'] == bundle['registry_sha256'], 'registry digest mismatch')
        fields(registry, ('schema','repos')); require(isinstance(registry['repos'],dict), 'invalid registry')
        require(repo in registry['repos'], 'repo is not enrolled')
        policy = registry['repos'][repo]
        fields(policy, ('contract','contract_sha256','selections','github_repository','required_selections'))
        if context != 'local':
            require(isinstance(policy['required_selections'],dict) and policy['required_selections'].get(context)==selection,
                    'selection differs from required context selection')
        result['github_repository']=policy['github_repository']
        auth, result['authorization_sha256'] = read_json(authorization_path, 'qa-kit.validation-authorization/v1')
        require(result['authorization_sha256'] == bundle['authorization_sha256'], 'authorization digest mismatch')
        fields(auth, ('schema','contexts','variants','effects'))
        for key in ('contexts','variants','effects'): strings(auth[key], key)
        require(context in auth['contexts'] and variant in auth['variants'], 'context/variant is not authorized')
        require(set(auth['effects']) <= EFFECTS, 'unsupported authorized effects')
        require(isinstance(bundle['adapters'],dict) and isinstance(bundle['fixtures'],dict), 'invalid control maps')
        if context != 'local':
            require(expected_bundle is not None, 'CI/release needs externally pinned bundle digest')
            require(adapter_root is not None and context in bundle['adapters'], 'trusted adapter unavailable')
            result['controls']['adapter'] = exact(adapter_root, bundle['adapters'][context])
        result['candidate']['before'] = exact(root, expected_head)
        contract_path = confined(root, policy['contract'])
        contract, result['contract_sha256'] = read_json(contract_path, 'qa-kit.validation-contract/v1')
        require(result['contract_sha256'] == policy['contract_sha256'], 'contract digest mismatch')
        execution_plan = plan(contract, policy, selection, variant)
        result['plan_sha256'] = json_digest(execution_plan)
        result['required'] = execution_plan['required']
        result['selected'] = execution_plan['selected']
        result['remaining_required'] = execution_plan['remaining_required']
        spec = execution_plan['environment']
        require(spec['os'] == platform.system().lower() and spec['arch'] == platform.machine(), 'platform/architecture mismatch')
        observed = runtimes(spec['runtimes'])
        result['observed'] = {'os':platform.system().lower(), 'arch':platform.machine(), 'runtimes':observed}
        needed = set(f for task in execution_plan['tasks'] for f in task['fixtures'])
        require(set(fixture_paths) == needed, 'missing or unexpected fixture mapping')
        for name in needed:
            require(name in bundle['fixtures'], 'fixture is not pinned')
            result['fixtures'][name] = {'before':exact(fixture_paths[name],bundle['fixtures'][name])}
        environments = {}
        for task in execution_plan['tasks']:
            require(set(task['effects']) <= set(auth['effects']), 'task effects are not authorized')
            confined(root, task['cwd'])
            environments[task['task']] = environment(root, task['env'], fixture_paths)
            resolved=[]
            for argument in task['argv']:
                if isinstance(argument,dict):
                    path=confined(Path(qa_root).resolve(),argument['qa_path'])
                    require(path.is_file(), 'QA helper must be a regular file')
                    git(qa_root,'ls-files','--error-unmatch','--',argument['qa_path'])
                    resolved.append(str(path))
                else:
                    resolved.append(argument)
            task['argv']=resolved
            # Check executable before any task can run.
            binary = task['argv'][0]
            aliases = {'python':'python','python3':'python','node':'node','bash':'bash','npm':'npm'}
            runtime = aliases.get(binary)
            require(runtime in observed or any(str(Path(binary).resolve()) == v['executable'] for v in observed.values()),
                    'task executable lacks observed runtime')
        def unchanged():
            result['candidate']['after'] = identity(root)
            require(result['candidate']['after'] == result['candidate']['before'], 'candidate source drift')
            for name, record in result['fixtures'].items():
                record['after'] = identity(fixture_paths[name])
                require(record['after'] == record['before'], 'fixture source drift: ' + name)
            require(identity(qa_root) == result['controls']['qa'], 'executor source drift')
            if context != 'local':
                require(identity(adapter_root) == result['controls']['adapter'], 'adapter source drift')
            for path, key in ((contract_path,'contract_sha256'), (registry_path,'registry_sha256'),
                              (bundle_path,'bundle_sha256'), (authorization_path,'authorization_sha256')):
                require(digest(Path(path).read_bytes()) == result[key], 'control input drift')
            for runtime in observed.values():
                require(digest(Path(runtime['executable']).read_bytes()) == runtime['sha256'], 'runtime binary drift')
        statuses = {}
        with tempfile.TemporaryDirectory(prefix='qa-validation-') as scratch:
            bindings=Path(scratch)/'bin'; bindings.mkdir()
            for name, runtime in observed.items():
                for alias in (('python','python3') if name=='python' else (name,)):
                    (bindings/alias).symlink_to(runtime['executable'])
            # Pin declared interpreter lookups in shell/npm descendants too. Only
            # system utilities follow these bindings, never the user's ambient PATH.
            base_env={'PATH':str(bindings)+':/usr/bin:/bin', 'HOME':scratch, 'TMPDIR':scratch,
                      'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','QA_VALIDATION_SCRATCH':scratch,
                      'PYTHONNOUSERSITE':'1'}
            for task in execution_plan['tasks']:
                if any(statuses[p] != 'pass' for p in task['after']):
                    record={'task':task['task'], 'status':'blocked', 'reason':'prerequisite failed', 'exit_code':None,'timed_out':False}
                else:
                    unchanged()
                    try:
                        record=execute(task,root,observed,{**base_env, **environments[task['task']]})
                    except (OSError, subprocess.SubprocessError) as exc:
                        record={'task':task['task'], 'status':'fail','reason':type(exc).__name__, 'exit_code':None,'timed_out':False}
                record['variant']=variant
                result['tasks'].append(record); statuses[task['task']]=record['status']
                try:
                    require(not record.get('cancelled'), 'execution cancelled by adapter')
                    unchanged()
                except Invalid as exc:
                    record['status']='fail'; statuses[task['task']]='fail'
                    result['errors'].append(str(exc))
                    for remaining in execution_plan['tasks'][len(result['tasks']):]:
                        result['tasks'].append({'task':remaining['task'],'variant':variant,'status':'blocked','reason':'source/control drift','exit_code':None,'timed_out':False})
                    break
        result['status']='pass' if all(t['status']=='pass' for t in result['tasks']) and not result['errors'] else 'fail'
        result['selection_complete']=result['status']=='pass' and not result['remaining_required']
    except (Invalid, OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        result['errors'].append(str(exc) if isinstance(exc, Invalid) else type(exc).__name__)
        result['status']='fail' if result['tasks'] else 'blocked'
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('root','repo','registry','bundle','selection','variant','expected-head','context','authorization','output','expected-bundle'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--adapter-root')
    parser.add_argument('--fixture', action='append', default=[])
    args=parser.parse_args()
    fixtures={}
    for item in args.fixture:
        if '=' not in item or item.split('=',1)[0] in fixtures:
            parser.error('fixture must be unique NAME=PATH')
        name,path=item.split('=',1); fixtures[name]=path
    output=Path(args.output)
    if output.exists(): parser.error('output already exists')
    protected=[Path(args.root).resolve(),HERE.resolve(),*(Path(v).resolve() for v in fixtures.values())]
    if args.adapter_root: protected.append(Path(args.adapter_root).resolve())
    if any(output.resolve().is_relative_to(root) for root in protected):
        parser.error('result output must be outside candidate, executor, adapter and fixture checkouts')
    result=run_validation(root=args.root, repo=args.repo, registry_path=args.registry,bundle_path=args.bundle,
                          selection=args.selection,variant=args.variant,expected_head=args.expected_head,
                          context=args.context,authorization_path=args.authorization,fixtures=fixtures,
                          adapter_root=args.adapter_root,expected_bundle=args.expected_bundle)
    try:
        with output.open('x',encoding='utf-8') as stream: json.dump(result,stream,indent=2); stream.write('\n')
    except OSError:
        print('cannot write validation result', file=sys.stderr); return 2
    print('validation '+result['status']+'; selection_complete='+str(result['selection_complete']).lower())
    return 0 if result['status']=='pass' else 1


if __name__=='__main__':
    raise SystemExit(main())
