<?php
// db.php
$host = 'localhost';
$db   = 'demo_app';
$user = 'demo_user';
$pass = 'demo_pass';
$charset = 'utf8mb4';

$dsn = "mysql:host=$host;dbname=$db;charset=$charset";
$options = [
    PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
    PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    PDO::ATTR_EMULATE_PREPARES   => false,
];

try {
    $pdo = new PDO($dsn, $user, $pass, $options);
} catch (\PDOException $e) {
    // We want this error to be visible in logs for the AI to find
    error_log("DB_CONNECTION_ERROR: " . $e->getMessage());
    throw new \PDOException($e->getMessage(), (int)$e->getCode());
}

function get_users($pdo) {
    // Simulate a query. If we want to simulate "Slow SQL", we can inject sleep here based on a flag or random chance.
    $stmt = $pdo->query("SELECT * FROM users LIMIT 5");
    return $stmt->fetchAll();
}
?>
