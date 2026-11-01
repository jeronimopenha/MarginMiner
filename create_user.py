from getpass import getpass
from common.common import get_store

if __name__ == "__main__":
    login = input("Login: ")
    name = input("Nome: ")
    password = getpass("Senha: ")
    if password != getpass("Repita a senha: "):
        raise SystemExit("Senhas diferentes.")
    store = get_store()
    store.create_user(login, name, password)
    print("Usuário criado.")
