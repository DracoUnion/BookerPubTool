import argparse
import sys
from . import __version__
from . import docker
from . import pypi
from . import npm
from . import ebook2site
from . import libgen
from . import zhihu_msger
from . import git
from . import kan
from . import gzh
from . import xhs_plrt
from . import jike_plrt
from . import douyin_plrt
from . import xiaoyuzhou_plrt
from . import shipinhao_plrt
from . import zhihu
from . import csdn
from . import cnblogs
from . import toutiao
from . import weibo
from . import xhs
from . import bili_video
from . import sohu
from . import juejin

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="BookerPubTool", formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--version", action="version", version=f"PYBP version: {__version__}")
    parser.set_defaults(func=lambda x: parser.print_help())
    subparsers = parser.add_subparsers()

    docker.reg_subparser(subparsers)
    pypi.reg_subparser(subparsers)
    npm.reg_subparser(subparsers)
    ebook2site.reg_subparser(subparsers)
    libgen.reg_subparser(subparsers)
    zhihu_msger.reg_subparser(subparsers)
    git.reg_subparser(subparsers)
    kan.reg_subparser(subparsers)
    gzh.reg_subparser(subparsers)
    xhs_plrt.reg_subparser(subparsers)
    jike_plrt.reg_subparser(subparsers)
    douyin_plrt.reg_subparser(subparsers)
    xiaoyuzhou_plrt.reg_subparser(subparsers)
    shipinhao_plrt.reg_subparser(subparsers)
    zhihu.reg_subparser(subparsers)
    csdn.reg_subparser(subparsers)
    cnblogs.reg_subparser(subparsers)
    toutiao.reg_subparser(subparsers)
    weibo.reg_subparser(subparsers)
    xhs.reg_subparser(subparsers)
    bili_video.reg_subparser(subparsers)
    sohu.reg_subparser(subparsers)
    juejin.reg_subparser(subparsers)

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__': main()