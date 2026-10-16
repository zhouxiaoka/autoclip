#!/usr/bin/env python3
"""R29 #323: build the one-line JSON request for ps/entry.ps1 from local argv (bash passes values as separate
argv entries; nothing is interpreted by any shell). Prints the line.
    winqa_req.py ps SCRIPT [Name=value | Name]...      (Name alone = switch)
    winqa_req.py py SCRIPT [--key] [arg]...            (--key: a key line follows on stdin, has_key=true)
    winqa_req.py hash FILE | make_parts DST NAME... | merge_parts DST NAME... | remove_parts DST
"""
import json, sys


def build(a):
    op = a[0]
    if op == 'ps':
        params = {}
        for x in a[2:]:
            k, eq, v = x.partition('=')
            params[k] = v if eq else True
        return {'op': 'ps', 'args': {'script': a[1], 'params': params}, 'has_key': False}
    if op == 'py':
        key = len(a) > 2 and a[2] == '--key'
        return {'op': 'py', 'args': {'script': a[1], 'args': a[3:] if key else a[2:]}, 'has_key': key}
    if op == 'hash':
        return {'op': 'hash', 'args': {'file': a[1]}, 'has_key': False}
    if op in ('make_parts', 'merge_parts'):
        return {'op': op, 'args': {'dst': a[1], 'names': a[2:]}, 'has_key': False}
    if op == 'remove_parts':
        return {'op': op, 'args': {'dst': a[1]}, 'has_key': False}
    raise SystemExit(2)


if __name__ == '__main__':
    print(json.dumps(build(sys.argv[1:]), ensure_ascii=False, separators=(',', ':')))
