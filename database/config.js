/**
 * Database Configuration
 * Supports SQLite (default) or MongoDB via environment variable
 */
const path = require('path');

const config = {
  // Default: SQLite for local development / production-ready without external DB
  sqlite: {
    filename: path.join(__dirname, 'higala.sqlite'),
  },
  // MongoDB (optional - set USE_MONGO=true in .env to enable)
  mongo: {
    uri: process.env.MONGO_URI || 'mongodb://localhost:27017_higala_express',
  },
  // PostgreSQL (optional - set USE_PG=true in .env to enable)
  postgres: {
    connectionString: process.env.DATABASE_URL || 'postgresql://localhost:5432/higala_express',
  },
};

module.exports = config;
