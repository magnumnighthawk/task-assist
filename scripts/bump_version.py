#!/usr/bin/env python3
"""
Simple semantic-version bumping script.

Behavior:
- Reads the latest semver-style tag (vMAJOR.MINOR.PATCH) if present, else reads `VERSION` file.
- Scans commits since that tag (or from repo start) for Conventional Commit cues:
  - BREAKING CHANGE or commit with a bang (e.g. feat!:) => major bump
  - feat: => minor bump
  - fix: => patch bump
- Defaults to patch bump if no cues are found.

Usage:
  # dry-run, shows next version
  ./scripts/bump_version.py

  # apply the bump, update VERSION file and commit
  ./scripts/bump_version.py --apply --commit --tag

This script does not push tags. Use your CI to push tags and images.
"""
import argparse
import subprocess
import re
import sys
from typing import Optional, Tuple


def run(*cmd: str) -> str:
    return subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()


def get_latest_tag() -> Optional[str]:
    # list tags sorted by version-like order, prefer tags that start with 'v'
    try:
        tags = run('git', 'tag', '--list', '--sort=-v:refname', 'v*').splitlines()
        if tags:
            return tags[0]
    except Exception:
        pass
    # fallback: try any tag
    try:
        tags = run('git', 'tag', '--list', '--sort=-v:refname').splitlines()
        if tags:
            return tags[0]
    except Exception:
        pass
    return None


def read_version_file(path: str = 'VERSION') -> str:
    try:
        with open(path, 'r') as fh:
            return fh.read().strip()
    except Exception:
        return 'dev'


SEMVER_RE = re.compile(r'v?(\d+)\.(\d+)\.(\d+)$')


def parse_semver(s: str) -> Tuple[int, int, int]:
    m = SEMVER_RE.match(s)
    if not m:
        return (0, 0, 0)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def determine_bump(commits: str) -> str:
    # commits: concatenated commit messages
    major = False
    minor = False
    patch = False
    for msg in commits.split('\n\n'):
        if re.search(r'BREAKING CHANGE', msg, re.I) or re.search(r'^.+!:', msg, re.M):
            major = True
        if re.search(r'^\s*(feat|feature)(\(.+\))?:', msg, re.I):
            minor = True
        if re.search(r'^\s*(fix|bugfix|hotfix)(\(.+\))?:', msg, re.I):
            patch = True
    if major:
        return 'major'
    if minor:
        return 'minor'
    if patch:
        return 'patch'
    return 'patch'


def get_commits_since(tag: Optional[str]) -> str:
    try:
        if tag:
            commits = run('git', 'log', f'{tag}..HEAD', '--pretty=%B')
        else:
            commits = run('git', 'log', '--pretty=%B')
        return commits
    except Exception:
        return ''


def bump_version_tuple(v: Tuple[int, int, int], bump: str) -> Tuple[int, int, int]:
    major, minor, patch = v
    if bump == 'major':
        return (major + 1, 0, 0)
    if bump == 'minor':
        return (major, minor + 1, 0)
    return (major, minor, patch + 1)


def write_version_file(version: str, path: str = 'VERSION') -> None:
    with open(path, 'w') as fh:
        fh.write(version + '\n')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apply', action='store_true', help='Write the VERSION file')
    p.add_argument('--commit', action='store_true', help='Commit the VERSION file after writing')
    p.add_argument('--tag', action='store_true', help='Create a git tag for the new version (requires --commit or pre-existing commit)')
    p.add_argument('--push', action='store_true', help='Push commits and tags to the remote after creating them')
    p.add_argument('--remote', default='origin', help='Remote name to push to (default: origin)')
    p.add_argument('--force-level', choices=['major', 'minor', 'patch'], help='Force a specific bump level')
    args = p.parse_args()

    latest_tag = get_latest_tag()
    current = None
    if latest_tag:
        current = latest_tag.lstrip('v')
    else:
        current = read_version_file()

    base_tuple = parse_semver(current)

    commits = get_commits_since(latest_tag)
    if args.force_level:
        bump = args.force_level
    else:
        bump = determine_bump(commits)

    new_tuple = bump_version_tuple(base_tuple, bump)
    new_version = f'v{new_tuple[0]}.{new_tuple[1]}.{new_tuple[2]}'

    print(f'Current: {current}  Latest tag: {latest_tag or "<none>"}')
    print(f'Determined bump: {bump} => Next version: {new_version}')

    if not args.apply:
        print('\nDry-run mode: use --apply to write VERSION (and --commit/--tag to commit/tag)')
        sys.exit(0)

    # write VERSION
    write_version_file(new_version)
    print(f'Wrote VERSION with {new_version}')

    if args.commit:
        try:
            run('git', 'add', 'VERSION')
            run('git', 'commit', '-m', f'Bump version to {new_version}')
            print('Committed VERSION')
            committed = True
        except subprocess.CalledProcessError as e:
            print('Failed to commit VERSION:', e)
            sys.exit(2)
    else:
        committed = False

    if args.tag:
        try:
            run('git', 'tag', '-a', new_version, '-m', f'Release {new_version}')
            print(f'Created tag {new_version}')
            tagged = True
        except subprocess.CalledProcessError as e:
            print('Failed to create tag:', e)
            sys.exit(3)
    else:
        tagged = False

    # Optionally push commits and tags to remote
    if args.push:
        try:
            # push commits (if we created one)
            if committed:
                print(f'Pushing commit to {args.remote}...')
                run('git', 'push', args.remote)
                print('Pushed commit')

            # push tags. Use --follow-tags to push annotated tags that point to pushed commits.
            if tagged:
                print(f'Pushing tag {new_version} to {args.remote} (using --follow-tags)...')
                run('git', 'push', args.remote, '--follow-tags')
                print('Pushed tag(s)')
        except subprocess.CalledProcessError as e:
            print('Failed to push to remote:', e)
            sys.exit(4)


if __name__ == '__main__':
    main()
