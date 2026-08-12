#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=============================================================
                 🚀 GITHUB UPLOADER
=============================================================

Upload de uma pasta, ZIP ou 7Z para qualquer repositório
do GitHub utilizando um Personal Access Token.

Compatível com GitHub Actions.

-------------------------------------------------------------
FUNCIONALIDADES
-------------------------------------------------------------

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
✓ Repositório público
✓ Repositório privado
✓ Descoberta automática do usuário através do PAT
✓ Validação do PAT
✓ Validação das permissões
✓ Atualização de arquivos existentes
✓ Criação de arquivos novos
✓ Preservação da estrutura de diretórios
✓ Um único git add
✓ Um único commit
✓ Um único push

-------------------------------------------------------------
TOKEN
-------------------------------------------------------------

Variável de ambiente:

    MY_GITHUB_TOKEN

GitHub Actions:

    Settings
    → Secrets and variables
    → Actions
    → Repository secrets
    → MY_GITHUB_TOKEN

-------------------------------------------------------------
EXEMPLOS
-------------------------------------------------------------

Pasta:

    python github_uploader.py pasta \
        --repo MEU-REPOSITORIO

ZIP:

    python github_uploader.py arquivo.zip \
        --repo MEU-REPOSITORIO

7Z:

    python github_uploader.py arquivo.7z \
        --repo MEU-REPOSITORIO

Criar:

    python github_uploader.py arquivo.zip \
        --repo MEU-REPOSITORIO \
        --create

Criar privado:

    python github_uploader.py arquivo.zip \
        --repo MEU-REPOSITORIO \
        --create \
        --private

Branch:

    python github_uploader.py arquivo.zip \
        --repo MEU-REPOSITORIO \
        --branch main

Subpasta:

    python github_uploader.py arquivo.zip \
        --repo MEU-REPOSITORIO \
        --remote-dir backup

Commit:

    python github_uploader.py arquivo.zip \
        --repo MEU-REPOSITORIO \
        --commit "Atualização automática"

Descrição:

    python github_uploader.py arquivo.zip \
        --repo MEU-REPOSITORIO \
        --create \
        --description "Meu projeto"

Ignore:

    python github_uploader.py arquivo.zip \
        --repo MEU-REPOSITORIO \
        --ignore .git \
        --ignore __pycache__

=============================================================
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

import requests


# =============================================================
# CONFIGURAÇÕES
# =============================================================

GITHUB_API = "https://api.github.com"

DEFAULT_BRANCH = "main"

TOKEN_ENVIRONMENT = "MY_GITHUB_TOKEN"

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
            "Instale o Git antes de executar o programa."
        )

    if check and result.returncode != 0:

        stderr = result.stderr.strip()

        stdout = result.stdout.strip()

        details = stderr or stdout or "Sem detalhes."

        raise GitHubUploaderError(
            "Erro executando Git:\n\n"
            f"git {' '.join(args)}\n\n"
            f"{details}"
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
            "Git não está instalado ou não está disponível no PATH."
        )

    print(
        f"✓ {result.stdout.strip()}"
    )


# =============================================================
# GITHUB API
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
                    "github-uploader",
            }
        )

    # ---------------------------------------------------------
    # REQUEST
    # ---------------------------------------------------------

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

            return {}

    # ---------------------------------------------------------
    # USUÁRIO AUTENTICADO
    # ---------------------------------------------------------

    def get_authenticated_user(self):

        return self.request(
            "GET",
            f"{GITHUB_API}/user",
        )

    # ---------------------------------------------------------
    # CABEÇALHOS DE PERMISSÃO
    # ---------------------------------------------------------

    def get_permission_scopes(self) -> list[str]:

        try:

            response = self.session.get(
                f"{GITHUB_API}/user",
                timeout=60,
            )

        except requests.RequestException as exc:

            raise GitHubUploaderError(
                "Erro verificando permissões do token:\n"
                f"{exc}"
            )

        if not response.ok:

            raise GitHubUploaderError(
                "Não foi possível verificar as permissões "
                "do token."
            )

        header = response.headers.get(
            "X-OAuth-Scopes",
            "",
        )

        scopes = []

        for item in header.split(","):

            item = item.strip()

            if item:

                scopes.append(item)

        return sorted(
            set(scopes)
        )

    # ---------------------------------------------------------
    # REPOSITÓRIO EXISTE
    # ---------------------------------------------------------

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
            )

        if response.status_code == 200:

            return True

        if response.status_code == 404:

            return False

        try:

            data = response.json()

            message = data.get(
                "message",
                response.text,
            )

        except Exception:

            message = response.text

        raise GitHubUploaderError(
            "Erro verificando o repositório:\n"
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
            "📦 Criando repositório:"
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
# VALIDAR TOKEN
# =============================================================

def validate_token(
    api: GitHubAPI,
) -> str:

    print(
        "🔐 Validando token..."
    )

    user = api.get_authenticated_user()

    login = user.get(
        "login"
    )

    if not login:

        raise GitHubUploaderError(
            "O GitHub não retornou o usuário autenticado."
        )

    print(
        "✓ Token autenticado como:"
    )

    print(
        f"   {login}"
    )

    return login


# =============================================================
# VALIDAR PERMISSÕES
# =============================================================

def validate_permissions(
    api: GitHubAPI,
    create: bool,
):

    print(
        "🔐 Verificando permissões do token..."
    )

    scopes = api.get_permission_scopes()

    if scopes:

        print(
            "✓ Escopos detectados:"
        )

        for scope in scopes:

            print(
                f"   • {scope}"
            )

    else:

        print(
            "ℹ️ O GitHub não informou escopos "
            "OAuth no cabeçalho."
        )

    # ---------------------------------------------------------
    # Verificação de PAT clássico
    # ---------------------------------------------------------

    if scopes:

        has_repo = (
            "repo" in scopes
        )

        has_public_repo = (
            "public_repo" in scopes
        )

        if not (
            has_repo
            or has_public_repo
        ):

            if create:

                raise GitHubUploaderError(
                    "O PAT não possui o escopo "
                    "'repo' ou 'public_repo'.\n\n"
                    "Para este uploader, use um PAT "
                    "com permissões adequadas."
                )

            raise GitHubUploaderError(
                "O PAT não possui permissões suficientes "
                "para acessar repositórios."
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
            "O arquivo ZIP é inválido ou está corrompido."
        )


# =============================================================
# VERIFICAR CAMINHO SEGURO DO ZIP
# =============================================================

def safe_extract_zip(
    source: Path,
    destination: Path,
):

    try:

        with zipfile.ZipFile(
            source,
            "r",
        ) as archive:

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
                    + os.sep
                ):

                    raise GitHubUploaderError(
                        "O ZIP contém um caminho inválido "
                        "que tenta sair da pasta de extração:\n"
                        f"{member.filename}"
                    )

            archive.extractall(
                destination
            )

    except zipfile.BadZipFile:

        raise GitHubUploaderError(
            "O arquivo ZIP é inválido ou está corrompido."
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
            "Erro extraindo o arquivo 7Z:\n"
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

            safe_extract_zip(
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
# CRIAR AMBIENTE GIT
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

        current_mode = (
            askpass.stat().st_mode
        )

        askpass.chmod(
            current_mode
            | stat.S_IXUSR
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

def get_remote_url(
    owner: str,
    repository: str,
) -> str:

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
# CONFIGURAR ORIGIN
# =============================================================

def configure_remote(
    repository: Path,
    owner: str,
    repository_name: str,
):

    remote_url = get_remote_url(
        owner,
        repository_name,
    )

    print()
    print(
        "🌐 Configurando origin:"
    )

    print(
        f"   {remote_url}"
    )

    existing = run_git(
        "remote",
        "get-url",
        "origin",
        cwd=repository,
        check=False,
    )

    if existing.returncode == 0:

        run_git(
            "remote",
            "set-url",
            "origin",
            remote_url,
            cwd=repository,
        )

    else:

        run_git(
            "remote",
            "add",
            "origin",
            remote_url,
            cwd=repository,
        )


# =============================================================
# CLONAR REPOSITÓRIO
# =============================================================

def clone_repository(
    destination: Path,
    owner: str,
    repository_name: str,
    branch: str,
    env: dict,
):

    remote_url = get_remote_url(
        owner,
        repository_name,
    )

    print()
    print(
        "📥 Clonando repositório:"
    )

    print(
        f"   {owner}/{repository_name}"
    )

    # ---------------------------------------------------------
    # Tentar branch solicitada
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
    # Remover clone parcial
    # ---------------------------------------------------------

    if destination.exists():

        shutil.rmtree(
            destination,
            ignore_errors=True,
        )

    # ---------------------------------------------------------
    # Tentar clone padrão
    # ---------------------------------------------------------

    print(
        "⚠️ A branch solicitada não pôde ser clonada."
    )

    print(
        "📥 Tentando clone padrão do repositório..."
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

        details = (
            result.stderr.strip()
            or result.stdout.strip()
            or "Sem detalhes."
        )

        raise GitHubUploaderError(
            "Não foi possível clonar o repositório:\n\n"
            f"{owner}/{repository_name}\n\n"
            f"{details}"
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
    repository: Path,
    env: dict,
):

    exists = api.repository_exists(
        owner,
        repository_name,
    )

    # ---------------------------------------------------------
    # REPOSITÓRIO NÃO EXISTE
    # ---------------------------------------------------------

    if not exists:

        if not create:

            raise GitHubUploaderError(
                f"O repositório "
                f"{owner}/{repository_name} "
                "não existe.\n\n"
                "Use --create para criá-lo."
            )

        print()
        print(
            f"📦 Criando repositório:"
        )

        print(
            f"   {owner}/{repository_name}"
        )

        api.create_repository(
            name=repository_name,
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

        configure_remote(
            repository=repository,
            owner=owner,
            repository_name=repository_name,
        )

        print(
            "✓ Repositório criado."
        )

        return

    # ---------------------------------------------------------
    # REPOSITÓRIO EXISTE
    # ---------------------------------------------------------

    clone_repository(
        destination=repository,
        owner=owner,
        repository_name=repository_name,
        branch=branch,
        env=env,
    )

    # ---------------------------------------------------------
    # GARANTIR ORIGIN CORRETO
    # ---------------------------------------------------------

    configure_remote(
        repository=repository,
        owner=owner,
        repository_name=repository_name,
    )

    # ---------------------------------------------------------
    # VERIFICAR BRANCH ATUAL
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

    result = run_git(
        "commit",
        "-m",
        message,
        cwd=repository,
        check=False,
    )

    if result.returncode != 0:

        output = (
            result.stderr.strip()
            or result.stdout.strip()
        )

        raise GitHubUploaderError(
            "Não foi possível criar o commit:\n"
            f"{output}"
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
# PROCESSO PRINCIPAL
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

    # ---------------------------------------------------------
    # LIMPAR ESPAÇOS
    # ---------------------------------------------------------

    repository_name = (
        repository_name.strip()
    )

    branch = branch.strip()

    remote_dir = (
        remote_dir.strip()
    )

    commit_message = (
        commit_message.strip()
    )

    # ---------------------------------------------------------
    # VALIDAR REPOSITÓRIO
    # ---------------------------------------------------------

    if not repository_name:

        raise GitHubUploaderError(
            "O nome do repositório não pode estar vazio."
        )

    if not branch:

        raise GitHubUploaderError(
            "A branch não pode estar vazia."
        )

    if not commit_message:

        raise GitHubUploaderError(
            "A mensagem do commit não pode estar vazia."
        )

    try:

        # -----------------------------------------------------
        # API
        # -----------------------------------------------------

        api = GitHubAPI(
            token
        )

        # -----------------------------------------------------
        # TOKEN
        # -----------------------------------------------------

        owner = validate_token(
            api
        )

        # -----------------------------------------------------
        # PERMISSÕES
        # -----------------------------------------------------

        validate_permissions(
            api,
            create=create,
        )

        # -----------------------------------------------------
        # MOSTRAR DESTINO
        # -----------------------------------------------------

        remote_url = get_remote_url(
            owner,
            repository_name,
        )

        print()
        print(
            "=================================================="
        )

        print(
            "📦 DESTINO"
        )

        print(
            "=================================================="
        )

        print(
            f"👤 Usuário: {owner}"
        )

        print(
            f"📦 Repositório: {repository_name}"
        )

        print(
            f"🌐 URL: {remote_url}"
        )

        print(
            f"🌿 Branch: {branch}"
        )

        print(
            f"🆕 Criar: "
            f"{'sim' if create else 'não'}"
        )

        print(
            f"🔒 Privado: "
            f"{'sim' if private else 'não'}"
        )

        print(
            f"📂 Subpasta: "
            f"{remote_dir if remote_dir else '(raiz)'}"
        )

        print(
            f"📝 Commit: {commit_message}"
        )

        # -----------------------------------------------------
        # ORIGEM
        # -----------------------------------------------------

        prepared_source, temporary_source = (
            prepare_source(
                source
            )
        )

        # -----------------------------------------------------
        # AUTENTICAÇÃO GIT
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
            owner=owner,
            repository_name=repository_name,
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
        # GARANTIR ORIGIN CORRETO
        # -----------------------------------------------------

        configure_remote(
            repository=repository,
            owner=owner,
            repository_name=repository_name,
        )

        # -----------------------------------------------------
        # COPIAR
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

            print(
                "ℹ️ Nenhum commit ou push foi realizado."
            )

            return

        # -----------------------------------------------------
        # UM COMMIT
        # -----------------------------------------------------

        create_commit(
            repository=repository,
            message=commit_message,
        )

        # -----------------------------------------------------
        # UM PUSH
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
            f"👤 Usuário: {owner}"
        )

        print(
            f"📦 Repositório: "
            f"{repository_name}"
        )

        print(
            f"🌿 Branch: "
            f"{branch}"
        )

        print(
            f"📄 Arquivos processados: "
            f"{total}"
        )

        print(
            "📝 Commits realizados: 1"
        )

        print(
            "🚀 Push realizados: 1"
        )

        print()

        print(
            f"🌐 https://github.com/"
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
            "para um repositório do GitHub."
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
            "Cria o repositório caso ele não exista."
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
            "Subpasta no repositório."
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
            "Pode ser repetido."
        ),
    )

    # ---------------------------------------------------------
    # COMMIT
    # ---------------------------------------------------------

    parser.add_argument(
        "--commit",
        default=(
            "Upload automático"
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
            "             🚀 GITHUB UPLOADER"
        )

        print(
            "=================================================="
        )

        print()

        print(
            f"📦 Repositório:"
        )

        print(
            f"   {args.repo}"
        )

        print()

        print(
            f"📁 Origem:"
        )

        print(
            f"   {args.source}"
        )

        print()

        print(
            f"🌿 Branch:"
        )

        print(
            f"   {args.branch}"
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
            f"   {args.remote_dir or '(raiz)'}"
        )

        print()

        print(
            f"📝 Commit:"
        )

        print(
            f"   {args.commit}"
        )

        # -----------------------------------------------------
        # GIT
        # -----------------------------------------------------

        check_git()

        # -----------------------------------------------------
        # SOURCE
        # -----------------------------------------------------

        source = Path(
            args.source
        ).expanduser().resolve()

        print()

        print(
            "📁 Origem absoluta:"
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
            "❌ Erro de comunicação com GitHub:"
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
