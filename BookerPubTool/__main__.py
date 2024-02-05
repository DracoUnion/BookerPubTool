import argparse
import sys
from . import __version__
from .pypi import *
from .npm import *
from .docker import *
from .ebook2site import *
from .libgen import *
from .zhihu_msger import *
from .git import *
from .csdn import *

def main():
    parser = argparse.ArgumentParser(prog="BookerPubTool", formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--version", action="version", version=f"PYBP version: {__version__}")
    parser.set_defaults(func=lambda x: parser.print_help())
    subparsers = parser.add_subparsers()
    
    docker_pub_parser = subparsers.add_parser("pub-docker", help="publish book to dockerhub")
    docker_pub_parser.add_argument("dir", help="dir")
    docker_pub_parser.add_argument("-e", "--expire", help="expire date for old packages")
    docker_pub_parser.add_argument("-p", "--proxy", help="http proxy")
    docker_pub_parser.set_defaults(func=publish_docker)

    pypi_pub_parser = subparsers.add_parser("pub-pypi", help="publish book to pypi")
    pypi_pub_parser.add_argument("dir", help="dir")
    pypi_pub_parser.add_argument("-e", "--expire", help="expire date for old packages")
    pypi_pub_parser.set_defaults(func=publish_pypi)
    
    pypi_config_parser = subparsers.add_parser("conf-pypi", help="configure pypi token")
    pypi_config_parser.add_argument("token", help="token")
    pypi_config_parser.set_defaults(func=config_pypi)
    
    npm_pub_parser = subparsers.add_parser("pub-npm", help="publish book to npm")
    npm_pub_parser.add_argument("dir", help="dir")
    npm_pub_parser.add_argument("-e", "--expire", help="expire date for old packages")
    npm_pub_parser.set_defaults(func=publish_npm)
    
    npm_config_parser = subparsers.add_parser("conf-npm", help="configure npm token")
    npm_config_parser.add_argument("token", help="token")
    npm_config_parser.set_defaults(func=config_npm)
    
    ebook2site_parser = subparsers.add_parser("ebook2site", help="convert an ebook to a site")
    ebook2site_parser.add_argument("file", help="file")
    ebook2site_parser.add_argument("-n", "--name", help="name")
    ebook2site_parser.add_argument("-d", "--dir", help="dir", default='.')
    ebook2site_parser.add_argument("-s", "--suffix", help="suffix", default='')
    ebook2site_parser.set_defaults(func=ebook2site_handle)
    
    libgen_parser = subparsers.add_parser("libgen", help="upload to libgen")
    libgen_parser.add_argument("series", help="series")
    libgen_parser.add_argument("fname", help="file name")
    libgen_parser.add_argument("-t", "--threads", type=int, default=3, help="thread count")
    libgen_parser.add_argument("-p", "--proxy", help="proxy")
    libgen_parser.set_defaults(func=upload_libgen)
    
    zhihu_msg_parser = subparsers.add_parser("zhihu-msg", help="send zhihu messages")
    zhihu_msg_parser.add_argument("uid_fname", help="file name including uids")
    zhihu_msg_parser.add_argument(
        "-m", "--content", 
        default='布客社区\n\n您永远在线的两性情感和技术变现专家\n\n🔗https://docs.apachecn.org', 
        help="message content",
    )
    zhihu_msg_parser.add_argument("-c", "--cookies", default=os.environ.get('ZHIHU_COOKIES', ''), help="zhihu cookies splited with ';;'")
    zhihu_msg_parser.add_argument("-n", "--new", action='store_true', help="whether to use new API")
    zhihu_msg_parser.add_argument("-s", "--wait-succ", type=float, default=60, help="how long to wait after success")
    zhihu_msg_parser.add_argument("-f", "--wait-fail", type=float, default=0, help="how long to wait after failure except HTTP403")
    zhihu_msg_parser.add_argument("-b", "--wait-403", type=float, default=0, help="how long to wait after HTTP403")
    zhihu_msg_parser.set_defaults(func=send_msg_handle)
    
    zhihu_uid_parser = subparsers.add_parser("zhihu-crawl-uid", help="crawl zhihu uids from topics")
    zhihu_uid_parser.add_argument("tid_fname", help="file name including tids")
    zhihu_uid_parser.add_argument("-u", "--uid-fname", default='uid.txt', help="output file name including uids")
    zhihu_uid_parser.set_defaults(func=crawl_uids_handle)
    
    git_init_parser = subparsers.add_parser("git-init", help="init git repo")
    git_init_parser.add_argument('-d', "--dir", default='.', help="git repo dir")
    git_init_parser.add_argument("-o", "--origin", help="remote origin url")
    git_init_parser.add_argument('-u', "--user", default='unknown', help="git config user.name")
    git_init_parser.add_argument('-e', "--email", default='unknown@example.com', help="git config user.email")
    git_init_parser.set_defaults(func=git_init)

    git_commit_parser = subparsers.add_parser("git-commit", help="git commit per file")
    git_commit_parser.add_argument('-d', "--dir", default='.', help="git repo dir")
    git_commit_parser.add_argument('-n', "--count", type=int, default=1_000_000_000, help="num of files to commit")
    git_commit_parser.add_argument('-x', "--reset", type=int, default=0, help="num of seceonds after which to reset process")
    git_commit_parser.add_argument('-u', "--user", default='unknown', help="git config user.name")
    git_commit_parser.add_argument('-e', "--email", default='unknown@example.com', help="git config user.email")
    git_commit_parser.set_defaults(func=git_commit_handle)

    git_push_parser = subparsers.add_parser("git-push", help="git push per commit")
    git_push_parser.add_argument('-d', "--dir", default='.', help="git repo dir")
    git_push_parser.add_argument("-r", "--remote", default='origin', help="remote repo to push")
    git_push_parser.add_argument("-b", "--branch", default='master', help="branch to push")
    git_push_parser.add_argument('-n', "--count", type=int, default=1_000_000_000, help="num of commits to push")
    git_push_parser.add_argument('-x', "--reset", type=int, default=0, help="num of seceonds after which to reset process")
    git_push_parser.set_defaults(func=git_push_handle)

    csdn_parser = subparsers.add_parser("csdn", help="csdn post")
    csdn_parser.add_argument('fname', help="md file name")
    csdn_parser.add_argument("-c", "--cookie", default=os.environ.get('CSDN_COOKIE', ''), help="csdn cookie")
    csdn_parser.set_defaults(func=pub_csdn)


    args = parser.parse_args()
    args.func(args)
    
if __name__ == '__main__': main()