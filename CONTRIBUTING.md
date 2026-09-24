# Contributing to qa-kit

This is the complete public contribution workflow. It assumes an outside
contributor with access only to this repository. No BeanLabs workspace, Agency
account, credentials, or private fleet checkout is required.

## Requirements

- Git.
- CPython 3.12. The tested runtime is Python 3.12 on GitHub Actions
  `ubuntu-latest`, as configured in `.github/workflows/test.yml`. Other Python
  versions and operating systems are not claimed as supported.
- No third-party Python packages. The checked-in code and tests use the Python
  standard library.

Run these commands from the repository root. Confirm that `python3` is 3.12
before relying on a local result:

```bash
python3 --version
```

## Setup

```bash
git clone https://github.com/stevekkall-beansgc/qa-kit.git
cd qa-kit
python3 --version
```

There is no dependency installation step.

## Local checks

Run the same public checks used by the repository's test workflow:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_stdlib.py bin/
CI=true bash bin/qa_selfcheck.sh
```

Run the standalone showcase as an additional integration check:

```bash
python3 examples/synthetic_quickstart.py
```

The committed public report sample is generated from the quickstart's real
passing docs-and-unit scenario. Verify it with:

```bash
python3 examples/synthetic_quickstart.py --verify-sample examples/synthetic_quickstart_report.json
```

To intentionally refresh the normalized sample, run:

```bash
python3 examples/synthetic_quickstart.py --write-sample examples/synthetic_quickstart_report.json
```

`--write-sample` writes the report to the requested `PATH`; the command above
overwrites the checked-in sample. Both sample commands run the real runner
against disposable synthetic fixtures; they do not use the default
`manifest.json` or a private workspace.

## What to include

- Keep changes standard-library-only unless a separately approved dependency
  change is part of the contribution.
- Add or update a regression test for a bug fix or behavior change.
- Keep secrets, credentials, real user data, private paths, and private fleet
  output out of commits, fixtures, reports, and documentation.
- For ordinary public contributions, do not edit the private fleet
  `manifest.json`; a registry change requires a separately reviewed maintainer
  request.
- Run the relevant commands above before opening a pull request.

The repository's [AGENTS.md](AGENTS.md) and [STANDARDS.md](STANDARDS.md) contain
additional internal engineering context. They do not replace the public checks
above.
