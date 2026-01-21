-- LinkedIn Workflow Database Schema for Supabase

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Customers/Clients Table
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Basic Info
    name TEXT NOT NULL,
    email TEXT,
    company_name TEXT,

    -- LinkedIn Profile
    linkedin_url TEXT NOT NULL UNIQUE,

    -- Metadata
    metadata JSONB DEFAULT '{}'::JSONB
);

-- LinkedIn Profiles Table (scraped data)
CREATE TABLE IF NOT EXISTS linkedin_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Profile Data
    profile_data JSONB NOT NULL,

    -- Extracted Information
    name TEXT,
    headline TEXT,
    summary TEXT,
    location TEXT,
    industry TEXT,

    UNIQUE(customer_id)
);

-- LinkedIn Posts Table (scraped posts)
CREATE TABLE IF NOT EXISTS linkedin_posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Post Data
    post_url TEXT,
    post_text TEXT NOT NULL,
    post_date TIMESTAMP WITH TIME ZONE,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,

    -- Raw Data
    raw_data JSONB,

    UNIQUE(customer_id, post_url)
);

-- Topics Table (extracted from posts)
CREATE TABLE IF NOT EXISTS topics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Topic Info
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,

    -- AI Extraction
    extracted_from_post_id UUID REFERENCES linkedin_posts(id),
    extraction_confidence FLOAT,

    -- Status
    is_used BOOLEAN DEFAULT FALSE,
    used_at TIMESTAMP WITH TIME ZONE
);

-- Profile Analysis Table (AI-generated insights)
CREATE TABLE IF NOT EXISTS profile_analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Analysis Results
    writing_style JSONB NOT NULL,
    tone_analysis JSONB NOT NULL,
    topic_patterns JSONB NOT NULL,
    audience_insights JSONB NOT NULL,

    -- Full Analysis
    full_analysis JSONB NOT NULL,

    UNIQUE(customer_id)
);

-- Research Results Table
CREATE TABLE IF NOT EXISTS research_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Research Data
    query TEXT NOT NULL,
    results JSONB NOT NULL,

    -- Topic Suggestions
    suggested_topics JSONB NOT NULL,

    -- Metadata
    source TEXT DEFAULT 'perplexity'
);

-- Generated Posts Table
CREATE TABLE IF NOT EXISTS generated_posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Topic
    topic_id UUID REFERENCES topics(id),
    topic_title TEXT NOT NULL,

    -- Post Content
    post_content TEXT NOT NULL,

    -- Generation Metadata
    iterations INTEGER DEFAULT 0,
    writer_versions JSONB DEFAULT '[]'::JSONB,
    critic_feedback JSONB DEFAULT '[]'::JSONB,

    -- Status
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'published', 'rejected')),
    approved_at TIMESTAMP WITH TIME ZONE,
    published_at TIMESTAMP WITH TIME ZONE
);

-- Create Indexes
CREATE INDEX idx_customers_linkedin_url ON customers(linkedin_url);
CREATE INDEX idx_linkedin_profiles_customer_id ON linkedin_profiles(customer_id);
CREATE INDEX idx_linkedin_posts_customer_id ON linkedin_posts(customer_id);
CREATE INDEX idx_topics_customer_id ON topics(customer_id);
CREATE INDEX idx_topics_is_used ON topics(is_used);
CREATE INDEX idx_profile_analyses_customer_id ON profile_analyses(customer_id);
CREATE INDEX idx_research_results_customer_id ON research_results(customer_id);
CREATE INDEX idx_generated_posts_customer_id ON generated_posts(customer_id);
CREATE INDEX idx_generated_posts_status ON generated_posts(status);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add trigger to customers table
CREATE TRIGGER update_customers_updated_at
    BEFORE UPDATE ON customers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
