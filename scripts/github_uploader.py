#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=============================================================
                 🚀 GITHUB UPLOADER
=============================================================

Uploader completo para GitHub.

O proprietário do repositório NÃO é fixado no código.

O usuário é descoberto automaticamente através do:

    MY_GITHUB_TOKEN

Funcionalidades:

    ✓ --repo
    ✓ --create
    ✓ --private
    ✓ --branch
    ✓ --remote-dir
    ✓ --commit
    ✓ --description
    ✓ --ignore
    ✓ Pasta
    ✓ ZIP
    ✓ 7Z
    ✓ Repositório existente
    ✓ Criação automática de repositório
    ✓ Público / privado
    ✓ PAT MY_GITHUB_TOKEN
    ✓ Validação do token
    ✓ Validação das permissões
    ✓ Atualização de arquivos existentes
    ✓ Criação de arquivos novos
    ✓ Preserva estrutura de diretórios
    ✓ 1 commit
    ✓ 1 push

Exemplo:

    python github_uploader.py uploads/projeto.zip \
        --repo meu-projeto \
        --create \
        --branch main \
        --commit "Upload automático"

Repositório privado:

    python github_uploader.py uploads/projeto.zip \
        --repo meu-projeto \
        --create \
        --private

Subpasta:

    python github_uploader.py uploads/projeto.zip \
        --repo meu-projeto \
        --remote-dir backup

Descrição:

    python github_uploader.py uploads/projeto.zip \
        --repo meu-projeto \
        --create \
        --description "Meu projeto"

Ignorar:

    python github_uploader.py uploads/projeto.zip \
        --repo meu-projeto \
        --ignore .git \
        --ignore __pycache__

Token:

    MY_GITHUB_TOKEN

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
# CONFIGURAÇÃO
# =============================================================

GITHUB_API = "https://api.github.com"

DEFAULT_BRANCH = "main"

TOKEN_ENVIRONMENT = "MY_GITHUB_TOKEN"

DEFAULT_DESCRIPTION = (
    "Upload automático via GitHub Uploader"
)


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
# EXCEÇÃO
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
            "Instale o Git antes de executar o uploader."
        )

    if check and result.returncode != 0:

        command_text = " ".join(
            args
        )

        error = result.stderr.strip()

        raise GitHubUploaderError(
            "Erro executando Git:\n\n"
            f"git {command_text}\n\n"
            f"{error}"
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
                    "GitHub-Uploader",
            }
        )

    # =========================================================
    # REQUISIÇÃO
    # =========================================================

    def request(
        self,
        method: str,
        url: str,
        **kwargs,
    ):

        try:

            response = self.session.request(
                method,
                url,
                timeout=120,
                **kwargs,
            )

        except requests.RequestException as exc:

            raise GitHubUploaderError(
                "Erro de comunicação com GitHub:\n"
                f"{exc}"
            )

        if not response.ok:

            try:

                data = response.json()

                message = data.get(
                    "message",
                    response.text,
                )

                documentation = data.get(
                    "documentation_url"
                )

            except Exception:

                message = response.text
                documentation = None

            error = (
                f"GitHub API HTTP "
                f"{response.status_code}:\n"
                f"{message}"
            )

            if documentation:

                error += (
                    "\n\nDocumentação:\n"
                    f"{documentation}"
                )

            raise GitHubUploaderError(
                error
            )

        if response.status_code == 204:

            return None

        try:

            return response.json()

        except ValueError:

            return None

    # =========================================================
    # USUÁRIO AUTENTICADO
    # =========================================================

    def get_authenticated_user(self):

        return self.request(
            "GET",
            f"{GITHUB_API}/user",
        )

    # =========================================================
    # VERIFICAR REPOSITÓRIO
    # =========================================================

    def repository_exists(
        self,
        owner: str,
        repository: str,
    ) -> bool:

        try:

            response = self.session.get(
                f"{GITHUB_API}/repos/"
                f"{owner}/{repository}",
                timeout=60,
            )

        except requests.RequestException as exc:

            raise GitHubUploaderError(
                "Erro consultando o repositório:\n"
                f"{exc}"
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
            "Erro verificando repositório:\n"
            f"{message}"
        )

    # =========================================================
    # CRIAR REPOSITÓRIO
    # =========================================================

    def create_repository(
        self,
        owner: str,
        name: str,
        private: bool,
        description: str,
    ):

        print()
        print(
            "📦 Criando repositório:"
        )

        print(
            f"   {owner}/{name}"
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

    # =========================================================
    # PERMISSÕES DO TOKEN
    # =========================================================

    def check_token_permissions(self):

        print(
            "🔐 Verificando permissões do token..."
        )

        try:

            response = self.session.get(
                f"{GITHUB_API}/user",
                timeout=60,
            )

        except requests.RequestException as exc:

            raise GitHubUploaderError(
                "Não foi possível validar "
                "as permissões do token:\n"
                f"{exc}"
            )

        if response.status_code != 200:

            raise GitHubUploaderError(
                "O PAT não conseguiu acessar "
                "a API do GitHub.\n\n"
                "Verifique se MY_GITHUB_TOKEN "
                "é válido."
            )

        scopes = (
            response.headers.get(
                "X-OAuth-Scopes",
                ""
            )
        )

        scopes = {
            scope.strip()
            for scope in scopes.split(",")
            if scope.strip()
        }

        # -----------------------------------------------------
        # Fine-grained PAT
        # -----------------------------------------------------

        if not scopes:

            print(
                "ℹ️ PAT fine-grained detectado "
                "ou escopos não expostos."
            )

            print(
                "✓ A autenticação com a API foi realizada."
            )

            return

        print(
            "✓ Escopos detectados:"
        )

        for scope in sorted(scopes):

            print(
                f"   • {scope}"
            )

        # -----------------------------------------------------
        # PAT clássico
        # -----------------------------------------------------

        required = {
            "repo",
        }

        missing = required - scopes

        if missing:

            raise GitHubUploaderError(
                "O token não possui o escopo "
                "necessário para este uploader.\n\n"
                "Escopo necessário:\n"
                "  repo\n\n"
                "Escopos ausentes:\n"
                + "\n".join(
                    f"  • {item}"
                    for item in sorted(missing)
                )
            )

        print(
            "✓ Permissões básicas do PAT verificadas."
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
        "📦 Extraindo ZIP:"
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
            "Instale com:\n\n"
            "pip install py7zr"
        )

    print()
    print(
        "📦 Extraindo 7Z:"
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
            "Erro extraindo 7Z:\n"
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
            "Arquivo/pasta não encontrado:\n"
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
        "Formatos aceitos:\n"
        "  • pasta\n"
        "  • .zip\n"
        "  • .7z"
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
# AUTENTICAÇÃO DO GIT
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
# URL DO REPOSITÓRIO
# =============================================================

def get_remote_url(
    owner: str,
    repository: str,
):

    return (
        f"https://github.com/"
        f"{owner}/"
        f"{repository}.git"
    )


# =============================================================
# CONFIGURAR GIT
# =============================================================

def configure_git(
    repository: Path,
    owner: str,
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

    run_git(
        "config",
        "remote.origin.url",
        get_remote_url(
            owner,
            repository.name,
        ),
        cwd=repository,
    )


# =============================================================
# CLONAR REPOSITÓRIO
# =============================================================

def clone_repository(
    destination: Path,
    owner: str,
    repository: str,
    branch: str,
    env: dict,
):

    remote_url = get_remote_url(
        owner,
        repository,
    )

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
        remote_url,
        str(destination),
        cwd=destination.parent,
        env=env,
        check=False,
    )

    if result.returncode == 0:

        return

    # ---------------------------------------------------------
    # Remover tentativa anterior
    # ---------------------------------------------------------

    if destination.exists():

        shutil.rmtree(
            destination,
            ignore_errors=True,
        )

    print(
        "⚠️ Branch informada não pôde "
        "ser clonada diretamente."
    )

    print(
        "📥 Tentando clone padrão..."
    )

    result = run_git(
        "clone",
        "--depth",
        "1",
        remote_url,
        str(destination),
        cwd=destination.parent,
        env=env,
        check=False,
    )

    if result.returncode != 0:

        error = result.stderr.strip()

        raise GitHubUploaderError(
            "Não foi possível clonar "
            "o repositório.\n\n"
            f"{error}"
        )


# =============================================================
# PREPARAR REPOSITÓRIO
# =============================================================

def prepare_repository(
    api: GitHubAPI,
    owner: str,
    repository_name: str,
    branch: str,
    create: bool,
    private: bool,
    description: str,
    repository_path: Path,
    env: dict,
):

    exists = api.repository_exists(
        owner,
        repository_name,
    )

    # =========================================================
    # REPOSITÓRIO NÃO EXISTE
    # =========================================================

    if not exists:

        if not create:

            raise GitHubUploaderError(
                f"O repositório "
                f"{owner}/{repository_name} "
                "não existe.\n\n"
                "Para criá-lo automaticamente, "
                "execute novamente usando:\n\n"
                "    --create"
            )

        api.create_repository(
            owner=owner,
            name=repository_name,
            private=private,
            description=description,
        )

        repository_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        run_git(
            "init",
            "-b",
            branch,
            cwd=repository_path,
        )

        run_git(
            "remote",
            "add",
            "origin",
            get_remote_url(
                owner,
                repository_name,
            ),
            cwd=repository_path,
        )

        print(
            "✓ Repositório criado."
        )

        return

    # =========================================================
    # REPOSITÓRIO EXISTE
    # =========================================================

    print()
    print(
        f"✓ Repositório encontrado:"
    )

    print(
        f"   {owner}/{repository_name}"
    )

    clone_repository(
        destination=repository_path,
        owner=owner,
        repository=repository_name,
        branch=branch,
        env=env,
    )

    # ---------------------------------------------------------
    # Garantir remote correto
    # ---------------------------------------------------------

    remote_url = get_remote_url(
        owner,
        repository_name,
    )

    run_git(
        "remote",
        "set-url",
        "origin",
        remote_url,
        cwd=repository_path,
    )

    # ---------------------------------------------------------
    # Verificar branch atual
    # ---------------------------------------------------------

    current = run_git(
        "branch",
        "--show-current",
        cwd=repository_path,
        check=False,
    )

    current_branch = (
        current.stdout.strip()
    )

    if current_branch != branch:

        checkout = run_git(
            "checkout",
            branch,
            cwd=repository_path,
            check=False,
        )

        if checkout.returncode != 0:

            run_git(
                "checkout",
                "-b",
                branch,
                cwd=repository_path,
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
            "Nenhum arquivo encontrado "
            "na origem."
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
        "📦 Executando git add --all..."
    )

    run_git(
        "add",
        "--all",
        cwd=repository,
    )

    print(
        "📝 Criando UM único commit..."
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
        "🚀 Executando UM único push..."
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
# UPLOAD
# =============================================================

def upload(
    source: Path,
    owner: str,
    repository_name: str,
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
            f"{TOKEN_ENVIRONMENT} "
            "não foi encontrada.\n\n"
            "Configure o Secret:\n\n"
            "MY_GITHUB_TOKEN"
        )

    try:

        # =====================================================
        # API
        # =====================================================

        api = GitHubAPI(
            token
        )

        # =====================================================
        # VALIDAR TOKEN
        # =====================================================

        print(
            "🔐 Validando token..."
        )

        user = (
            api.get_authenticated_user()
        )

        authenticated_user = (
            user.get(
                "login",
                "",
            )
        )

        if not authenticated_user:

            raise GitHubUploaderError(
                "O GitHub não retornou "
                "o usuário autenticado."
            )

        # =====================================================
        # IMPORTANTE:
        # O OWNER VEM DO TOKEN.
        # =====================================================

        owner = authenticated_user

        print(
            f"✓ Token autenticado como:"
        )

        print(
            f"   {owner}"
        )

        # =====================================================
        # VALIDAR PERMISSÕES
        # =====================================================

        api.check_token_permissions()

        # =====================================================
        # PREPARAR ORIGEM
        # =====================================================

        prepared_source, temporary_source = (
            prepare_source(
                source
            )
        )

        # =====================================================
        # AUTENTICAÇÃO GIT
        # =====================================================

        git_env, askpass_dir = (
            create_git_environment(
                token
            )
        )

        # =====================================================
        # REPOSITÓRIO TEMPORÁRIO
        # =====================================================

        temporary_repository = Path(
            tempfile.mkdtemp(
                prefix="github_repository_"
            )
        )

        repository_path = (
            temporary_repository
            / "repo"
        )

        # =====================================================
        # PREPARAR REPOSITÓRIO
        # =====================================================

        prepare_repository(
            api=api,
            owner=owner,
            repository_name=repository_name,
            branch=branch,
            create=create,
            private=private,
            description=description,
            repository_path=repository_path,
            env=git_env,
        )

        # =====================================================
        # CONFIGURAR GIT
        # =====================================================

        configure_git(
            repository_path,
            owner,
        )

        # =====================================================
        # COPIAR
        # =====================================================

        total = copy_files(
            source=prepared_source,
            repository=repository_path,
            remote_dir=remote_dir,
            ignores=ignores,
        )

        # =====================================================
        # STATUS
        # =====================================================

        status = get_status(
            repository_path
        )

        if not status:

            print()
            print(
                "ℹ️ Nenhuma alteração detectada."
            )

            print(
                "ℹ️ Nenhum commit foi criado."
            )

            print(
                "ℹ️ Nenhum push foi realizado."
            )

            return

        # =====================================================
        # UM COMMIT
        # =====================================================

        create_commit(
            repository=repository_path,
            message=commit_message,
        )

        # =====================================================
        # UM PUSH
        # =====================================================

        push(
            repository=repository_path,
            branch=branch,
            env=git_env,
        )

        # =====================================================
        # SUCESSO
        # =====================================================

        print()
        print(
            "=================================================="
        )

        print(
            "       ✅ UPLOAD CONCLUÍDO COM SUCESSO"
        )

        print(
            "=================================================="
        )

        print()
        print(
            f"👤 Proprietário: {owner}"
        )

        print(
            f"📦 Repositório: "
            f"{repository_name}"
        )

        print(
            f"🌿 Branch: {branch}"
        )

        print(
            f"📄 Arquivos processados: "
            f"{total}"
        )

        print(
            "📝 Commits: 1"
        )

        print(
            "🚀 Pushes: 1"
        )

        if remote_dir:

            print(
                f"📂 Subpasta: {remote_dir}"
            )

        else:

            print(
                "📂 Subpasta: raiz"
            )

        print()

        print(
            f"https://github.com/"
            f"{owner}/"
            f"{repository_name}"
        )

    finally:

        # -----------------------------------------------------
        # LIMPAR ORIGEM TEMPORÁRIA
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
            "para um repositório GitHub."
        )
    )

    # ---------------------------------------------------------
    # SOURCE
    # ---------------------------------------------------------

    parser.add_argument(
        "source",
        help=(
            "Pasta, arquivo .zip "
            "ou arquivo .7z."
        ),
    )

    # ---------------------------------------------------------
    # REPOSITORY
    # ---------------------------------------------------------

    parser.add_argument(
        "--repo",
        required=True,
        help=(
            "Nome do repositório de destino."
        ),
    )

    # ---------------------------------------------------------
    # BRANCH
    # ---------------------------------------------------------

    parser.add_argument(
        "--branch",
        default=DEFAULT_BRANCH,
        help=(
            "Branch de destino. "
            "Padrão: main."
        ),
    )

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------

    parser.add_argument(
        "--create",
        action="store_true",
        help=(
            "Cria o repositório caso "
            "ele não exista."
        ),
    )

    # ---------------------------------------------------------
    # PRIVATE
    # ---------------------------------------------------------

    parser.add_argument(
        "--private",
        action="store_true",
        help=(
            "Cria o repositório como privado."
        ),
    )

    # ---------------------------------------------------------
    # DESCRIPTION
    # ---------------------------------------------------------

    parser.add_argument(
        "--description",
        default=DEFAULT_DESCRIPTION,
        help=(
            "Descrição do repositório."
        ),
    )

    # ---------------------------------------------------------
    # REMOTE DIR
    # ---------------------------------------------------------

    parser.add_argument(
        "--remote-dir",
        default="",
        help=(
            "Subpasta de destino dentro "
            "do repositório."
        ),
    )

    # ---------------------------------------------------------
    # IGNORE
    # ---------------------------------------------------------

    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help=(
            "Arquivo/pasta a ignorar. "
            "Pode ser usado várias vezes."
        ),
    )

    # ---------------------------------------------------------
    # COMMIT
    # ---------------------------------------------------------

    parser.add_argument(
        "--commit",
        default="Upload automático",
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
            "             🚀 GITHUB UPLOADER"
        )

        print(
            "=================================================="
        )

        print()

        print(
            "📦 Repositório:"
        )

        print(
            f"   {args.repo}"
        )

        print()

        print(
            "📁 Origem:"
        )

        print(
            f"   {args.source}"
        )

        print()

        print(
            "🌿 Branch:"
        )

        print(
            f"   {args.branch}"
        )

        print()

        print(
            "🆕 Criar:"
        )

        print(
            "   "
            + (
                "sim"
                if args.create
                else "não"
            )
        )

        print()

        print(
            "🔒 Privado:"
        )

        print(
            "   "
            + (
                "sim"
                if args.private
                else "não"
            )
        )

        print()

        print(
            "📂 Subpasta:"
        )

        print(
            "   "
            + (
                args.remote_dir
                if args.remote_dir
                else "(raiz)"
            )
        )

        print()

        print(
            "📝 Commit:"
        )

        print(
            f"   {args.commit}"
        )

        print()

        # =====================================================
        # GIT
        # =====================================================

        check_git()

        # =====================================================
        # TOKEN
        # =====================================================

        token = os.getenv(
            TOKEN_ENVIRONMENT
        )

        if not token:

            raise GitHubUploaderError(
                "MY_GITHUB_TOKEN não encontrado."
            )

        # =====================================================
        # ORIGEM
        # =====================================================

        source = Path(
            args.source
        ).expanduser().resolve()

        # =====================================================
        # IGNORE
        # =====================================================

        ignores = parse_ignores(
            args.ignore
        )

        # =====================================================
        # UPLOAD
        # =====================================================

        upload(
            source=source,

            # Será substituído automaticamente
            # pelo usuário autenticado pelo PAT.
            owner="",

            repository_name=args.repo,

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
