"""R29 #323: entry.ps1 starts the bundled Python with this fixed shim. Line 1 of stdin is JSON {script, args};
sys.argv is set from it, so no value ever crosses a Windows command line (PS 5.1 native-argument quoting of empty
strings, quotes, CJK and newlines does not apply). The rest of stdin (the key line, if any) stays for the script."""
import json, runpy, sys

req = json.loads(sys.stdin.buffer.readline().decode('utf-8'))
if not isinstance(req, dict) or set(req) != {'script', 'args'} or not isinstance(req['args'], list) \
        or not all(isinstance(x, str) for x in req['args']):
    sys.stderr.write('WINQA_E_REQUEST argshim\n'); sys.exit(64)
sys.argv = [req['script']] + req['args']
sys.path.insert(0, __import__('os').path.dirname(req['script']))
runpy.run_path(req['script'], run_name='__main__')
