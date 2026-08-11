#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=============================================================
                 GITHUB UPLOADER
=============================================================

Upload de arquivos, pastas, ZIP e 7Z para qualquer
repositório do GitHub.

Usuário:
    josieljefferson12

Token:
    MY_GITHUB_TOKEN

=============================================================
RECURSOS
=============================================================

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
✓ Validação de permissões
✓ Atualização de arquivos existentes
✓ Criação de arquivos novos
✓ Preserva estrutura de diretórios
✓ 1 único commit
✓ 1 único push

=============================================================
EXEMPLOS
=============================================================

Pasta:

    python github_uploader.py uploads/meu_projeto \
        --repo meu-projeto

ZIP:

    python github_uploader.py uploads/projeto.zip \
        --repo meu-projeto

7Z:

    python github_uploader.py uploads/projeto.7z \
        --repo meu-projeto

Criar repositório:

    python github_uploader.py uploads/projeto.zip \
        --repo meu-projeto \
        --create

Criar privado:

    python github_uploader.py uploads/projeto.zip \
        --repo meu-projeto \
        --create \
        --private

Subpasta:

    python github_uploader.py uploads/projeto.zip \
        --repo meu-projeto \
        --remote-dir backup

Commit personalizado:

    python github_uploader.py uploads/projeto.zip \
        --repo meu-projeto \
        --commit "Atualização automática"

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

GITHUB_USERNAME = "josieljefferson12"

GITHUB_API = "https://api.github.com"

DEFAULT_BRANCH = "main"

TOKEN_ENVIRONMENT = "MY_GITHUB_TOKEN"


# =============================================================
# IGNORADOS PADRÃO
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
    """Erro controlado do GitHub Uploader."""


# =============================================================
# EXECUTAR GIT
# =============================================================

def run_git(
    *args: str,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:

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

    except FileNotFoundError as exc:

        raise GitHubUploaderError(
            "Git não foi encontrado. "
            "Instale o Git antes de executar o programa."
        ) from exc

    if check and result.returncode != 0:

        command_text = " ".join(
            args
        )

        raise GitHubUploaderError(
            "Erro executando Git:\n\n"
            f"git {command_text}\n\n"
            f"{result.stderr.strip()}"
        )

    return result


# =============================================================
# VERIFICAR GIT
# =============================================================

def check_git() -> None:

    result = run_git(
        "--version",
        check=False,
    )

    if result.returncode != 0:

        raise GitHubUploaderError(
            "Git não está instalado ou não está disponível."
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
    ) -> None:

        self.token = token

        self.session = requests.Session()

        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": (
                    "josieljefferson12-github-uploader"
                ),
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
                "Erro de comunicação com o GitHub:\n"
                f"{exc}"
            ) from exc

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
    # PERMISSÕES / TOKEN
    # =========================================================

    def validate_token(
        self,
    ):

        user = self.get_authenticated_user()

        login = user.get(
            "login",
            "",
        )

        if not login:

            raise GitHubUploaderError(
                "O GitHub não retornou o usuário "
                "associado ao token."
            )

        if login.lower() != GITHUB_USERNAME.lower():

            raise GitHubUploaderError(
                "O token pertence ao usuário "
                f"'{login}', mas este uploader está "
                f"configurado para '{GITHUB_USERNAME}'."
            )

        # -----------------------------------------------------
        # Verificar escopos/permissões retornados pelo GitHub
        # -----------------------------------------------------

        response = self.session.get(
            f"{GITHUB_API}/user",
            timeout=60,
        )

        scopes = {
            scope.strip()
            for scope in response.headers.get(
                "X-OAuth-Scopes",
                ""
            ).split(",")
            if scope.strip()
        }

        permissions = {
            key.lower(): value
            for key, value in (
                response.headers.items()
            )
            if key.lower().startswith(
                "x-oauth-scopes"
            )
        }

        # O GitHub pode não informar scopes para fine-grained PAT.
        # Nesse caso, a validação real ocorrerá durante as operações.

        return {
            "login": login,
            "scopes": scopes,
            "permissions_headers": permissions,
        }

    # =========================================================
    # REPOSITÓRIO
    # =========================================================

    def repository_exists(
        self,
        owner: str,
        repository: str,
    ) -> bool:

        url = (
            f"{GITHUB_API}/repos/"
            f"{owner}/{repository}"
        )

        try:

            response = self.session.get(
                url,
                timeout=60,
            )

        except requests.RequestException as exc:

            raise GitHubUploaderError(
                "Erro verificando o repositório:\n"
                f"{exc}"
            ) from exc

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
            "Erro verificando o repositório:\n"
            f"HTTP {response.status_code}: "
            f"{message}"
        )

    # =========================================================
    # CRIAR REPOSITÓRIO
    # =========================================================

    def create_repository(
        self,
        name: str,
        private: bool,
        description: str,
    ):

        print()
        print(
            "📦 Criando repositório:"
        )

        print(
            f"   {GITHUB_USERNAME}/{name}"
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
# VALIDAR NOME DO REPOSITÓRIO
# =============================================================

def validate_repository_name(
    repository: str,
) -> str:

    repository = repository.strip()

    if not repository:

        raise GitHubUploaderError(
            "O nome do repositório não pode estar vazio."
        )

    if repository in {
        ".",
        "..",
    }:

        raise GitHubUploaderError(
            "Nome de repositório inválido."
        )

    invalid_characters = {
        "/",
        "\\",
        ":",
        "*",
        "?",
        '"',
        "<",
        ">",
        "|",
        "\n",
        "\r",
    }

    for character in invalid_characters:

        if character in repository:

            raise GitHubUploaderError(
                "Nome de repositório inválido:\n"
                f"{repository}"
            )

    return repository


# =============================================================
# VALIDAR BRANCH
# =============================================================

def validate_branch(
    branch: str,
) -> str:

    branch = branch.strip()

    if not branch:

        raise GitHubUploaderError(
            "A branch não pode estar vazia."
        )

    return branch


# =============================================================
# VALIDAR REMOTE DIR
# =============================================================

def validate_remote_dir(
    remote_dir: str,
) -> str:

    remote_dir = remote_dir.strip()

    if not remote_dir:

        return ""

    path = Path(
        remote_dir
    )

    if path.is_absolute():

        raise GitHubUploaderError(
            "A subpasta de destino não pode ser "
            "um caminho absoluto."
        )

    normalized = remote_dir.replace(
        "\\",
        "/",
    ).strip("/")

    if normalized in {
        "",
        ".",
    }:

        return ""

    if ".." in Path(
        normalized
    ).parts:

        raise GitHubUploaderError(
            "A subpasta de destino não pode "
            "conter '..'."
        )

    return normalized


# =============================================================
# EXTRAIR ZIP
# =============================================================

def extract_zip(
    source: Path,
    destination: Path,
) -> None:

    print()
    print(
        f"📦 Extraindo ZIP: {source.name}"
    )

    try:

        with zipfile.ZipFile(
            source,
            "r",
        ) as archive:

            # -------------------------------------------------
            # Proteção contra Zip Slip
            # -------------------------------------------------

            destination_resolved = (
                destination.resolve()
            )

            for member in archive.infolist():

                member_path = (
                    destination
                    / member.filename
                ).resolve()

                if not str(
                    member_path
                ).startswith(
                    str(destination_resolved)
                ):

                    raise GitHubUploaderError(
                        "O ZIP contém um caminho inválido "
                        "que sairia da pasta de extração."
                    )

            archive.extractall(
                destination
            )

    except zipfile.BadZipFile as exc:

        raise GitHubUploaderError(
            "O arquivo ZIP é inválido."
        ) from exc


# =============================================================
# EXTRAIR 7Z
# =============================================================

def extract_7z(
    source: Path,
    destination: Path,
) -> None:

    try:

        import py7zr

    except ImportError as exc:

        raise GitHubUploaderError(
            "A biblioteca py7zr não está instalada.\n\n"
            "Execute:\n\n"
            "pip install py7zr"
        ) from exc

    print()
    print(
        f"📦 Extraindo 7Z: {source.name}"
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
            "Erro extraindo o arquivo 7Z:\n"
            f"{exc}"
        ) from exc


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

    if source.is_dir():

        return source, None

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

            return temporary, temporary

        if extension == ".7z":

            extract_7z(
                source,
                temporary,
            )

            return temporary, temporary

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
        "• pasta\n"
        "• .zip\n"
        "• .7z"
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
# ITERAR ARQUIVOS
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
# GIT AUTHENTICATION
# =============================================================

def create_git_environment(
    token: str,
):

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

    env = os.environ.copy()

    env["GITHUB_TOKEN"] = token

    env["GIT_ASKPASS"] = str(
        askpass
    )

    env["GIT_TERMINAL_PROMPT"] = "0"

    return env, askpass_dir


# =============================================================
# URL DO REPOSITÓRIO
# =============================================================

def get_remote_url(
    repository_name: str,
) -> str:

    return (
        "https://github.com/"
        f"{GITHUB_USERNAME}/"
        f"{repository_name}.git"
    )


# =============================================================
# CONFIGURAR GIT
# =============================================================

def configure_git(
    repository: Path,
) -> None:

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
    repository_name: str,
    destination: Path,
    branch: str,
    env: dict[str, str],
) -> None:

    remote_url = get_remote_url(
        repository_name
    )

    print()
    print(
        "📥 Clonando repositório:"
    )

    print(
        f"   {GITHUB_USERNAME}/{repository_name}"
    )

    # ---------------------------------------------------------
    # Tentar branch informada
    # ---------------------------------------------------------

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
    # Limpar tentativa
    # ---------------------------------------------------------

    if destination.exists():

        shutil.rmtree(
            destination,
            ignore_errors=True,
        )

    # ---------------------------------------------------------
    # Clone padrão
    # ---------------------------------------------------------

    print(
        "⚠️ Não foi possível clonar "
        f"diretamente a branch '{branch}'."
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

        raise GitHubUploaderError(
            "Não foi possível clonar o repositório.\n\n"
            f"{result.stderr.strip()}"
        )


# =============================================================
# PREPARAR REPOSITÓRIO
# =============================================================

def prepare_repository(
    api: GitHubAPI,
    repository_name: str,
    branch: str,
    create: bool,
    private: bool,
    description: str,
    repository: Path,
    env: dict[str, str],
) -> None:

    exists = api.repository_exists(
        GITHUB_USERNAME,
        repository_name,
    )

    # =========================================================
    # REPOSITÓRIO NÃO EXISTE
    # =========================================================

    if not exists:

        if not create:

            raise GitHubUploaderError(
                f"O repositório "
                f"{GITHUB_USERNAME}/{repository_name} "
                "não existe.\n\n"
                "Marque 'Criar repositório' "
                "ou use --create."
            )

        api.create_repository(
            name=repository_name,
            private=private,
            description=description,
        )

        print()
        print(
            "✓ Repositório criado."
        )

        # -----------------------------------------------------
        # Criar Git local
        # -----------------------------------------------------

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
            get_remote_url(
                repository_name
            ),
            cwd=repository,
        )

        configure_git(
            repository
        )

        return

    # =========================================================
    # REPOSITÓRIO EXISTE
    # =========================================================

    clone_repository(
        repository_name=repository_name,
        destination=repository,
        branch=branch,
        env=env,
    )

    configure_git(
        repository
    )

    # ---------------------------------------------------------
    # Verificar branch
    # ---------------------------------------------------------

    current = run_git(
        "branch",
        "--show-current",
        cwd=repository,
        check=False,
    )

    current_branch = (
        current.stdout.strip()
    )

    if current_branch == branch:

        return

    # ---------------------------------------------------------
    # Tentar checkout
    # ---------------------------------------------------------

    checkout = run_git(
        "checkout",
        branch,
        cwd=repository,
        check=False,
    )

    if checkout.returncode == 0:

        return

    # ---------------------------------------------------------
    # Criar branch local baseada na atual
    # ---------------------------------------------------------

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
) -> int:

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
            "Nenhum arquivo encontrado na origem."
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

        relative = source_file.relative_to(
            source
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
# GIT STATUS
# =============================================================

def get_status(
    repository: Path,
) -> str:

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
) -> None:

    print()
    print(
        "📦 Adicionando alterações..."
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
    env: dict[str, str],
) -> None:

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
# UPLOAD PRINCIPAL
# =============================================================

def upload(
    source: Path,
    repository_name: str,
    branch: str,
    create: bool,
    private: bool,
    description: str,
    remote_dir: str,
    ignores: set[str],
    commit_message: str,
) -> None:

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
            "No GitHub Actions, configure o Secret:\n"
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

        print()
        print(
            "🔐 Validando token..."
        )

        user = api.validate_token()

        print(
            f"✓ Token autenticado como: "
            f"{user['login']}"
        )

        if user["scopes"]:

            print(
                "✓ Escopos OAuth detectados:"
            )

            print(
                "  "
                + ", ".join(
                    sorted(
                        user["scopes"]
                    )
                )
            )

        else:

            print(
                "ℹ️ Token provavelmente é "
                "Fine-grained PAT."
            )

            print(
                "ℹ️ As permissões serão "
                "confirmadas pelas operações GitHub."
            )

        # =====================================================
        # PREPARAR ORIGEM
        # =====================================================

        prepared_source, temporary_source = (
            prepare_source(
                source
            )
        )

        # =====================================================
        # GIT AUTH
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

        repository = (
            temporary_repository
            / "repo"
        )

        # =====================================================
        # PREPARAR REPOSITÓRIO
        # =====================================================

        prepare_repository(
            api=api,
            repository_name=repository_name,
            branch=branch,
            create=create,
            private=private,
            description=description,
            repository=repository,
            env=git_env,
        )

        # =====================================================
        # COPIAR ARQUIVOS
        # =====================================================

        total = copy_files(
            source=prepared_source,
            repository=repository,
            remote_dir=remote_dir,
            ignores=ignores,
        )

        # =====================================================
        # VERIFICAR ALTERAÇÕES
        # =====================================================

        status = get_status(
            repository
        )

        if not status:

            print()
            print(
                "ℹ️ Nenhuma alteração detectada."
            )

            print(
                "ℹ️ Nada para fazer."
            )

            return

        # =====================================================
        # COMMIT
        # =====================================================

        create_commit(
            repository=repository,
            message=commit_message,
        )

        # =====================================================
        # PUSH
        # =====================================================

        push(
            repository=repository,
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
            f"👤 Usuário: "
            f"{GITHUB_USERNAME}"
        )

        print(
            f"📦 Repositório: "
            f"{repository_name}"
        )

        print(
            f"🌿 Branch: "
            f"{branch}"
        )

        if remote_dir:

            print(
                f"📂 Subpasta: "
                f"{remote_dir}"
            )

        else:

            print(
                "📂 Subpasta: "
                "(raiz)"
            )

        print(
            f"📄 Arquivos processados: "
            f"{total}"
        )

        print(
            "📝 Commits realizados: 1"
        )

        print(
            "🚀 Push realizado: 1"
        )

        print()

        print(
            f"🔗 https://github.com/"
            f"{GITHUB_USERNAME}/"
            f"{repository_name}"
        )

    finally:

        # =====================================================
        # LIMPAR ZIP/7Z EXTRAÍDO
        # =====================================================

        if temporary_source:

            shutil.rmtree(
                temporary_source,
                ignore_errors=True,
            )

        # =====================================================
        # LIMPAR REPOSITÓRIO
        # =====================================================

        if temporary_repository:

            shutil.rmtree(
                temporary_repository,
                ignore_errors=True,
            )

        # =====================================================
        # LIMPAR ASKPASS
        # =====================================================

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
            "GitHub Uploader - envia pasta, "
            "ZIP ou 7Z para qualquer repositório "
            "de josieljefferson12."
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
    # REPO
    # ---------------------------------------------------------

    parser.add_argument(
        "--repo",
        required=True,
        help=(
            "Nome do repositório GitHub "
            "de destino."
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
        default=(
            "Upload automático de arquivos "
            "via GitHub Uploader"
        ),
        help=(
            "Descrição do repositório "
            "quando ele for criado."
        ),
    )

    # ---------------------------------------------------------
    # REMOTE DIR
    # ---------------------------------------------------------

    parser.add_argument(
        "--remote-dir",
        default="",
        help=(
            "Subpasta dentro do repositório."
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
            "Pode ser repetido ou separado por vírgula."
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

def main() -> None:

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

        # -----------------------------------------------------
        # REPOSITÓRIO
        # -----------------------------------------------------

        repository_name = (
            validate_repository_name(
                args.repo
            )
        )

        # -----------------------------------------------------
        # BRANCH
        # -----------------------------------------------------

        branch = validate_branch(
            args.branch
        )

        # -----------------------------------------------------
        # REMOTE DIR
        # -----------------------------------------------------

        remote_dir = validate_remote_dir(
            args.remote_dir
        )

        # -----------------------------------------------------
        # SOURCE
        # -----------------------------------------------------

        source = Path(
            args.source
        ).expanduser().resolve()

        # -----------------------------------------------------
        # INFORMAÇÕES
        # -----------------------------------------------------

        print(
            f"👤 Usuário:"
        )

        print(
            f"   {GITHUB_USERNAME}"
        )

        print()

        print(
            f"📦 Repositório:"
        )

        print(
            f"   {repository_name}"
        )

        print()

        print(
            f"📁 Origem:"
        )

        print(
            f"   {source}"
        )

        print()

        print(
            f"🌿 Branch:"
        )

        print(
            f"   {branch}"
        )

        print()

        print(
            f"🆕 Criar:"
        )

        print(
            f"   {'sim' if args.create else 'não'}"
        )

        print()

        print(
            f"🔒 Privado:"
        )

        print(
            f"   {'sim' if args.private else 'não'}"
        )

        print()

        print(
            f"📂 Subpasta:"
        )

        print(
            f"   {remote_dir if remote_dir else '(raiz)'}"
        )

        print()

        print(
            f"📝 Commit:"
        )

        print(
            f"   {args.commit}"
        )

        # =====================================================
        # GIT
        # =====================================================

        print()

        check_git()

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
            repository_name=repository_name,
            branch=branch,
            create=args.create,
            private=args.private,
            description=args.description,
            remote_dir=remote_dir,
            ignores=ignores,
            commit_message=args.commit,
        )

    except KeyboardInterrupt:

        print()
        print(
            "⚠️ Operação cancelada pelo usuário."
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
            "❌ Erro de comunicação com o GitHub:"
        )

        print(
            str(exc)
        )

        sys.exit(1)

    except Exception as exc:

        print()
        print(
            "=================================================="
        )

        print(
            "❌ ERRO INESPERADO"
        )

        print(
            "=================================================="
        )

        print()

        print(
            repr(exc)
        )

        sys.exit(1)


# =============================================================
# EXECUÇÃO
# =============================================================

if __name__ == "__main__":

    main()
