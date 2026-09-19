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
from . import wechat
from . import xhs
from . import jike
from . import douyin
from . import xiaoyuzhou
from . import shipinhao

def main():
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
    wechat.reg_subparser(subparsers)
    xhs.reg_subparser(subparsers)
    jike.reg_subparser(subparsers)
    douyin.reg_subparser(subparsers)
    xiaoyuzhou.reg_subparser(subparsers)
    shipinhao.reg_subparser(subparsers)

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__': main()