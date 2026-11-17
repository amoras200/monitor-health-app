// Cria um usuário da aplicação com permissão mínima (somente o banco do projeto).
// Roda uma vez, na primeira inicialização do volume do MongoDB.
const dbName = process.env.MONGO_DB;
const appDb = db.getSiblingDB(dbName);
appDb.createUser({
  user: process.env.MONGO_APP_USER,
  pwd: process.env.MONGO_APP_PASSWORD,
  roles: [{ role: "readWrite", db: dbName }],
});
