from common.common import get_store
if __name__ == '__main__':
    db = get_store()
    print(f'Banco inicializado em: {db.path}')
