#!/bin/bash
# Example user data script: Database Server Setup
# This script sets up a MySQL database server with basic configuration

# Update system packages
yum update -y

# Install MySQL 8.0
yum install -y mysql-server

# Start and enable MySQL service
systemctl start mysqld
systemctl enable mysqld

# Get temporary root password
TEMP_PASSWORD=$(grep 'temporary password' /var/log/mysqld.log | awk '{print $NF}')

# Set up MySQL secure installation
mysql -uroot -p"$TEMP_PASSWORD" --connect-expired-password << 'EOF'
ALTER USER 'root'@'localhost' IDENTIFIED BY 'SecurePassword123!';
DELETE FROM mysql.user WHERE User='';
DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');
DROP DATABASE IF EXISTS test;
DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%';
FLUSH PRIVILEGES;
EOF

# Create application database and user
mysql -uroot -p'SecurePassword123!' << 'EOF'
CREATE DATABASE appdb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'appuser'@'%' IDENTIFIED BY 'AppPassword123!';
GRANT ALL PRIVILEGES ON appdb.* TO 'appuser'@'%';
FLUSH PRIVILEGES;
EOF

# Configure MySQL for remote connections
sed -i 's/bind-address.*/bind-address = 0.0.0.0/' /etc/mysql/mysql.conf.d/mysqld.cnf

# Restart MySQL to apply configuration
systemctl restart mysqld

# Install backup tools
yum install -y awscli

# Create backup script
cat << 'EOF' > /opt/mysql-backup.sh
#!/bin/bash
BACKUP_DIR="/opt/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="appdb_backup_$DATE.sql"

mkdir -p $BACKUP_DIR

# Create database backup
mysqldump -uroot -p'SecurePassword123!' appdb > $BACKUP_DIR/$BACKUP_FILE

# Compress backup
gzip $BACKUP_DIR/$BACKUP_FILE

# Upload to S3 (if configured)
if [ ! -z "$S3_BUCKET" ]; then
    aws s3 cp $BACKUP_DIR/$BACKUP_FILE.gz s3://$S3_BUCKET/mysql-backups/
fi

# Keep only last 7 days of backups
find $BACKUP_DIR -name "appdb_backup_*.sql.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE.gz"
EOF

chmod +x /opt/mysql-backup.sh

# Set up cron job for daily backups
echo "0 2 * * * root /opt/mysql-backup.sh >> /var/log/mysql-backup.log 2>&1" >> /etc/crontab

# Install MySQL client tools
yum install -y mysql

# Set up environment variables
cat << 'EOF' >> /etc/environment
MYSQL_ROOT_PASSWORD=SecurePassword123!
MYSQL_DATABASE=appdb
MYSQL_USER=appuser
MYSQL_PASSWORD=AppPassword123!
EOF

# Create MySQL monitoring script
cat << 'EOF' > /opt/mysql-monitor.sh
#!/bin/bash
# Basic MySQL monitoring script

echo "MySQL Status Check - $(date)"
echo "================================"

# Check if MySQL is running
if systemctl is-active --quiet mysqld; then
    echo "✓ MySQL service is running"
else
    echo "✗ MySQL service is not running"
    systemctl start mysqld
fi

# Check MySQL connections
CONNECTIONS=$(mysql -uroot -p'SecurePassword123!' -e "SHOW STATUS LIKE 'Threads_connected';" | awk 'NR==2 {print $2}')
echo "Active connections: $CONNECTIONS"

# Check database size
DB_SIZE=$(mysql -uroot -p'SecurePassword123!' -e "SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 1) AS 'DB Size in MB' FROM information_schema.tables WHERE table_schema='appdb';" | awk 'NR==2 {print $1}')
echo "Database size: ${DB_SIZE} MB"

echo "================================"
EOF

chmod +x /opt/mysql-monitor.sh

echo "MySQL database server setup completed successfully!"
echo "Database: appdb"
echo "User: appuser"
echo "Root password and app password are set in /etc/environment"
