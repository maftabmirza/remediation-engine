-- Count total tables
SELECT COUNT(*) as table_count 
FROM information_schema.tables 
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';

-- Count total columns
SELECT SUM(column_count) as total_columns 
FROM (
  SELECT COUNT(*) as column_count 
  FROM information_schema.columns 
  WHERE table_schema = 'public' 
  GROUP BY table_name
) as counts;

-- List all tables with column counts
SELECT table_name, COUNT(*) as column_count 
FROM information_schema.columns 
WHERE table_schema = 'public' 
GROUP BY table_name 
ORDER BY table_name;
