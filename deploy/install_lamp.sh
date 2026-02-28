#!/bin/bash
# install_lamp.sh
# Installs Apache, MySQL, PHP and sets up the demo database.

set -e

DB_NAME="demo_app"
DB_USER="demo_user"
DB_PASS="demo_pass"

echo ">>> Updating apt repositories..."
sudo apt-get update

echo ">>> Installing Apache, MySQL, PHP..."
sudo apt-get install -y apache2 mysql-server php php-mysql libapache2-mod-php

echo ">>> Configuring MySQL Database..."
sudo mysql -e "CREATE DATABASE IF NOT EXISTS ${DB_NAME};"
sudo mysql -e "CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';"
sudo mysql -e "GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';"
sudo mysql -e "FLUSH PRIVILEGES;"

echo ">>> Seeding Data..."
sudo mysql -e "USE ${DB_NAME}; DROP TABLE IF EXISTS users; CREATE TABLE users (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(50), email VARCHAR(50));"
sudo mysql -e "USE ${DB_NAME}; INSERT INTO users (name, email) VALUES ('Alice Smith', 'alice@example.com'), ('Bob Jones', 'bob@example.com'), ('Charlie Brown', 'charlie@example.com');"

echo ">>> Deploying Website..."
# Assuming scripts are in /tmp/deploy/test_website
sudo rm -rf /var/www/html/index.html
if [ -d "test_website" ]; then
    sudo cp test_website/* /var/www/html/
    sudo chown -R www-data:www-data /var/www/html/
    sudo chmod -R 755 /var/www/html/
else
    echo "WARNING: ./test_website directory not found. Please upload it."
fi

echo ">>> Restarting Apache..."
sudo systemctl restart apache2

echo ">>> LAMP Stack Setup Complete!"
echo "Check http://localhost or http://$(hostname -I | awk '{print $1}')"
