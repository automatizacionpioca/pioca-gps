#!/usr/bin/env python3
"""Ejecuta el mismo flujo de construccion V7..B15 original presente en GitHub.
No regenera ni sustituye sus scripts nativos: solo orquesta los pasos de RUN.
"""
from pathlib import Path
import subprocess
import yaml

root=Path.cwd()
yml=root/'.github/workflows/build-android-apk-B15-ETA-PREAPROXIMACION-AUTOCONTENIDO.yml'
spec=yaml.safe_load(yml.read_text(encoding='utf-8'))
steps=spec['jobs']['build']['steps']
first=next((i for i,s in enumerate(steps) if str(s.get('name','')).startswith('Generar proyecto base V7')),None)
last=next((i for i,s in enumerate(steps) if str(s.get('name','')).startswith('Verificar configuración B15')),None)
if first is None or last is None or first>=last:
    raise SystemExit('B16: no pude identificar el flujo base V7..B15 en GitHub')
for st in steps[first:last+1]:
    script=st.get('run')
    if not script:
        raise SystemExit('B16: paso del flujo B15 sin script: '+str(st.get('name','?')))
    workdir=root/str(st.get('working-directory','.'))
    print('EJECUTANDO B15:',st.get('name','paso'),flush=True)
    subprocess.run(['bash','-e','-o','pipefail','-c',script],check=True,cwd=workdir)
print('B15 generada y verificada sin modificaciones en el repo')
