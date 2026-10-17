"""Extend the preserved-app smoke with actual dense PDF/resource measurements.

Set DOCLENS_FREEZE_FIXTURES to the generated fixture directory. Uses the existing
recovery smoke's isolated Qdrant/network/model fixtures; no hosted inference.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import subprocess
import time

import requests
import mac_upload_recovery_smoke as recovery

fixtures = Path(os.environ['DOCLENS_FREEZE_FIXTURES'])
evidence = Path(os.environ['DOCLENS_MAC_EVIDENCE'])
evidence.mkdir(parents=True, exist_ok=True)
original_docker = recovery.docker
original_gateway = recovery.gateway


def docker(*args):
    args = list(args)
    if args[:1] == ['run'] and '--network-alias' in args and args[args.index('--network-alias')+1] == 'backend':
        args[1:1] = ['--cpus=2', '--memory=1536m', '--memory-swap=1536m']
    return original_docker(*args)


def stage_values(base):
    text = requests.get(base+'/metrics', timeout=5).text
    return {name:float(value) for name,value in re.findall(r'doclens_upload_stage_seconds_sum\{stage="([^"]+)"\} ([0-9.e+\-]+)',text)}


def gateway(base, secret, location):
    # Find only our isolated fixture backend, never an existing application.
    names = original_docker('ps','--filter','name=doclens-mac-api-','--format','{{.Names}}').splitlines()
    assert len(names) == 1, names
    stats_file = location/'process-resources.jsonl'
    results = {}
    with stats_file.open('w') as log:
        sampler = 'import time,json,pathlib,os; start=time.monotonic(); ticks=os.sysconf("SC_CLK_TCK");\nwhile time.monotonic()-start<18:\n s=pathlib.Path("/proc/1/status").read_text(); cpu=pathlib.Path("/proc/1/stat").read_text().split(); m={line.split(":")[0]:int(line.split()[1]) for line in s.splitlines() if line.startswith(("VmRSS:","VmHWM:"))}; m.update(seconds=time.monotonic()-start,cpu_seconds=(int(cpu[13])+int(cpu[14]))/ticks); print(json.dumps(m),flush=True); time.sleep(.25)'
        stats = subprocess.Popen(['docker','exec',names[0],'python','-u','-c',sampler],stdout=log,stderr=subprocess.STDOUT)
        try:
            for name in ('padded-28mib.pdf','text-heavy-40pages.pdf','text-heavy-28mib.pdf'):
                data = (fixtures/name).read_bytes()
                before = stage_values(base);began=time.perf_counter();latencies=[];timeouts=0
                with ThreadPoolExecutor() as pool:
                    upload = pool.submit(requests.post,base+'/documents/process',headers={'X-DocLens-Internal-Key':secret},
                        files={'file':(name,data,'application/pdf')},timeout=115)
                    while not upload.done():
                        start=time.perf_counter()
                        try:requests.get(base+'/',timeout=.35).raise_for_status();latencies.append(time.perf_counter()-start)
                        except requests.RequestException:timeouts+=1
                        time.sleep(.1)
                    response=upload.result()
                after=stage_values(base)
                expected=413 if name=='text-heavy-28mib.pdf' else 200
                assert response.status_code==expected,response.text
                assert timeouts==0,(name,timeouts)
                results[name]={'bytes':len(data),'status':response.status_code,'seconds':time.perf_counter()-began,
                    'health_successes':len(latencies),'health_timeouts':timeouts,'health_max_seconds':max(latencies,default=None),
                    'stage_seconds':{key:after.get(key,0)-before.get(key,0) for key in after}}
                print('PASS constrained container PDF:',json.dumps({name:results[name]}),flush=True)
            inspect=json.loads(original_docker('inspect',names[0]))[0]
            assert inspect['HostConfig']['Memory']==1536*1024*1024
            assert inspect['HostConfig']['NanoCpus']==2_000_000_000
            results['docker_requested_limits']={'memory_bytes':inspect['HostConfig']['Memory'],'nano_cpus':inspect['HostConfig']['NanoCpus'],
                'swap_total_bytes':inspect['HostConfig']['MemorySwap']}
        finally:
            try:stats.wait(timeout=25)
            except subprocess.TimeoutExpired:stats.kill();stats.wait(timeout=5)
    (location/'cgroup-driver.txt').write_text(original_docker('info','--format','{{.CgroupDriver}} {{.CgroupVersion}}'))
    (location/'processing-measurements.json').write_text(json.dumps(results,indent=2)+'\n')
    original_gateway(base,secret,location)


recovery.docker=docker
recovery.gateway=gateway
if __name__=='__main__':recovery.main()
