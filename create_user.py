"""Crie usuários adicionais no terminal, sem cadastro público."""

from getpass import getpass
from core import Store

if __name__ == "__main__":
    login = input("Login: ")
    name = input("Nome: ")
    password = getpass("Senha: ")
    if password != getpass("Repita a senha: "):
        raise SystemExit("Senhas diferentes.")
    Store().create_user(login, name, password)
    print("Usuário criado.")
