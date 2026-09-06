# BookerPubTool

ApacheCN 书籍一键发布工具：把电子书（PDF / EPUB / MOBI / AZW3）或文档站点发布到 **Docker Hub / PyPI / npm / Libgen / 看云（KanCloud）**，同时内置知乎私信、Git 批量提交/推送等发布相关工具。

> GitHub: <https://github.com/apachecn/BookerPubTool>

---

## 安装

```bash
pip install .          # 或
pip install -e .       # 开发模式，改动即时生效
```

依赖来自 `requirements.txt` / `pyproject.toml`（requests、pyquery、twine、wheel、jieba、xpinyin）。部分功能需要额外的外部命令：

- Docker 发布需要本机安装 `docker`
- npm 发布需要本机安装 `node` / `npm`
- MOBI / AZW3 转换需要 `calibre` 的 `ebook-convert`

## 命令总览

安装后提供 3 个入口（等价），也支持模块方式运行：

```bash
BookerPubTool <cmd> [args]
bpt <cmd> [args]
pub-tool <cmd> [args]
python -m BookerPubTool <cmd> [args]
```

```text
{ pub-docker, pub-pypi, conf-pypi, pub-npm, conf-npm, ebook2site,
  libgen, zhihu-msg, zhihu-crawl-uid, git-init, git-commit, git-push,
  kancloud }
```

每个命令都可以用 `-h` / `--help` 查看详细参数。全局参数：

| 参数 | 说明 |
| --- | --- |
| `-v, --version` | 显示版本号 |
| `-h, --help` | 显示帮助 |

## 快速上手

```bash
# 1. 配置发布凭证
bpt conf-pypi <pypi-token>
bpt conf-npm  <npm-token>

# 2. 把电子书转换为站点目录
bpt ebook2site ./book.epub -d ./docs

# 3. 发布站点（dir 为包含 index.html 和 README.md 的目录）
bpt pub-pypi   ./docs
bpt pub-npm    ./docs
bpt pub-docker ./docs
```

> **注意**：`pub-*` 命令的 `dir` 既可以是一个文档目录，也可以直接传一个 PDF / EPUB / MOBI / AZW3 文件——此时会先用 `ebook2site` 自动转成站点再发布。

---

## 发布类命令

### `pub-pypi` — 发布站点到 PyPI

```text
usage: bpt pub-pypi [-h] [-e EXPIRE] [-w WAIT] [-p PROXY] dir
```

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `dir` | 文档目录或电子书文件（必填） | — |
| `-e, --expire` | 过期日期，格式 `YYYYMMDD`。若 PyPI 上最新包的日期 ≥ 该值则跳过发布 | 无（总是发布） |
| `-w, --wait` | 发布成功后等待的秒数 | `0` |
| `-p, --proxy` | HTTP 代理，如 `http://127.0.0.1:7890` | 无 |

示例：

```bash
bpt pub-pypi ./docs -e 20260906 -w 30 -p http://127.0.0.1:7890
```

### `conf-pypi` — 配置 PyPI 上传凭证

```text
usage: bpt conf-pypi [-h] token
```

等价于 `pip config set pypi.username __token__` 和 `pip config set pypi.password <token>`。

```bash
bpt conf-pypi pypi_xxxxxxxxxxxxxxxxxxxx
```

### `pub-npm` — 发布站点到 npm

```text
usage: bpt pub-npm [-h] [-e EXPIRE] dir
```

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `dir` | 文档目录或电子书文件（必填） | — |
| `-e, --expire` | 过期日期，格式 `YYYYMMDD`。逻辑同 `pub-pypi` | 无（总是发布） |

```bash
bpt pub-npm ./docs -e 20260906
```

### `conf-npm` — 配置 npm 上传凭证

```text
usage: bpt conf-npm [-h] token
```

等价于 `npm config set //registry.npmjs.org/:_authToken <token>`。

```bash
bpt conf-npm npm_xxxxxxxxxxxxxxxxxxxx
```

### `pub-docker` — 发布站点到 Docker Hub

```text
usage: bpt pub-docker [-h] [-e EXPIRE] [-p PROXY] dir
```

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `dir` | 文档目录或电子书文件（必填） | — |
| `-e, --expire` | 过期日期，格式 `YYYYMMDD`。逻辑同 `pub-pypi` | 无（总是发布） |
| `-p, --proxy` | HTTP 代理 | 无 |

发布到 `apachecn0/<name>` 仓库，镜像名取目录名（小写）。若目录中没有 `Dockerfile` 会自动生成一个基于 `httpd:2.4` 的。

```bash
bpt pub-docker ./docs -e 20260906
```

### `ebook2site` — 把电子书转换为站点目录

```text
usage: bpt ebook2site [-h] [-n NAME] [-d DIR] [-s SUFFIX] file
```

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `file` | 电子书文件：PDF / EPUB（必填） | — |
| `-n, --name` | 项目名；缺省时由文件名自动生成（中文转拼音、数字开头加 `x`） | 自动生成 |
| `-d, --dir` | 输出目录 | `.` |
| `-s, --suffix` | 名称后缀，追加到 `name` 后 | 空 |

输出目录 `dir/name` 中会生成 `index.html`、`file.pdf`/epub 阅读器以及 `README.md`，可直接作为 `pub-*` 的输入。

```bash
bpt ebook2site ./book.epub -n my-book -d ./docs -s v2
```

### `libgen` — 上传到 Libgen

```text
usage: bpt libgen [-h] [-t THREADS] [-p PROXY] series fname
```

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `series` | 系列名，决定分类与元信息解析规则（必填） | — |
| `fname` | 文件或目录（必填）；传目录时并发处理其中所有文件 | — |
| `-t, --threads` | 并发线程数 | `3` |
| `-p, --proxy` | HTTP 代理 | 无 |

`series` 支持的值及对应分类：

| 值 | 分类 |
| --- | --- |
| `lightnovel` / `biquge` / `giantessnight` / `dmzj` / `nhentai` | `fiction` |
| `it-ebooks` / `ixinzhi` | `main` |

```bash
bpt libgen it-ebooks ~/books -t 5
bpt libgen lightnovel ~/book.epub
```

---

## 知乎类命令

### `zhihu-msg` — 批量发送知乎私信

```text
usage: bpt zhihu-msg [-h] [-m CONTENT] [-c COOKIES] [-n] [-s WAIT_SUCC] [-f WAIT_FAIL] [-b WAIT_403] uid_fname
```

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `uid_fname` | 包含知乎 uid 的文件，每行一个（必填） | — |
| `-m, --content` | 私信内容 | 布客社区默认文案 |
| `-c, --cookies` | 多个 cookie 用 `;;` 分隔 | 环境变量 `ZHIHU_COOKIES`，缺省为空 |
| `-n, --new` | 使用新版 Chat API（`api/v4//chat`）；否则用旧版 messages API | 旧版 |
| `-s, --wait-succ` | 发送成功后等待秒数 | `60` |
| `-f, --wait-fail` | 普通失败后等待秒数（HTTP 403 除外） | `0` |
| `-b, --wait-403` | HTTP 403 后等待秒数 | `0` |

```bash
export ZHIHU_COOKIES='z_c0=xxx;; z_c0=yyy'
bpt zhihu-msg ./uid.txt -m 'Hello' -s 30
bpt zhihu-msg ./uid.txt --new
```

### `zhihu-crawl-uid` — 从话题爬取知乎 uid

```text
usage: bpt zhihu-crawl-uid [-h] [-u UID_FNAME] tid_fname
```

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `tid_fname` | 包含话题 id（tid）的文件，每行一个（必填） | — |
| `-u, --uid-fname` | 输出 uid 的文件，结果追加写入 | `uid.txt` |

```bash
bpt zhihu-crawl-uid ./tid.txt -u ./uid2.txt
```

---

## Git 类命令

发布到各处之前，常用这套命令把文档提交到 GitHub 仓库。

### `git-init` — 初始化 Git 仓库

```text
usage: bpt git-init [-h] [-d DIR] [-o ORIGIN] [-u USER] [-e EMAIL]
```

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `-d, --dir` | 仓库目录 | `.` |
| `-o, --origin` | 远程 origin 地址（可选，提供则设置） | 无 |
| `-u, --user` | `git config user.name` | `unknown` |
| `-e, --email` | `git config user.email` | `unknown@example.com` |

```bash
bpt git-init -d ./docs -o git@github.com:user/repo.git -u wizardforcel -e me@example.com
```

### `git-commit` — 逐个文件提交

```text
usage: bpt git-commit [-h] [-d DIR] [-n COUNT] [-x RESET] [-u USER] [-e EMAIL]
```

把未跟踪文件一个一个单独提交（每个 `add` + `commit`），方便大仓库分次推送。

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `-d, --dir` | 仓库目录 | `.` |
| `-n, --count` | 本次提交的文件数量上限 | `1000000000` |
| `-x, --reset` | 每隔 N 秒强制重启子进程（防止进程被杀/卡死） | `0`（不重启） |
| `-u, --user` | `git config user.name` | `unknown` |
| `-e, --email` | `git config user.email` | `unknown@example.com` |

```bash
bpt git-commit -d ./docs -n 1000 -x 5400
```

### `git-push` — 逐个提交推送

```text
usage: bpt git-push [-h] [-d DIR] [-r REMOTE] [-b BRANCH] [-n COUNT] [-x RESET]
```

把本地新提交一个一个推到远程分支。若远程分支领先会提示手动 `git pull`。

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `-d, --dir` | 仓库目录 | `.` |
| `-r, --remote` | 远程名；也可直接传 URL，会自动添加为临时远程 | `origin` |
| `-b, --branch` | 推送的分支 | `master` |
| `-n, --count` | 本次推送的提交数量上限 | `1000000000` |
| `-x, --reset` | 每隔 N 秒强制重启子进程 | `0`（不重启） |

```bash
bpt git-push -d ./docs -r origin -b master -n 1000 -x 5400
```

---

## 看云类命令

### `kancloud` — 发布站点到看云

```text
usage: bpt kancloud [-h] [-u UN] [-c COOKIE] dir
```

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `dir` | 文档目录，需包含 `SUMMARY.md` 和 `README.md`（必填） | — |
| `-u, --un` | 看云用户名 | `wizardforcel` |
| `-c, --cookie` | 看云登录 cookie | 环境变量 `KAN_COOKIE`，缺省为空 |

```bash
export KAN_COOKIE='PHPSESSID=xxx; remember_xxx=xxx'
bpt kancloud ./docs -u myname
```

---

## 环境变量

| 变量 | 用途 | 生效命令 |
| --- | --- | --- |
| `ZHIHU_COOKIES` | 知乎 cookie，多个用 `;;` 分隔 | `zhihu-msg` 的 `--cookies` 默认值 |
| `KAN_COOKIE` | 看云 cookie | `kancloud` 的 `--cookie` 默认值 |

---

## 发布到 PyPI（给本工具自己做新版本）

```bash
publish.sh      # = rm -rf dist; python -m build; twine upload dist/*
```

需要先 `pip install build` 并通过 `conf-pypi` 配置好凭证。版本号在 `pyproject.toml` 和 `BookerPubTool/__init__.py` 中维护。