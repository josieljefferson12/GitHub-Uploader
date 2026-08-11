#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=============================================================
                 GITHUB UPLOADER
=============================================================

Usuário:
    josieljefferson12

Repositório:
    GitHub-Uploader

Token:
    MY_GITHUB_TOKEN

Entrada aceita:
    ✓ Pasta completa
    ✓ arquivo .zip
    ✓ arquivo .7z

Processamento:
    ✓ Extrai ZIP automaticamente
    ✓ Extrai 7Z automaticamente
    ✓ Copia arquivos recursivamente
    ✓ Preserva estrutura de diretórios
    ✓ git add
    ✓ UM único commit
    ✓ UM único push
    ✓ Atualiza arquivos existentes
    ✓ Cria arquivos novos
    ✓ Pode criar o repositório
    ✓ Pode usar repositório público ou privado
    ✓ Funciona com GitHub Actions

=============================================================
INSTALAÇÃO
=============================================================

Python:

    pip install requests py7zr

Git:

    git --version

=============================================================
TOKEN
=============================================================

Linux / macOS / Termux:

    export MY_GITHUB_TOKEN="github_pat_SEU_TOKEN"

Windows PowerShell:

    $env:MY_GITHUB_TOKEN="github_pat_SEU_TOKEN"

Windows CMD:

    set MY_GITHUB_TOKEN=github_pat_SEU_TOKEN

=============================================================
EXEMPLOS
=============================================================

Pasta:

    python github_uploader.py ./minha_pasta

ZIP:

    python github_uploader.py ./arquivo.zip

7Z:

    python github_uploader.py ./arquivo.7z

Criar repositório:

    python github_uploader.py ./arquivo.zip --create

Criar privado:

    python github_uploader.py ./arquivo.zip --create --private

Enviar para subpasta:

    python github_uploader.py ./arquivo.zip \
        --remote-dir backup

=============================================================
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

import requests


# =============================================================
# CONFIGURAÇÃO PRINCIPAL
# =============================================================

GITHUB_USERNAME = "josieljefferson12"

GITHUB_REPOSITORY = "GitHub-Uploader"

GITHUB_API = "https://api.github.com"

DEFAULT_BRANCH = "main"

TOKEN_ENVIRONMENT = "MY_GITHUB_TOKEN"


# =============================================================
# ARQUIVOS / PASTAS IGNORADOS
# =============================================================

DEFAULT_IGNORES = {
    ".git",
    "__pycache__",
    ".DS_Store",
    "Thumbs.db",
}


# =============================================================
# EXCEÇÃO PERSONALIZADA
# =============================================================

class GitHubUploaderError(Exception):
    pass


# =============================================================
# EXECUTAR GIT
# =============================================================

def run_git(
    *args: str,
    cwd: Path | None = None,
    env: dict | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess:

    command = [
        "git",
        *args,
    ]

    try:

        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
        )

    except FileNotFoundError:

        raise GitHubUploaderError(
            "Git não foi encontrado.\n\n"
            "Instale o Git antes de executar este programa."
        )

    if check and result.returncode != 0:

        raise GitHubUploaderError(
            "Erro executando Git:\n\n"
            f"git {' '.join(args)}\n\n"
            f"{result.stderr.strip()}"
        )

    return result


# =============================================================
# VERIFICAR GIT
# =============================================================

def check_git():

    result = run_git(
        "--version",
        check=False,
    )

    if result.returncode != 0:

        raise GitHubUploaderError(
            "Git não está instalado."
        )

    print(
        f"✓ {result.stdout.strip()}"
    )


# =============================================================
# API GITHUB
# =============================================================

class GitHubAPI:

    def __init__(
        self,
        token: str,
    ):

        self.token = token

        self.session = requests.Session()

        self.session.headers.update(
            {
                "Authorization":
                    f"Bearer {token}",

                "Accept":
                    "application/vnd.github+json",

                "X-GitHub-Api-Version":
                    "2022-11-28",

                "User-Agent":
                    "josieljefferson12-github-uploader",
            }
        )

    # ---------------------------------------------------------
    # REQUISIÇÃO
    # ---------------------------------------------------------

    def request(
        self,
        method: str,
        url: str,
        **kwargs,
    ):

        response = self.session.request(
            method,
            url,
            timeout=120,
            **kwargs,
        )

        if not response.ok:

            try:

                data = response.json()

                message = data.get(
                    "message",
                    response.text,
                )

            except Exception:

                message = response.text

            raise GitHubUploaderError(
                f"GitHub API HTTP "
                f"{response.status_code}:\n"
                f"{message}"
            )

        if response.status_code == 204:

            return None

        return response.json()

    # ---------------------------------------------------------
    # USUÁRIO AUTENTICADO
    # ---------------------------------------------------------

    def get_authenticated_user(self):

        return self.request(
            "GET",
            f"{GITHUB_API}/user",
        )

    # ---------------------------------------------------------
    # VERIFICAR REPOSITÓRIO
    # ---------------------------------------------------------

    def repository_exists(
        self,
        owner: str,
        repository: str,
    ) -> bool:

        response = self.session.get(
            f"{GITHUB_API}/repos/"
            f"{owner}/{repository}",
            timeout=60,
        )

        if response.status_code == 200:

            return True

        if response.status_code == 404:

            return False

        try:

            message = response.json().get(
                "message",
                response.text,
            )

        except Exception:

            message = response.text

        raise GitHubUploaderError(
            f"Erro verificando repositório:\n"
            f"{message}"
        )

    # ---------------------------------------------------------
    # CRIAR REPOSITÓRIO
    # ---------------------------------------------------------

    def create_repository(
        self,
        name: str,
        private: bool,
        description: str,
    ):

        print()
        print(
            f"📦 Criando repositório "
            f"{GITHUB_USERNAME}/{name}..."
        )

        data = {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": False,
        }

        return self.request(
            "POST",
            f"{GITHUB_API}/user/repos",
            json=data,
        )


# =============================================================
# EXTRAIR ZIP
# =============================================================

def extract_zip(
    source: Path,
    destination: Path,
):

    print()
    print(
        f"📦 Extraindo ZIP:"
    )

    print(
        f"   {source}"
    )

    try:

        with zipfile.ZipFile(
            source,
            "r",
        ) as archive:

            archive.extractall(
                destination
            )

    except zipfile.BadZipFile:

        raise GitHubUploaderError(
            "O arquivo ZIP é inválido."
        )


# =============================================================
# EXTRAIR 7Z
# =============================================================

def extract_7z(
    source: Path,
    destination: Path,
):

    try:

        import py7zr

    except ImportError:

        raise GitHubUploaderError(
            "A biblioteca py7zr não está instalada.\n\n"
            "Execute:\n\n"
            "pip install py7zr"
        )

    print()
    print(
        f"📦 Extraindo 7Z:"
    )

    print(
        f"   {source}"
    )

    try:

        with py7zr.SevenZipFile(
            source,
            mode="r",
        ) as archive:

            archive.extractall(
                path=destination
            )

    except Exception as exc:

        raise GitHubUploaderError(
            f"Erro extraindo 7Z:\n"
            f"{exc}"
        )


# =============================================================
# PREPARAR ORIGEM
# =============================================================

def prepare_source(
    source: Path,
):

    if not source.exists():

        raise GitHubUploaderError(
            f"Arquivo/pasta não encontrado:\n"
            f"{source}"
        )

    # ---------------------------------------------------------
    # PASTA
    # ---------------------------------------------------------

    if source.is_dir():

        return source, None

    # ---------------------------------------------------------
    # ARQUIVO
    # ---------------------------------------------------------

    extension = source.suffix.lower()

    temporary = Path(
        tempfile.mkdtemp(
            prefix="github_source_"
        )
    )

    try:

        if extension == ".zip":

            extract_zip(
                source,
                temporary,
            )

            return (
                temporary,
                temporary,
            )

        if extension == ".7z":

            extract_7z(
                source,
                temporary,
            )

            return (
                temporary,
                temporary,
            )

    except Exception:

        shutil.rmtree(
            temporary,
            ignore_errors=True,
        )

        raise

    shutil.rmtree(
        temporary,
        ignore_errors=True,
    )

    raise GitHubUploaderError(
        "Formato não suportado.\n\n"
        "Use:\n"
        "  pasta\n"
        "  .zip\n"
        "  .7z"
    )


# =============================================================
# IGNORE
# =============================================================

def parse_ignores(
    values: list[str],
) -> set[str]:

    ignores = set(
        DEFAULT_IGNORES
    )

    for value in values:

        for item in value.split(","):

            item = item.strip()

            if item:

                ignores.add(item)

    return ignores


def should_ignore(
    path: Path,
    root: Path,
    ignores: set[str],
) -> bool:

    relative = path.relative_to(
        root
    )

    for part in relative.parts:

        if part in ignores:

            return True

    if relative.as_posix() in ignores:

        return True

    return False


# =============================================================
# LISTAR ARQUIVOS
# =============================================================

def iter_files(
    root: Path,
    ignores: set[str],
) -> Iterable[Path]:

    for path in root.rglob("*"):

        if not path.is_file():

            continue

        if should_ignore(
            path,
            root,
            ignores,
        ):

            continue

        yield path


# =============================================================
# AMBIENTE DE AUTENTICAÇÃO GIT
# =============================================================

def create_git_environment(
    token: str,
):

    env = os.environ.copy()

    askpass_dir = Path(
        tempfile.mkdtemp(
            prefix="github_askpass_"
        )
    )

    if os.name == "nt":

        askpass = (
            askpass_dir
            / "askpass.cmd"
        )

        askpass.write_text(
            "@echo off\n"
            "echo %GITHUB_TOKEN%\n",
            encoding="utf-8",
        )

    else:

        askpass = (
            askpass_dir
            / "askpass.sh"
        )

        askpass.write_text(
            "#!/bin/sh\n"
            'printf "%s\\n" "$GITHUB_TOKEN"\n',
            encoding="utf-8",
        )

        askpass.chmod(
            0o700
        )

    env["GITHUB_TOKEN"] = token

    env["GIT_ASKPASS"] = str(
        askpass
    )

    env["GIT_TERMINAL_PROMPT"] = "0"

    return (
        env,
        askpass_dir,
    )


# =============================================================
# URL REMOTA
# =============================================================

def get_remote_url():

    return (
        f"https://github.com/"
        f"{GITHUB_USERNAME}/"
        f"{GITHUB_REPOSITORY}.git"
    )


# =============================================================
# CONFIGURAR GIT
# =============================================================

def configure_git(
    repository: Path,
):

    run_git(
        "config",
        "user.name",
        "github-actions[bot]",
        cwd=repository,
    )

    run_git(
        "config",
        "user.email",
        "41898282+github-actions[bot]"
        "@users.noreply.github.com",
        cwd=repository,
    )


# =============================================================
# CLONAR REPOSITÓRIO
# =============================================================

def clone_repository(
    destination: Path,
    branch: str,
    env: dict,
):

    print()
    print(
        "📥 Clonando repositório..."
    )

    result = run_git(
        "clone",
        "--depth",
        "1",
        "--branch",
        branch,
        get_remote_url(),
        str(destination),
        cwd=destination.parent,
        env=env,
        check=False,
    )

    if result.returncode == 0:

        return

    # ---------------------------------------------------------
    # Tentar clone sem branch
    # ---------------------------------------------------------

    if destination.exists():

        shutil.rmtree(
            destination,
            ignore_errors=True,
        )

    print(
        "⚠️ Branch principal não encontrada."
    )

    print(
        "📥 Tentando clone padrão..."
    )

    result = run_git(
        "clone",
        "--depth",
        "1",
        get_remote_url(),
        str(destination),
        cwd=destination.parent,
        env=env,
        check=False,
    )

    if result.returncode != 0:

        raise GitHubUploaderError(
            "Não foi possível clonar "
            "o repositório.\n\n"
            f"{result.stderr.strip()}"
        )


# =============================================================
# PREPARAR REPOSITÓRIO
# =============================================================

def prepare_repository(
    api: GitHubAPI,
    branch: str,
    create: bool,
    private: bool,
    description: str,
    repository: Path,
    env: dict,
):

    exists = api.repository_exists(
        GITHUB_USERNAME,
        GITHUB_REPOSITORY,
    )

    # ---------------------------------------------------------
    # NÃO EXISTE
    # ---------------------------------------------------------

    if not exists:

        if not create:

            raise GitHubUploaderError(
                f"O repositório "
                f"{GITHUB_USERNAME}/"
                f"{GITHUB_REPOSITORY} "
                "não existe.\n\n"
                "Use --create para criá-lo."
            )

        api.create_repository(
            name=GITHUB_REPOSITORY,
            private=private,
            description=description,
        )

        repository.mkdir(
            parents=True,
            exist_ok=True,
        )

        run_git(
            "init",
            "-b",
            branch,
            cwd=repository,
        )

        run_git(
            "remote",
            "add",
            "origin",
            get_remote_url(),
            cwd=repository,
        )

        print(
            "✓ Repositório criado."
        )

        return

    # ---------------------------------------------------------
    # EXISTE
    # ---------------------------------------------------------

    clone_repository(
        destination=repository,
        branch=branch,
        env=env,
    )

    current = run_git(
        "branch",
        "--show-current",
        cwd=repository,
        check=False,
    )

    current_branch = (
        current.stdout.strip()
    )

    if current_branch != branch:

        result = run_git(
            "checkout",
            branch,
            cwd=repository,
            check=False,
        )

        if result.returncode != 0:

            run_git(
                "checkout",
                "-b",
                branch,
                cwd=repository,
            )


# =============================================================
# COPIAR ARQUIVOS
# =============================================================

def copy_files(
    source: Path,
    repository: Path,
    remote_dir: str,
    ignores: set[str],
):

    if remote_dir:

        destination = (
            repository
            / remote_dir
        )

    else:

        destination = repository

    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    files = list(
        iter_files(
            source,
            ignores,
        )
    )

    total = len(files)

    if total == 0:

        raise GitHubUploaderError(
            "Nenhum arquivo encontrado."
        )

    print()
    print(
        f"📄 {total} arquivo(s) encontrado(s)."
    )

    print()
    print(
        "📂 Copiando arquivos..."
    )

    for number, source_file in enumerate(
        files,
        1,
    ):

        relative = (
            source_file.relative_to(
                source
            )
        )

        target = (
            destination
            / relative
        )

        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source_file,
            target,
        )

        print(
            f"[{number}/{total}] "
            f"✓ {relative.as_posix()}"
        )

    return total


# =============================================================
# STATUS
# =============================================================

def get_status(
    repository: Path,
):

    result = run_git(
        "status",
        "--porcelain",
        cwd=repository,
    )

    return result.stdout.strip()


# =============================================================
# COMMIT
# =============================================================

def create_commit(
    repository: Path,
    message: str,
):

    print()
    print(
        "📦 git add --all"
    )

    run_git(
        "add",
        "--all",
        cwd=repository,
    )

    print(
        "📝 Criando único commit..."
    )

    run_git(
        "commit",
        "-m",
        message,
        cwd=repository,
    )


# =============================================================
# PUSH
# =============================================================

def push(
    repository: Path,
    branch: str,
    env: dict,
):

    print()
    print(
        "🚀 Enviando para GitHub..."
    )

    run_git(
        "push",
        "--set-upstream",
        "origin",
        branch,
        cwd=repository,
        env=env,
    )


# =============================================================
# PROCESSO PRINCIPAL DE UPLOAD
# =============================================================

def upload(
    source: Path,
    branch: str,
    create: bool,
    private: bool,
    description: str,
    remote_dir: str,
    ignores: set[str],
    commit_message: str,
):

    temporary_source = None
    temporary_repository = None
    askpass_dir = None

    token = os.getenv(
        TOKEN_ENVIRONMENT
    )

    if not token:

        raise GitHubUploaderError(
            "A variável de ambiente "
            f"{TOKEN_ENVIRONMENT} não foi encontrada.\n\n"
            "Configure o PAT antes de executar."
        )

    try:

        # -----------------------------------------------------
        # API
        # -----------------------------------------------------

        api = GitHubAPI(
            token
        )

        # -----------------------------------------------------
        # VERIFICAR TOKEN
        # -----------------------------------------------------

        user = api.get_authenticated_user()

        authenticated_user = user.get(
            "login",
            "",
        )

        if (
            authenticated_user.lower()
            != GITHUB_USERNAME.lower()
        ):

            raise GitHubUploaderError(
                "O token pertence ao usuário "
                f"'{authenticated_user}', "
                "mas este script está configurado "
                f"para '{GITHUB_USERNAME}'."
            )

        print()
        print(
            f"✓ Token autenticado como: "
            f"{authenticated_user}"
        )

        # -----------------------------------------------------
        # PREPARAR ORIGEM
        # -----------------------------------------------------

        prepared_source, temporary_source = (
            prepare_source(
                source
            )
        )

        # -----------------------------------------------------
        # GIT AUTH
        # -----------------------------------------------------

        git_env, askpass_dir = (
            create_git_environment(
                token
            )
        )

        # -----------------------------------------------------
        # REPOSITÓRIO TEMPORÁRIO
        # -----------------------------------------------------

        temporary_repository = Path(
            tempfile.mkdtemp(
                prefix="github_repository_"
            )
        )

        repository = (
            temporary_repository
            / "repo"
        )

        # -----------------------------------------------------
        # PREPARAR REPOSITÓRIO
        # -----------------------------------------------------

        prepare_repository(
            api=api,
            branch=branch,
            create=create,
            private=private,
            description=description,
            repository=repository,
            env=git_env,
        )

        # -----------------------------------------------------
        # CONFIGURAR GIT
        # -----------------------------------------------------

        configure_git(
            repository
        )

        # -----------------------------------------------------
        # COPIAR ARQUIVOS
        # -----------------------------------------------------

        total = copy_files(
            source=prepared_source,
            repository=repository,
            remote_dir=remote_dir,
            ignores=ignores,
        )

        # -----------------------------------------------------
        # VERIFICAR ALTERAÇÕES
        # -----------------------------------------------------

        status = get_status(
            repository
        )

        if not status:

            print()
            print(
                "ℹ️ Nenhuma alteração detectada."
            )

            return

        # -----------------------------------------------------
        # COMMIT
        # -----------------------------------------------------

        create_commit(
            repository=repository,
            message=commit_message,
        )

        # -----------------------------------------------------
        # PUSH
        # -----------------------------------------------------

        push(
            repository=repository,
            branch=branch,
            env=git_env,
        )

        # -----------------------------------------------------
        # SUCESSO
        # -----------------------------------------------------

        print()
        print(
            "=================================================="
        )

        print(
            "✅ UPLOAD CONCLUÍDO COM SUCESSO"
        )

        print(
            "=================================================="
        )

        print()
        print(
            f"👤 Usuário: "
            f"{GITHUB_USERNAME}"
        )

        print(
            f"📦 Repositório: "
            f"{GITHUB_REPOSITORY}"
        )

        print(
            f"🌿 Branch: "
            f"{branch}"
        )

        print(
            f"📄 Arquivos: "
            f"{total}"
        )

        print(
            "📝 Commits: 1"
        )

        print(
            "🚀 Push: 1"
        )

        print()
        print(
            f"https://github.com/"
            f"{GITHUB_USERNAME}/"
            f"{GITHUB_REPOSITORY}"
        )

    finally:

        # -----------------------------------------------------
        # LIMPAR ORIGEM EXTRAÍDA
        # -----------------------------------------------------

        if temporary_source:

            shutil.rmtree(
                temporary_source,
                ignore_errors=True,
            )

        # -----------------------------------------------------
        # LIMPAR REPOSITÓRIO TEMPORÁRIO
        # -----------------------------------------------------

        if temporary_repository:

            shutil.rmtree(
                temporary_repository,
                ignore_errors=True,
            )

        # -----------------------------------------------------
        # LIMPAR ASKPASS
        # -----------------------------------------------------

        if askpass_dir:

            shutil.rmtree(
                askpass_dir,
                ignore_errors=True,
            )


# =============================================================
# ARGUMENTOS
# =============================================================

def build_parser():

    parser = argparse.ArgumentParser(
        description=(
            "Upload de pasta, ZIP ou 7Z "
            "para josieljefferson12/"
            "GitHub-Uploader."
        )
    )

    parser.add_argument(
        "source",
        help=(
            "Pasta, arquivo .zip "
            "ou arquivo .7z."
        ),
    )

    parser.add_argument(
        "--branch",
        default=DEFAULT_BRANCH,
        help=(
            "Branch de destino. "
            "Padrão: main."
        ),
    )

    parser.add_argument(
        "--create",
        action="store_true",
        help=(
            "Cria o repositório caso "
            "ele não exista."
        ),
    )

    parser.add_argument(
        "--private",
        action="store_true",
        help=(
            "Cria o repositório como privado."
        ),
    )

    parser.add_argument(
        "--description",
        default=(
            "Upload automático de arquivos "
            "via GitHub Uploader"
        ),
        help=(
            "Descrição do repositório."
        ),
    )

    parser.add_argument(
        "--remote-dir",
        default="",
        help=(
            "Subpasta no repositório."
        ),
    )

    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help=(
            "Arquivo/pasta a ignorar. "
            "Pode ser repetido."
        ),
    )

    parser.add_argument(
        "--commit",
        default=(
            "Upload automático "
            "de arquivos"
        ),
        help=(
            "Mensagem do commit."
        ),
    )

    return parser


# =============================================================
# MAIN
# =============================================================

def main():

    parser = build_parser()

    args = parser.parse_args()

    try:

        print()
        print(
            "=================================================="
        )

        print(
            "             GITHUB UPLOADER"
        )

        print(
            "=================================================="
        )

        print()
        print(
            f"👤 Usuário: "
            f"{GITHUB_USERNAME}"
        )

        print(
            f"📦 Repositório: "
            f"{GITHUB_REPOSITORY}"
        )

        print()

        # -----------------------------------------------------
        # GIT
        # -----------------------------------------------------

        check_git()

        # -----------------------------------------------------
        # ORIGEM
        # -----------------------------------------------------

        source = Path(
            args.source
        ).expanduser().resolve()

        print(
            f"📁 Origem:"
        )

        print(
            f"   {source}"
        )

        # -----------------------------------------------------
        # IGNORE
        # -----------------------------------------------------

        ignores = parse_ignores(
            args.ignore
        )

        # -----------------------------------------------------
        # UPLOAD
        # -----------------------------------------------------

        upload(
            source=source,
            branch=args.branch,
            create=args.create,
            private=args.private,
            description=args.description,
            remote_dir=args.remote_dir,
            ignores=ignores,
            commit_message=args.commit,
        )

    except KeyboardInterrupt:

        print()
        print(
            "⚠️ Operação cancelada."
        )

        sys.exit(130)

    except GitHubUploaderError as exc:

        print()
        print(
            "=================================================="
        )

        print(
            "❌ ERRO"
        )

        print(
            "=================================================="
        )

        print()
        print(
            str(exc)
        )

        sys.exit(1)

    except requests.RequestException as exc:

        print()
        print(
            "❌ Erro de comunicação com GitHub:"
        )

        print(
            str(exc)
        )

        sys.exit(1)

    except Exception as exc:

        print()
        print(
            "❌ ERRO INESPERADO:"
        )

        print(
            repr(exc)
        )

        sys.exit(1)


# =============================================================
# EXECUTAR
# =============================================================

if __name__ == "__main__":

    main()
