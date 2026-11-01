
CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_version VALUES(1);
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY, login TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
 salt TEXT NOT NULL, password_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS assets(
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 ticker TEXT NOT NULL, name TEXT NOT NULL, category TEXT NOT NULL,
 UNIQUE(user_id,ticker));
CREATE TABLE IF NOT EXISTS quotes(
 user_id INTEGER NOT NULL REFERENCES users(id), ticker TEXT NOT NULL,
 date TEXT NOT NULL, close TEXT NOT NULL,
 PRIMARY KEY(user_id,ticker,date),
 FOREIGN KEY(user_id,ticker) REFERENCES assets(user_id,ticker));
CREATE TABLE IF NOT EXISTS movements(
 id TEXT NOT NULL, user_id INTEGER NOT NULL REFERENCES users(id),
 data TEXT NOT NULL, ordem INTEGER NOT NULL CHECK(ordem > 0), tipo TEXT NOT NULL,
 ticker TEXT, quantidade TEXT NOT NULL, preco TEXT NOT NULL,
 valor TEXT NOT NULL, taxas TEXT NOT NULL, fator TEXT NOT NULL, observacao TEXT NOT NULL,
 FOREIGN KEY(user_id,ticker) REFERENCES assets(user_id,ticker),
 UNIQUE(user_id,data,ordem), PRIMARY KEY(user_id,id));
CREATE INDEX IF NOT EXISTS movements_date ON movements(user_id,data,ordem,id);
