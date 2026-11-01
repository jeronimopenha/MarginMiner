import os
import tempfile
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from common.core import Store

class UITests(unittest.TestCase):
    def test_setup_login_and_pages(self):
        with tempfile.TemporaryDirectory() as folder:
            old=os.environ.get('CARTEIRA_DB')
            os.environ['CARTEIRA_DB']=str(Path(folder)/'ui.sqlite3')
            try:
                app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=15).run()
                self.assertFalse(app.exception)
                app.text_input[0].input('Pessoa Teste')
                app.text_input[1].input('teste')
                app.text_input[2].input('senha-longa-123')
                app.text_input[3].input('senha-longa-123')
                app.button[0].click().run()
                self.assertFalse(app.exception)
                app.text_input[0].input('teste')
                app.text_input[1].input('senha-longa-123')
                app.button[0].click().run()
                self.assertFalse(app.exception)
                self.assertIn('user',app.session_state)
                uid=app.session_state.user['id']
                store=Store()
                store.asset(uid,'TEST3','Teste','Ação')
                store.save_movements(uid,[dict(data='2024-01-02',ordem=1,tipo='APORTE',valor=100),dict(data='2024-01-02',ordem=2,tipo='COMPRA',ticker='TEST3',quantidade=10,preco=10)])
                store.save_quotes(uid,[dict(ticker='TEST3',date='2024-01-02',close=10)])
                for page in ['Ativos','Lançamentos','Cotações','Importar e exportar','Resumo e cotização']:
                    app.sidebar.radio[0].set_value(page).run()
                    self.assertFalse(app.exception, page)
            finally:
                if old is None: os.environ.pop('CARTEIRA_DB',None)
                else: os.environ['CARTEIRA_DB']=old

if __name__=='__main__': unittest.main()
