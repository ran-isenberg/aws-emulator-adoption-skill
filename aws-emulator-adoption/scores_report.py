"""Pass rates per service, and per operation, from an AWS Emulator release's scores.json(.gz).

usage: python3 -I scores_report.py scores.json.gz dynamodb:PutItem,Query cognitoidentityprovider:InitiateAuth
       python3 -I scores_report.py scores.json.gz --find cognito     # list matching service namespaces
Service rows count whole checks (wire and behavioral). Operation rows count every wire-check step that called the
operation (behavioral checks don't record operations; read the known-gap files for those).
"""
import collections, gzip, json, sys

path, args = sys.argv[1], sys.argv[2:]
units = json.load((gzip.open if path.endswith('.gz') else open)(path, 'rt'))['units']


def namespace(service_id):  # 'com.amazonaws.dynamodb#DynamoDB_20120810' -> 'dynamodb'
    return service_id.split('#')[0].removeprefix('com.amazonaws.')


if args and args[0] == '--find':
    for ns in sorted({namespace(s) for u in units for s in u['services'] if args[1].lower() in s.lower()}):
        print(ns)
    sys.exit()

wanted = {a.split(':')[0]: set(filter(None, a.partition(':')[2].split(','))) for a in args}
stats = collections.defaultdict(lambda: [0, 0])


def count(key, passed):
    stats[key][0] += passed
    stats[key][1] += 1


for u in units:
    if u['outcome'] == 'skipped':
        continue
    for ns in {namespace(s) for s in u['services']} & wanted.keys():
        count((ns, '(service)', u['kind']), u['outcome'] == 'pass')
        for step in u['detail'].get('steps', []):
            if step.get('operation') in wanted[ns]:
                count((ns, step['operation'], 'wire step'), step.get('outcome') == 'pass')
for (ns, op, kind), (passed, total) in sorted(stats.items()):
    print(f'{ns:26} {op:24} {kind:10} {passed:5}/{total:<5} {passed / total:4.0%}')
for ns, ops in wanted.items():
    for op in sorted(ops - {k[1] for k in stats if k[0] == ns}):
        print(f'{ns:26} {op:24} no checks in this release: probe it yourself')
