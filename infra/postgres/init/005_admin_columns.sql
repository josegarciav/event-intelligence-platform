-- Add admin-specific columns to the shared users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS api_key TEXT UNIQUE;
