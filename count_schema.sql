SELECT
    (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public') as table_count,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'public') as column_count;
