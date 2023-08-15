import re
import os
from os import path
import shutil
import sys
import subprocess as subp
import zipfile
from io import BytesIO
from .util import *


def ebook2site(fname, odir):
    if path.isdir(odir):
        shutil.rmtree(odir)
    os.makedirs(odir)
    ext = extname(fname)
    if ext == 'pdf':
        shutil.copy(fname, path.join(odir, 'file.pdf'))
        shutil.copy(
            d('asset/pdf.html'), 
            path.join(odir, 'index.html'),
        )
    elif ext in ['epub', 'mobi', 'azw3']:
        tmp_fname = path.join(odir, 'file.epub')
        if ext in ['mobi', 'azw3']:
            r = subp.Popen(
                ['ebook-convert', fname, tmp_fname], 
                shell=True,
            ).communicate()
        else:
            shutil.copy(fname, tmp_fname)
        zip = zipfile.ZipFile(BytesIO(open(d('asset/epubjs-reader.zip'), 'rb').read()))
        for f in zip.namelist(): zip.extract(f, odir)
        zip.close()
    else:
        raise ValueError('文件必须是 PDF、EPUB、MOBI 或 AZW3')
    title = path.basename(fname).replace('.pdf', '').replace('.epub', '')
    name = path.basename(path.abspath(odir))
    npm_name = npm_filter_name(name)
    README_TMP = read_file(d('asset/readme.tmpl'), 'utf-8')
    README_MD = README_TMP \
        .replace('{title}', title) \
        .replace('{docker_hub_name}', name) \
        .replace('{pip_name}', name) \
        .replace('{npm_name}', npm_name)
    open(path.join(odir, 'README.md'), 'w', encoding='utf8').write(README_MD)

def ebook2site_handle(args):
    name = args.name
    fname = args.file
    dir = args.dir
    suff = args.suffix
        
    if not fname.endswith('.pdf') and \
       not fname.endswith('.epub'):
        print(f'{timestr()} 请提供 PDF 或 EPUB')
        return 
    
    if not name: name = gen_proj_name(path.basename(fname))
    if suff:
        suff = gen_proj_name(suff)
        if suff: name += '-' + suff
    proj_dir = path.join(dir, name)
    ebook2site(fname, proj_dir)
    
