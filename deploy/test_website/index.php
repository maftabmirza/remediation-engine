<?php
// index.php
require 'db.php';

$message = "";
$status_color = "green";

try {
    $users = get_users($pdo);
    $message = "Database Connection: SUCCESS";
} catch (Exception $e) {
    $message = "Database Connection: FAILED - " . $e->getMessage();
    $status_color = "red";
}
?>
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <title>Demo App (t-aiops-01)</title>
    <style>
        body {
            font-family: sans-serif;
            padding: 50px;
            background: #f0f0f0;
        }

        .card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
            max-width: 600px;
            margin: 0 auto;
        }

        h1 {
            color: #333;
        }

        .status {
            padding: 10px;
            border-radius: 4px;
            color: white;
            font-weight: bold;
            background-color:
                <?php echo $status_color; ?>
            ;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }

        th,
        td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }

        th {
            background-color: #f2f2f2;
        }
    </style>
</head>

<body>
    <div class="card">
        <h1>Demo Application</h1>
        <p>Server ID: <strong>t-aiops-01</strong></p>
        <div class="status">
            <?php echo $message; ?>
        </div>

        <?php if ($status_color === 'green'): ?>
            <h3>User Data (From DB)</h3>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Email</th>
                </tr>
                <?php foreach ($users as $user): ?>
                    <tr>
                        <td><?php echo htmlspecialchars($user['id']); ?></td>
                        <td><?php echo htmlspecialchars($user['name']); ?></td>
                        <td><?php echo htmlspecialchars($user['email']); ?></td>
                    </tr>
                <?php endforeach; ?>
            </table>
        <?php endif; ?>
    </div>
</body>

</html>