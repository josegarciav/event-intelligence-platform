CREATE TABLE experience_categories (
    category_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    taxonomy_version TEXT,
    created_at TIMESTAMP
);

CREATE TABLE experience_subcategories (
    subcategory_id TEXT PRIMARY KEY,
    category_id TEXT REFERENCES experience_categories(category_id),
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE experience_activities (
    activity_id UUID PRIMARY KEY,
    subcategory_id TEXT REFERENCES experience_subcategories(subcategory_id),
    name TEXT NOT NULL,
    energy_level TEXT,
    social_intensity TEXT,
    cognitive_load TEXT,
    physical_involvement TEXT,
    cost_level TEXT,
    time_scale TEXT,
    environment TEXT,
    risk_level TEXT,
    age_accessibility TEXT,
    repeatability TEXT,
    notes TEXT
);

