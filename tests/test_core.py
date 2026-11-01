import tempfile
import unittest

from datetime import date
from decimal import Decimal as D
from pathlib import Path
from common.core import Store, history, replay

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=Store(Path(self.temp.name)/'test.sqlite3')
        self.db.create_user('a','Pessoa A','senha-teste-123')
        self.db.create_user('b','Pessoa B','outra-senha-123')
        self.a=self.db.authenticate('a','senha-teste-123')['id']
        self.b=self.db.authenticate('b','outra-senha-123')['id']
        self.db.asset(self.a,'TEST3','Teste','Ação')
        self.i=0
    def tearDown(self): self.temp.cleanup()
    def row(self, kind, day='2024-01-01', **kwargs):
        self.i+=1
        return dict(data=day,ordem=self.i,tipo=kind,**kwargs)
    def add(self,kind,day='2024-01-01',**kwargs):
        self.db.save_movements(self.a,[self.row(kind,day,**kwargs)])
    def test_auth_and_isolation(self):
        self.assertIsNone(self.db.authenticate('a','errada'))
        self.add('APORTE',valor=100)
        self.assertEqual(self.db.movements(self.b),[])
        self.assertEqual(self.db.assets(self.b),[])
        with self.assertRaises(Exception):
            self.db.save_quotes(self.b,[dict(ticker='TEST3',date='2024-01-01',close=10)])
    def test_split_dividend_sale_liquidation(self):
        self.add('APORTE',valor=1000)
        self.add('COMPRA',ticker='TEST3',quantidade=10,preco=50,taxas=2)
        self.add('DESDOBRAMENTO',ticker='TEST3',fator=2)
        self.add('GRUPAMENTO',ticker='TEST3',fator='0.5')
        self.add('BONIFICACAO',ticker='TEST3',quantidade=1)
        self.add('DIVIDENDO',ticker='TEST3',valor=20)
        self.add('VENDA',ticker='TEST3',quantidade=1,preco=55,taxas=1)
        self.add('LIQUIDACAO',ticker='TEST3',valor=600)
        cash,pos=replay(self.db.movements(self.a))
        self.assertEqual(cash,D(1172)); self.assertEqual(pos['TEST3'],0)
    def test_failed_batch_rollback_and_delete(self):
        self.add('APORTE',valor=100)
        with self.assertRaises(ValueError):
            self.db.save_movements(self.a,[self.row('COMPRA',ticker='TEST3',quantidade=20,preco=10)])
        self.assertEqual(len(self.db.movements(self.a)),1)
        self.add('COMPRA',ticker='TEST3',quantidade=10,preco=10)
        with self.assertRaises(ValueError): self.db.delete(self.a,self.db.movements(self.a)[0]['id'])
        self.assertEqual(len(self.db.movements(self.a)),2)
    def test_cotization_external_flow_and_dividend(self):
        self.add('APORTE',valor=100)
        self.add('COMPRA',ticker='TEST3',quantidade=10,preco=10)
        self.add('DIVIDENDO','2024-01-02',ticker='TEST3',valor=10)
        self.add('APORTE','2024-01-03',valor=110)
        quotes=[dict(ticker='TEST3',date='2024-01-01',close='10')]
        series=history(self.db.movements(self.a),quotes,date(2024,1,3))
        self.assertAlmostEqual(series[-1]['valor_cota'],1.1)
        self.assertAlmostEqual(series[-1]['patrimonio'],220)
        self.assertAlmostEqual(series[-1]['cotas'],200)
    def test_split_no_phantom_gain(self):
        self.add('APORTE',valor=100)
        self.add('COMPRA',ticker='TEST3',quantidade=10,preco=10)
        self.add('DESDOBRAMENTO','2024-01-02',ticker='TEST3',fator=2)
        series=history(self.db.movements(self.a),[dict(ticker='TEST3',date='2024-01-01',close=10)],date(2024,1,2))
        self.assertEqual(series[-1]['valor_cota'],1)
    def test_missing_quote(self):
        self.add('APORTE',valor=100)
        self.add('COMPRA',ticker='TEST3',quantidade=10,preco=10)
        with self.assertRaises(ValueError): history(self.db.movements(self.a),[],date(2024,1,1))
    def test_export_restore_and_idempotence(self):
        self.add('APORTE',valor='100.23')
        rows=self.db.movements(self.a)
        self.db.save_movements(self.a,rows)
        self.assertEqual(len(self.db.movements(self.a)),1)
        payload=self.db.export(self.a)
        self.db.restore(self.b,payload)
        self.assertEqual(self.db.assets(self.b),self.db.assets(self.a))
        self.assertEqual(self.db.movements(self.a), self.db.movements(self.b))
    def test_invalid_values_and_unsupported_event(self):
        for kind, kwargs in [('APORTE',dict(valor='NaN')),('INCORPORACAO',{}),('APORTE',dict(valor=10,quantidade=2))]:
            with self.assertRaises(ValueError): self.add(kind,**kwargs)

if __name__=='__main__': unittest.main()
