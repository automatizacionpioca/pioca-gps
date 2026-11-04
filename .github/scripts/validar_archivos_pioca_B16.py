#!/usr/bin/env python3
"""Validación estática de archivos B16 generados (sin tocar producción)."""
from __future__ import annotations
from pathlib import Path
import re, subprocess, shutil, sys, tempfile, importlib.util

def validate(root:Path):
    files=['admin.html','index.html','cliente.html']
    node=shutil.which('node')
    if not node:
        print('ADVERTENCIA: falta Node.js; no se pudo validar sintaxis JavaScript localmente.')
    else:
        total=0
        for name in files:
            html=(root/name).read_text(encoding='utf-8')
            scripts=re.findall(r'<script\b[^>]*>(.*?)</script\s*>',html,re.S|re.I)
            for i,js in enumerate(scripts):
                if not js.strip():continue
                with tempfile.NamedTemporaryFile('w',suffix='.js',encoding='utf-8',delete=False) as f:
                    f.write(js);p=Path(f.name)
                try:
                    result=subprocess.run([node,'--check',str(p)],capture_output=True,text=True)
                    if result.returncode:
                        raise RuntimeError(name+': script '+str(i)+' inválido\n'+result.stderr)
                    total+=1
                finally:p.unlink(missing_ok=True)
        print('OK: sintaxis de',total,'scripts JavaScript')
    workflow=root/'.github/workflows/build-android-apk-B16-FLUIDEZ.yml'
    patch=root/'.github/scripts/patch_android_b16_webview.py'
    compile(patch.read_text(encoding='utf-8'),str(patch),'exec')
    t=workflow.read_text(encoding='utf-8')
    for required in ['versionCode 16','patch_android_b16_webview.py','Compilar APK debug','piOca-Seguimiento-APK-B16-FLUIDEZ']:
        if required not in t:raise RuntimeError('Workflow B16 falta '+required)
    if importlib.util.find_spec('yaml'):
        import yaml
        data=yaml.safe_load(t)
        if not isinstance(data.get('jobs'),dict):raise RuntimeError('Workflow YAML inválido')
        print('OK: sintaxis YAML workflow')
    print('OK: programa de parche nativo B16 válido en Python')

if __name__=='__main__':
    if len(sys.argv)!=2:sys.exit('Uso: python validar_archivos_pioca_B16.py ruta/archivos')
    validate(Path(sys.argv[1]))
